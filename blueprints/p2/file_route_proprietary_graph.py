from flask import Blueprint, request, jsonify, render_template, abort, Response
from flask_login import current_user, login_required
from datetime import datetime
from html import unescape
import re

from extensions import db
from .models import File, GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment, Folder
from .graph_service import (
    ensure_workspace,
    rebuild_content_snapshot,
    serialize_graph,
    validate_attachment_ownership,
    jsonl_export,
)
from utilities_main import update_user_data_size, check_guest_limit
from . import graph_bp

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_plain_text(value: str, max_len: int | None = None) -> str:
    """Strip HTML and return trimmed plain text. Falls back to empty string."""
    if not isinstance(value, str):
        return ""
    cleaned = unescape(value)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = cleaned.replace("\r", "").strip()
    if max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def _get_graph_file(file_id: int) -> File | None:
    return File.query.filter_by(id=file_id, type='proprietary_graph').first()


def _authorize_read(file_obj: File):
    if not file_obj:
        abort(404)
    if file_obj.is_public:
        return
    if not current_user.is_authenticated or file_obj.owner_id != current_user.id:
        abort(403)


def _authorize_write(file_obj: File):
    if not file_obj:
        abort(404)
    if not current_user.is_authenticated or file_obj.owner_id != current_user.id:
        abort(403)


@graph_bp.route('/<int:file_id>', methods=['GET'])
def view_graph(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_read(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id, create_if_missing=False)
    if not workspace:
        abort(404)
    snapshot = serialize_graph(workspace)
    return render_template(
        'p2/graph_workspace.html',
        file=file_obj,
        graph=workspace,
        snapshot=snapshot,
        is_owner=current_user.is_authenticated and current_user.id == file_obj.owner_id,
    )


@graph_bp.route('/<int:file_id>/data', methods=['GET'])
def graph_data(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_read(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id, create_if_missing=False)
    if not workspace:
        abort(404)
    return jsonify({"ok": True, "graph": serialize_graph(workspace)})


@graph_bp.route('/<int:file_id>/nodes', methods=['POST'])
@login_required
def create_node(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400

    title = _clean_plain_text(data.get('title') or 'Untitled', max_len=255) or 'Untitled'
    summary = _clean_plain_text(data.get('summary', ''))
    node = GraphNode(
        graph_id=workspace.id,
        title=title,
        summary=summary,
        position_json=data.get('position') or {},
        size_json=data.get('size') or {},
        style_json=data.get('style') or {},
        metadata_json=data.get('metadata') or {},
    )
    db.session.add(node)
    db.session.flush()

    size_delta = rebuild_content_snapshot(file_obj)
    if size_delta > 0 and not check_guest_limit(current_user, size_delta):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Data limit exceeded"}), 400

    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "node": serialize_graph(workspace)["nodes"][-1]})


@graph_bp.route('/<int:file_id>/nodes/<int:node_id>', methods=['PATCH'])
@login_required
def update_node(file_id: int, node_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    node = GraphNode.query.filter_by(id=node_id, graph_id=workspace.id).first()
    if not node:
        abort(404)

    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400

    field_map = [
        ('title', 'title', False),
        ('summary', 'summary', False),
        ('position', 'position_json', True),
        ('size', 'size_json', True),
        ('style', 'style_json', True),
        ('metadata', 'metadata_json', True),
    ]
    for field, attr, expect_json in field_map:
        if field in data:
            value = data.get(field)
            if expect_json:
                value = value if isinstance(value, dict) else {}
            elif attr == 'title':
                value = _clean_plain_text(value, max_len=255) or node.title
            elif attr == 'summary':
                value = _clean_plain_text(value)
            setattr(node, attr, value or {} if expect_json else value)
    node.updated_at = datetime.utcnow()
    db.session.flush()

    try:
        size_delta = rebuild_content_snapshot(file_obj)
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "Failed to save node"}), 500
    if size_delta > 0 and not check_guest_limit(current_user, size_delta):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Data limit exceeded"}), 400

    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "node": serialize_graph(workspace)["nodes"]})


@graph_bp.route('/<int:file_id>/nodes/<int:node_id>', methods=['DELETE'])
@login_required
def delete_node(file_id: int, node_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    node = GraphNode.query.filter_by(id=node_id, graph_id=workspace.id).first()
    if not node:
        abort(404)

    GraphEdge.query.filter(
        (GraphEdge.source_node_id == node_id) | (GraphEdge.target_node_id == node_id)
    ).delete(synchronize_session=False)
    GraphNodeAttachment.query.filter_by(node_id=node_id).delete(synchronize_session=False)
    db.session.delete(node)

    size_delta = rebuild_content_snapshot(file_obj)
    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "size_delta": size_delta})


