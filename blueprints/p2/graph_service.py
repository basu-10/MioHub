"""Service helpers for graph workspaces (proprietary_graph).

Keeps serialization logic centralized so routes remain lean/testable.
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple
from datetime import datetime
from sqlalchemy.orm.attributes import flag_modified

from extensions import db
from .models import (
    File,
    Folder,
    GraphWorkspace,
    GraphNode,
    GraphEdge,
    GraphNodeAttachment,
)

ALLOWED_ATTACHMENT_TYPES = {"file", "folder", "url", "task"}


def ensure_workspace(
    file_obj: File,
    owner_id: int,
    folder_id: int | None,
    create_if_missing: bool = True,
) -> GraphWorkspace | None:
    """Return an existing GraphWorkspace for the file or create one if missing."""
    if file_obj.graph_workspace:
        return file_obj.graph_workspace
    if not create_if_missing:
        return None
    workspace = GraphWorkspace(
        file_id=file_obj.id,
        owner_id=owner_id,
        folder_id=folder_id,
        settings_json={},
        metadata_json={},
    )
    db.session.add(workspace)
    db.session.flush()
    return workspace


def serialize_graph(workspace: GraphWorkspace) -> Dict:
    """Serialize graph workspace with nodes, edges, and attachments."""
    if workspace is None:
        return {
            "graph_id": None,
            "file_id": None,
            "nodes": [],
            "edges": [],
            "settings": {},
            "metadata": {},
        }

    def _serialize_attachment(att: GraphNodeAttachment) -> Dict:
        payload = {
            "id": att.id,
            "node_id": att.node_id,
            "attachment_type": att.attachment_type,
            "metadata": att.metadata_json or {},
        }
        if att.file_id:
            payload["file_id"] = att.file_id
        if att.folder_id:
            payload["folder_id"] = att.folder_id
        if att.url:
            payload["url"] = att.url
        return payload

    nodes = []
    for node in workspace.nodes:
        nodes.append(
            {
                "id": node.id,
                "graph_id": node.graph_id,
                "title": node.title,
                "summary": node.summary or "",
                "position": node.position_json or {},
                "size": node.size_json or {},
                "style": node.style_json or {},
                "metadata": node.metadata_json or {},
                "attachments": [_serialize_attachment(a) for a in node.attachments],
            }
        )

    edges = []
    for edge in workspace.edges:
        edges.append(
            {
                "id": edge.id,
                "graph_id": edge.graph_id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "label": edge.label or "",
                "edge_type": edge.edge_type or "directed",
                "metadata": edge.metadata_json or {},
            }
        )

    return {
        "graph_id": workspace.id,
        "file_id": workspace.file_id,
        "settings": workspace.settings_json or {},
        "metadata": workspace.metadata_json or {},
        "nodes": nodes,
        "edges": edges,
    }


def rebuild_content_snapshot(file_obj: File) -> int:
    """Update File.content_json to reflect current graph; return size delta in bytes."""
    workspace = file_obj.graph_workspace or GraphWorkspace.query.filter_by(file_id=file_obj.id).first()
    if not workspace:
        workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    if not workspace:
        return 0

    # Ensure any pending node/edge writes are flushed before serialization
    db.session.flush()

    old_size = file_obj.get_content_size()
    snapshot = serialize_graph(workspace)
    file_obj.content_json = snapshot
    flag_modified(file_obj, "content_json")
    file_obj.last_modified = datetime.utcnow()
    new_size = file_obj.get_content_size()
    return new_size - old_size


def validate_attachment_ownership(
    attachment_type: str,
    file_id: int | None,
    folder_id: int | None,
    user_id: int,
) -> Tuple[bool, str | None]:
    """Verify attachment targets belong to the user. Returns (ok, error_message)."""
    if attachment_type not in ALLOWED_ATTACHMENT_TYPES:
        return False, f"Invalid attachment_type '{attachment_type}'."

    if attachment_type == "file":
        if not file_id:
            return False, "file_id is required for attachment_type 'file'."
        file_obj = File.query.get(file_id)
        if not file_obj or file_obj.owner_id != user_id:
            return False, "File not found or unauthorized."
    elif attachment_type == "folder":
        if not folder_id:
            return False, "folder_id is required for attachment_type 'folder'."
        folder = Folder.query.get(folder_id)
        if not folder or folder.user_id != user_id:
            return False, "Folder not found or unauthorized."
    elif attachment_type == "url":
        if not file_id and not folder_id:
            return True, None  # URL-only; handled in routes
    # "task" is allowed but validated upstream when tasks are introduced
    return True, None


def jsonl_export(workspace: GraphWorkspace) -> str:
    """Export graph as JSONL (graph, nodes, edges, attachments lines)."""
    payloads: List[Dict] = []
    graph_header = {
        "type": "graph",
        "graph_id": workspace.id,
        "file_id": workspace.file_id,
        "settings": workspace.settings_json or {},
        "metadata": workspace.metadata_json or {},
    }
    payloads.append(graph_header)

    for node in workspace.nodes:
        payloads.append(
            {
                "type": "node",
                "graph_id": workspace.id,
                "id": node.id,
                "title": node.title,
                "summary": node.summary or "",
                "position": node.position_json or {},
                "size": node.size_json or {},
                "style": node.style_json or {},
                "metadata": node.metadata_json or {},
            }
        )
        for att in node.attachments:
            payloads.append(
                {
                    "type": "attachment",
                    "graph_id": workspace.id,
                    "node_id": node.id,
                    "attachment_type": att.attachment_type,
                    "file_id": att.file_id,
                    "folder_id": att.folder_id,
                    "url": att.url,
                    "metadata": att.metadata_json or {},
                }
            )

    for edge in workspace.edges:
        payloads.append(
            {
                "type": "edge",
                "graph_id": workspace.id,
                "id": edge.id,
                "source_node_id": edge.source_node_id,
                "target_node_id": edge.target_node_id,
                "label": edge.label or "",
                "edge_type": edge.edge_type or "directed",
                "metadata": edge.metadata_json or {},
            }
        )

    return "\n".join(json.dumps(p) for p in payloads)