@graph_bp.route('/<int:file_id>/edges', methods=['POST'])
@login_required
def create_edge(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    data = request.get_json(force=True) or {}

    source_id = data.get('source_node_id')
    target_id = data.get('target_node_id')
    if not source_id or not target_id:
        return jsonify({"ok": False, "error": "source_node_id and target_node_id are required"}), 400

    for node_id in [source_id, target_id]:
        if not GraphNode.query.filter_by(id=node_id, graph_id=workspace.id).first():
            return jsonify({"ok": False, "error": f"Node {node_id} not found in graph"}), 404

    edge = GraphEdge(
        graph_id=workspace.id,
        source_node_id=source_id,
        target_node_id=target_id,
        label=data.get('label'),
        edge_type=data.get('edge_type') or 'directed',
        metadata_json=data.get('metadata') or {},
    )
    db.session.add(edge)
    db.session.flush()

    size_delta = rebuild_content_snapshot(file_obj)
    if size_delta > 0 and not check_guest_limit(current_user, size_delta):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Data limit exceeded"}), 400

    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "edge": serialize_graph(workspace)["edges"][-1]})


@graph_bp.route('/<int:file_id>/edges/<int:edge_id>', methods=['DELETE'])
@login_required
def delete_edge(file_id: int, edge_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    edge = GraphEdge.query.filter_by(id=edge_id, graph_id=workspace.id).first()
    if not edge:
        abort(404)

    db.session.delete(edge)
    size_delta = rebuild_content_snapshot(file_obj)
    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "size_delta": size_delta})


@graph_bp.route('/<int:file_id>/edges/<int:edge_id>', methods=['PUT'])
@login_required
def update_edge(file_id: int, edge_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    edge = GraphEdge.query.filter_by(id=edge_id, graph_id=workspace.id).first()
    if not edge:
        abort(404)

    data = request.get_json(force=True) or {}
    
    # Update label if provided
    if 'label' in data:
        edge.label = data['label']
    
    # Update edge_type (direction) if provided
    if 'edge_type' in data:
        edge.edge_type = data['edge_type']
    
    # Update metadata if provided
    if 'metadata' in data:
        edge.metadata_json = data['metadata']
    
    db.session.flush()
    size_delta = rebuild_content_snapshot(file_obj)
    
    if size_delta > 0 and not check_guest_limit(current_user, size_delta):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Data limit exceeded"}), 400
    
    db.session.commit()
    update_user_data_size(current_user, size_delta)
    
    # Return updated edge
    updated_edges = serialize_graph(workspace)["edges"]
    updated_edge = next((e for e in updated_edges if e['id'] == edge_id), None)
    return jsonify({"ok": True, "edge": updated_edge})


@graph_bp.route('/<int:file_id>/attachments', methods=['POST'])
@login_required
def add_attachment(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    data = request.get_json(force=True) or {}

    node_id = data.get('node_id')
    attachment_type = data.get('attachment_type')
    target_file_id = data.get('file_id')
    target_folder_id = data.get('folder_id')
    url = data.get('url')

    node = GraphNode.query.filter_by(id=node_id, graph_id=workspace.id).first()
    if not node:
        abort(404)

    ok, error = validate_attachment_ownership(attachment_type, target_file_id, target_folder_id, current_user.id)
    if not ok:
        return jsonify({"ok": False, "error": error}), 400

    # Check for duplicate attachment
    existing = None
    if attachment_type == 'file' and target_file_id:
        existing = GraphNodeAttachment.query.filter_by(
            node_id=node_id,
            attachment_type='file',
            file_id=target_file_id
        ).first()
    elif attachment_type == 'folder' and target_folder_id:
        existing = GraphNodeAttachment.query.filter_by(
            node_id=node_id,
            attachment_type='folder',
            folder_id=target_folder_id
        ).first()
    
    if existing:
        return jsonify({"ok": False, "error": "This file/folder is already attached to this node"}), 400

    # Prepare metadata with file type for proper routing
    metadata = data.get('metadata') or {}
    if attachment_type == 'file' and target_file_id:
        file_item = File.query.get(target_file_id)
        if file_item:
            metadata['file_type'] = file_item.type
            metadata['title'] = file_item.title
    elif attachment_type == 'folder' and target_folder_id:
        folder_item = Folder.query.get(target_folder_id)
        if folder_item:
            metadata['title'] = folder_item.name

    attachment = GraphNodeAttachment(
        node_id=node_id,
        attachment_type=attachment_type,
        file_id=target_file_id,
        folder_id=target_folder_id,
        url=url,
        metadata_json=metadata,
    )
    db.session.add(attachment)
    db.session.flush()

    size_delta = rebuild_content_snapshot(file_obj)
    if size_delta > 0 and not check_guest_limit(current_user, size_delta):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Data limit exceeded"}), 400

    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "attachment": attachment.id})


@graph_bp.route('/<int:file_id>/attachments/<int:attachment_id>', methods=['DELETE'])
@login_required
def delete_attachment(file_id: int, attachment_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)
    att = GraphNodeAttachment.query.join(GraphNode).filter(
        GraphNodeAttachment.id == attachment_id,
        GraphNode.graph_id == workspace.id,
    ).first()
    if not att:
        abort(404)

    db.session.delete(att)
    size_delta = rebuild_content_snapshot(file_obj)
    db.session.commit()
    update_user_data_size(current_user, size_delta)
    return jsonify({"ok": True, "size_delta": size_delta})


@graph_bp.route('/<int:file_id>/refresh-attachments', methods=['POST'])
@login_required
def refresh_attachments(file_id: int):
    """Refresh attachment metadata with current file/folder names"""
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id, create_if_missing=False)
    if not workspace:
        abort(404)
    
    # Get all attachments in this graph
    attachments = GraphNodeAttachment.query.join(GraphNode).filter(
        GraphNode.graph_id == workspace.id
    ).all()
    
    updated_count = 0
    for att in attachments:
        new_title = None
        new_file_type = None
        
        if att.attachment_type == 'file' and att.file_id:
            file_item = File.query.get(att.file_id)
            if file_item:
                type_suffix = f' ({file_item.type})' if file_item.type else ''
                new_title = f'{file_item.title}{type_suffix}'
                new_file_type = file_item.type
        elif att.attachment_type == 'folder' and att.folder_id:
            folder_item = Folder.query.get(att.folder_id)
            if folder_item:
                new_title = folder_item.name
        
        # Update metadata if we found a new title or file type
        if new_title or new_file_type:
            if not att.metadata_json:
                att.metadata_json = {}
            old_title = att.metadata_json.get('title', '')
            old_file_type = att.metadata_json.get('file_type', '')
            changed = False
            if new_title and old_title != new_title:
                att.metadata_json['title'] = new_title
                changed = True
            if new_file_type and old_file_type != new_file_type:
                att.metadata_json['file_type'] = new_file_type
                changed = True
            if changed:
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(att, 'metadata_json')
                updated_count += 1
    
    if updated_count > 0:
        size_delta = rebuild_content_snapshot(file_obj)
        db.session.commit()
        update_user_data_size(current_user, size_delta)
    else:
        db.session.commit()
    
    return jsonify({"ok": True, "updated_count": updated_count})


@graph_bp.route('/<int:file_id>/settings', methods=['PATCH'])
@login_required
def update_settings(file_id: int):
    """Update workspace settings (viewport, zoom, preferences)."""
    file_obj = _get_graph_file(file_id)
    _authorize_write(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id)

    data = request.get_json(force=True) or {}
    settings = workspace.settings_json or {}
    
    # Update canvas/viewport settings
    if 'canvas' in data:
        settings['canvas'] = {**settings.get('canvas', {}), **data['canvas']}
    
    # Update any other settings passed
    for key in data:
        if key != 'canvas':
            settings[key] = data[key]
    
    workspace.settings_json = settings
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(workspace, 'settings_json')
    workspace.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"ok": True, "settings": settings})


@graph_bp.route('/<int:file_id>/export/jsonl', methods=['GET'])
def export_jsonl(file_id: int):
    file_obj = _get_graph_file(file_id)
    _authorize_read(file_obj)
    workspace = ensure_workspace(file_obj, file_obj.owner_id, file_obj.folder_id, create_if_missing=False)
    if not workspace:
        abort(404)
    payload = jsonl_export(workspace)
    return Response(payload, mimetype='text/plain')
