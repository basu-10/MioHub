#folder ops - UPDATED FOR FILE MODEL MIGRATION

from blueprints.p2.models import Folder, File, db, User, GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment
from flask_login import current_user
from .utils import collect_images_from_content, copy_images_to_user, save_data_uri_images_for_user
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import SQLAlchemyError
import re
import json

def create_folder(name, parent_id=None, description=None, is_root=False):
    """Create a new folder with optional description."""
    if is_root:
        # Prevent duplicate roots per user
        existing_root = Folder.query.filter_by(user_id=current_user.id, is_root=True).first()
        if existing_root:
            return existing_root
        parent_id = None  # Root must not have a parent

    folder = Folder(
        name=name,
        user_id=current_user.id,
        parent_id=parent_id,
        description=description,
        is_root=is_root,
    )
    db.session.add(folder)
    db.session.commit()
    return folder

def rename_folder(folder_id, new_name, new_description=None):
    """Rename folder and optionally update description"""
    folder = Folder.query.get(folder_id)
    if folder and folder.user_id == current_user.id:
        folder.name = new_name
        if new_description is not None:
            folder.description = new_description
        db.session.commit()
        return True
    return False

def _delete_graph_workspace_for_file(file_id):
    """Delete graph workspace and dependents for a given graph file id."""
    if not file_id:
        return
    workspace = GraphWorkspace.query.filter_by(file_id=file_id).first()
    if not workspace:
        return

    # Delete node attachments tied to this graph
    node_ids = [node.id for node in workspace.nodes]
    if node_ids:
        GraphNodeAttachment.query.filter(GraphNodeAttachment.node_id.in_(node_ids)).delete(synchronize_session=False)

    # Delete edges and nodes, then workspace
    GraphEdge.query.filter_by(graph_id=workspace.id).delete(synchronize_session=False)
    GraphNode.query.filter_by(graph_id=workspace.id).delete(synchronize_session=False)
    db.session.delete(workspace)


def _delete_graph_references_for_folder(folder_id):
    """Remove graph attachments/workspaces that directly reference a folder."""
    if not folder_id:
        return

    # Attachments pointing to this folder
    GraphNodeAttachment.query.filter_by(folder_id=folder_id).delete(synchronize_session=False)

    # Any workspaces explicitly linked to this folder
    workspaces = GraphWorkspace.query.filter_by(folder_id=folder_id).all()
    for ws in workspaces:
        _delete_graph_workspace_for_file(ws.file_id)
        db.session.delete(ws)


def delete_file_with_graph_cleanup(file_obj):
    """Delete a File after cleaning graph references and chat attachments."""
    if not file_obj:
        return

    # Remove graph attachments referencing this file
    GraphNodeAttachment.query.filter_by(file_id=file_obj.id).delete(synchronize_session=False)

    # If this is a graph file, drop its workspace hierarchy
    if file_obj.type == 'proprietary_graph':
        _delete_graph_workspace_for_file(file_obj.id)

    # Remove chat attachments that reference this file to satisfy FK constraints
    try:
        from blueprints.p3.models import ChatAttachment

        attachments = ChatAttachment.query.filter_by(file_id=file_obj.id).all()
        for attachment in attachments:
            db.session.delete(attachment)

        # Clear any summaries that point at this file
        ChatAttachment.query.filter_by(summary_file_id=file_obj.id).update({"summary_file_id": None})
    except Exception as exc:
        print(f"[DELETE FILE] Failed to clean chat attachments for file {file_obj.id}: {exc}")

    db.session.delete(file_obj)


def delete_folder(folder_id, *, acting_user=None, with_reason=False):
    """Delete folder and all its contents (files and subfolders).

    When with_reason=True, returns (success: bool, reason: str).
    """
    folder = Folder.query.get(folder_id)
    if acting_user:
        actor = acting_user
    else:
        actor = current_user
        if hasattr(current_user, '_get_current_object'):
            try:
                actor = current_user._get_current_object()
            except Exception:
                actor = current_user

    reason = None
    if not folder:
        reason = 'folder not found'
        result = False
    elif folder.is_root:
        reason = 'cannot delete root folder'
        result = False
    elif not actor or (folder.user_id != getattr(actor, 'id', None) and not getattr(actor, 'is_admin', False)):
        reason = 'unauthorized'
        result = False
    else:
        try:
            def delete_recursive(f):
                # Clean graph references pointing to this folder
                _delete_graph_references_for_folder(f.id)

                # Delete all files in this folder (unified delete with graph/chat cleanup)
                files_in_folder = File.query.filter_by(folder_id=f.id).all()
                for file_obj in files_in_folder:
                    delete_file_with_graph_cleanup(file_obj)

                # Recursively delete all subfolders
                for child in f.children:
                    delete_recursive(child)

                db.session.delete(f)

            delete_recursive(folder)
            db.session.commit()
            result = True
        except SQLAlchemyError as exc:
            db.session.rollback()
            reason = f'database error: {exc}'
            result = False
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            reason = f'error: {exc}'
            result = False

    if with_reason:
        return result, reason
    return result


# build and pass the breadcrumb
def build_folder_breadcrumb(folder):
    """Return list of folders from root -> ... -> current folder."""
    chain = []
    f = folder
    while f is not None:
        chain.append(f)
        f = f.parent  # assumes Folder.parent relationship
    chain.reverse()
    return chain

def move_folder(folder_id, target_parent_id):
    folder = Folder.query.get(folder_id)
    target_parent = Folder.query.get(target_parent_id)

    if (
        folder and folder.user_id == current_user.id
        and target_parent and target_parent.user_id == current_user.id
        and folder.id != target_parent_id  # prevent self-parenting
        and not folder.is_root  # root folder must stay at top
    ):
        folder.parent_id = target_parent_id
        db.session.commit()
        return True
    return False



def copy_folder_recursive(original_folder_id, target_parent_id, allow_external=False):
    """Recursively copy a folder with all File contents.
    By default only allows copying folders owned by current_user.
    If allow_external is True, allows copying other users' public folders into current_user's tree.
    Cross-user copies preserve original titles (no " (copy)" suffix) while same-user copies keep the suffix.
    Returns the cloned root Folder instance on success, or None on failure.
    """
    original = Folder.query.get(original_folder_id)
    if not original:
        return None
    if not allow_external and original.user_id != current_user.id:
        return None

    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    # Cross-user copies should keep titles unchanged; local duplicates keep " (copy)" to avoid collisions
    append_copy_suffix = not allow_external

    # Track visited folders to prevent infinite recursion from circular references
    visited = set()

    def clone_folder(folder, new_parent_id, depth=0):
        # Prevent circular references and excessive depth
        if folder.id in visited:
            print(f"WARNING: Circular reference detected for folder {folder.id} '{folder.name}'")
            return None
        if depth > 100:  # Maximum nesting depth
            print(f"WARNING: Maximum folder depth (100) exceeded for folder {folder.id} '{folder.name}'")
            return None
        
        visited.add(folder.id)
        
        # Folder.name column is String(100)
        new_folder_name = truncate((folder.name or '') + (' (copy)' if append_copy_suffix else ''), 100)
        # Preserve folder description when copying (truncate to column length)
        new_folder_description = truncate(folder.description, 500) if getattr(folder, 'description', None) else None
        new_folder = Folder(name=new_folder_name, user_id=current_user.id, parent_id=new_parent_id, description=new_folder_description)
        db.session.add(new_folder)
        db.session.flush()  # get new_folder.id

        # Copy all files in this folder (unified approach)
        files = File.query.filter_by(folder_id=folder.id).all()
        for file_obj in files:
            # Clone file with (copy) suffix
            new_file = File(
                owner_id=current_user.id,
                folder_id=new_folder.id,
                type=file_obj.type,
                title=truncate((file_obj.title or '') + (' (copy)' if append_copy_suffix else ''), 500),
                content_text=file_obj.content_text,
                content_html=file_obj.content_html,
                content_json=file_obj.content_json.copy() if file_obj.content_json else None,
                content_blob=file_obj.content_blob,
                metadata_json=file_obj.metadata_json.copy() if file_obj.metadata_json else {},
                is_public=False  # Don't copy public flag when duplicating
            )
            db.session.add(new_file)

        # Recurse into children
        for sub in folder.children:
            clone_folder(sub, new_folder.id, depth + 1)

        return new_folder

    cloned_root = clone_folder(original, target_parent_id)
    db.session.commit()
    return cloned_root


def _sanitize_username_for_folder(username):
    """Sanitize username to be safe in folder name: lowercase, replace non-alnum with underscore"""
    if not username:
        return 'unknown'
    s = username.strip().lower()
    s = re.sub(r'[^a-z0-9_\-]', '_', s)
    return s


def get_or_create_folder_path(user_id, segments):
    """Ensure that a nested path exists for a given user and return the final folder id.

    Example: segments=['social','received','from_alice'] -> ensures root/social/received/from_alice exist and returns the id for 'from_alice'
    """
    if not segments:
        return None
    # find the user's root folder; create one if it does not exist
    root = Folder.query.filter_by(user_id=user_id, is_root=True).first()
    if not root:
        # Fall back to parentless folder if older data lacks is_root, otherwise create one
        root = Folder.query.filter_by(user_id=user_id, parent_id=None).first()
    if not root:
        root = Folder(name='root', user_id=user_id, parent_id=None, is_root=True)
        db.session.add(root)
        db.session.flush()

    parent = root
    for seg in segments:
        # try to find child with exact name
        child = Folder.query.filter_by(user_id=user_id, parent_id=parent.id, name=seg).first()
        if not child:
            child = Folder(name=seg, user_id=user_id, parent_id=parent.id)
            db.session.add(child)
            db.session.flush()
        parent = child
    db.session.commit()
    return parent.id


def copy_folder_to_user(original_folder_id, receiver_user_id, sender_username=None):
    """Copy a folder (and its File contents) from sender to receiver_user's folder tree 
    under root/social/received/from_<sender_username>
    Returns tuple: (cloned_folder, actual_bytes_written) or (None, 0) on failure
    """
    original = Folder.query.get(original_folder_id)
    if not original:
        return (None, 0)

    receiver = User.query.get(receiver_user_id)
    if not receiver:
        return (None, 0)

    # Get sender username from folder owner if not provided
    if not sender_username:
        sender_user = User.query.get(original.user_id)
        sender_username = sender_user.username if sender_user else 'unknown'

    # Build path segments
    sender_segment = 'from_' + _sanitize_username_for_folder(sender_username)
    segments = ['social', 'received', sender_segment]
    target_parent_id = get_or_create_folder_path(receiver_user_id, segments)
    if not target_parent_id:
        print(f"ERROR: copy_folder_to_user - failed to create/get folder path for receiver {receiver_user_id}")
        return (None, 0)

    # Track total bytes written
    total_bytes_written = 0

    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    def clone_folder_to_user(folder, new_parent_id):
        nonlocal total_bytes_written
        new_folder = Folder(
            name=truncate(folder.name, 100), 
            user_id=receiver_user_id, 
            parent_id=new_parent_id, 
            description=truncate(folder.description, 500) if getattr(folder, 'description', None) else None
        )
        db.session.add(new_folder)
        db.session.flush()

        # Copy all files (unified approach)
        files = File.query.filter_by(folder_id=folder.id).all()
        for file_obj in files:
            # Process content based on type
            new_content_text = file_obj.content_text
            new_content_html = file_obj.content_html
            new_content_json = None
            new_content_blob = file_obj.content_blob
            new_metadata = file_obj.metadata_json.copy() if file_obj.metadata_json else {}
            
            bytes_from_datauris = 0
            
            # Handle text/html content with images
            if new_content_text:
                new_content_text, added = save_data_uri_images_for_user(new_content_text, receiver_user_id)
                bytes_from_datauris += added
            
            if new_content_html:
                new_content_html, added = save_data_uri_images_for_user(new_content_html, receiver_user_id)
                bytes_from_datauris += added
            
            # Handle JSON content (boards, diagrams, etc.)
            if file_obj.content_json:
                # Convert to string for image processing
                json_str = json.dumps(file_obj.content_json)
                json_str, added = save_data_uri_images_for_user(json_str, receiver_user_id)
                bytes_from_datauris += added
                try:
                    new_content_json = json.loads(json_str)
                except:
                    new_content_json = file_obj.content_json.copy()
            
            # Handle metadata description field
            if new_metadata.get('description'):
                desc, added = save_data_uri_images_for_user(new_metadata['description'], receiver_user_id)
                new_metadata['description'] = desc
                bytes_from_datauris += added
            
            # Collect all image filenames from content
            image_filenames = set()
            for content in [new_content_text, new_content_html, json_str if new_content_json else None]:
                if content:
                    collect_images_from_content(content, image_filenames)
            
            if new_metadata.get('description'):
                collect_images_from_content(new_metadata['description'], image_filenames)
            
            # Copy images with deduplication
            mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
            
            # Replace filenames in all content fields
            if mapping:
                for old_fn, new_fn in mapping.items():
                    if new_content_text:
                        new_content_text = new_content_text.replace(old_fn, new_fn)
                    if new_content_html:
                        new_content_html = new_content_html.replace(old_fn, new_fn)
                    if new_content_json:
                        # Replace in JSON string representation
                        json_str = json.dumps(new_content_json)
                        json_str = json_str.replace(old_fn, new_fn)
                        try:
                            new_content_json = json.loads(json_str)
                        except:
                            pass  # Keep original if parsing fails
                    if new_metadata.get('description'):
                        new_metadata['description'] = new_metadata['description'].replace(old_fn, new_fn)
            
            # Calculate content bytes
            content_bytes = 0
            if new_content_text:
                content_bytes += len(new_content_text.encode('utf-8'))
            if new_content_html:
                content_bytes += len(new_content_html.encode('utf-8'))
            if new_content_json:
                content_bytes += len(json.dumps(new_content_json).encode('utf-8'))
            if new_content_blob:
                content_bytes += len(new_content_blob)
            
            total_bytes_written += content_bytes + bytes_from_datauris + image_bytes
            
            # Create new file
            new_file = File(
                owner_id=receiver_user_id,
                folder_id=new_folder.id,
                type=file_obj.type,
                title=truncate(file_obj.title, 500),
                content_text=new_content_text,
                content_html=new_content_html,
                content_json=new_content_json,
                content_blob=new_content_blob,
                metadata_json=new_metadata,
                is_public=False  # Don't copy public flag
            )
            db.session.add(new_file)
            db.session.flush()  # Flush to get ID
            
            # CRITICAL: Copy graph structure if this is a graph file
            if file_obj.type == 'proprietary_graph':
                from blueprints.p2.models import GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment
                
                # Get original graph workspace
                original_workspace = GraphWorkspace.query.filter_by(file_id=file_obj.id).first()
                if original_workspace:
                    # Create new graph workspace for receiver
                    new_workspace = GraphWorkspace(
                        file_id=new_file.id,
                        owner_id=receiver_user_id,
                        folder_id=new_folder.id,
                        settings_json=original_workspace.settings_json.copy() if original_workspace.settings_json else {},
                        metadata_json=original_workspace.metadata_json.copy() if original_workspace.metadata_json else {}
                    )
                    db.session.add(new_workspace)
                    db.session.flush()  # Get workspace ID
                    
                    # Copy nodes and build ID mapping
                    node_id_mapping = {}  # old_node_id -> new_node_id
                    original_nodes = GraphNode.query.filter_by(graph_id=original_workspace.id).all()
                    for original_node in original_nodes:
                        new_node = GraphNode(
                            graph_id=new_workspace.id,
                            title=original_node.title,
                            summary=original_node.summary,
                            position_json=original_node.position_json.copy() if original_node.position_json else {},
                            size_json=original_node.size_json.copy() if original_node.size_json else {},
                            style_json=original_node.style_json.copy() if original_node.style_json else {},
                            metadata_json=original_node.metadata_json.copy() if original_node.metadata_json else {}
                        )
                        db.session.add(new_node)
                        db.session.flush()  # Get new node ID
                        node_id_mapping[original_node.id] = new_node.id
                    
                    # Copy edges (updating node references)
                    original_edges = GraphEdge.query.filter_by(graph_id=original_workspace.id).all()
                    for original_edge in original_edges:
                        # Only copy edge if both nodes were copied
                        if original_edge.source_node_id in node_id_mapping and original_edge.target_node_id in node_id_mapping:
                            new_edge = GraphEdge(
                                graph_id=new_workspace.id,
                                source_node_id=node_id_mapping[original_edge.source_node_id],
                                target_node_id=node_id_mapping[original_edge.target_node_id],
                                label=original_edge.label,
                                edge_type=original_edge.edge_type,
                                metadata_json=original_edge.metadata_json.copy() if original_edge.metadata_json else {}
                            )
                            db.session.add(new_edge)
                    
                    # Copy attachments (updating node references)
                    original_attachments = db.session.query(GraphNodeAttachment).join(
                        GraphNode, GraphNodeAttachment.node_id == GraphNode.id
                    ).filter(GraphNode.graph_id == original_workspace.id).all()
                    
                    for original_attachment in original_attachments:
                        # Only copy attachment if node was copied
                        if original_attachment.node_id in node_id_mapping:
                            new_attachment = GraphNodeAttachment(
                                node_id=node_id_mapping[original_attachment.node_id],
                                attachment_type=original_attachment.attachment_type,
                                file_id=original_attachment.file_id,  # Keep reference to original file (not copied)
                                folder_id=original_attachment.folder_id,  # Keep reference to original folder (not copied)
                                url=original_attachment.url,
                                metadata_json=original_attachment.metadata_json.copy() if original_attachment.metadata_json else {}
                            )
                            db.session.add(new_attachment)
                    
                    print(f"DEBUG: copy_folder_to_user - copied graph structure for file {file_obj.id}: workspace {original_workspace.id} -> {new_workspace.id}, {len(node_id_mapping)} nodes, {len(original_edges)} edges, {len(original_attachments)} attachments")

        # Recurse into children
        for sub in folder.children:
            clone_folder_to_user(sub, new_folder.id)

        return new_folder

    cloned_root = clone_folder_to_user(original, target_parent_id)
    print(f"DEBUG: copy_folder_to_user - cloned folder {original_folder_id} to receiver {receiver_user_id} as folder {cloned_root.id if cloned_root else 'None'}, bytes={total_bytes_written}")
    return (cloned_root, total_bytes_written)


def copy_file_to_user(file_id, receiver_user_id, sender_username=None):
    """Copy a single file to receiver's path root/social/received/from_<sender> 
    Returns tuple (new_file, actual_bytes) or (None, 0) on failure
    
    This function replaces both copy_note_to_user and copy_board_to_user.
    """
    file_obj = File.query.get(file_id)
    if not file_obj:
        return (None, 0)
    
    receiver = User.query.get(receiver_user_id)
    if not receiver:
        return (None, 0)

    # Use provided sender_username or get from file owner
    if not sender_username:
        sender_user = User.query.get(file_obj.owner_id)
        sender_username = sender_user.username if sender_user else 'unknown'
    
    sender_segment = 'from_' + _sanitize_username_for_folder(sender_username)
    segments = ['social', 'received', sender_segment]
    target_parent_id = get_or_create_folder_path(receiver_user_id, segments)
    if not target_parent_id:
        print(f"ERROR: copy_file_to_user - failed to create/get folder path for receiver {receiver_user_id}")
        return (None, 0)

    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    total_bytes_written = 0
    
    # Initialize content variables
    new_content_text = file_obj.content_text
    new_content_html = file_obj.content_html
    new_content_json = None
    new_content_blob = file_obj.content_blob
    new_metadata = file_obj.metadata_json.copy() if file_obj.metadata_json else {}
    
    # Convert inline data URIs to receiver's upload folder
    bytes_from_datauris = 0
    
    if new_content_text:
        new_content_text, added = save_data_uri_images_for_user(new_content_text, receiver_user_id)
        bytes_from_datauris += added
        total_bytes_written += added
    
    if new_content_html:
        new_content_html, added = save_data_uri_images_for_user(new_content_html, receiver_user_id)
        bytes_from_datauris += added
        total_bytes_written += added
    
    if file_obj.content_json:
        json_str = json.dumps(file_obj.content_json)
        json_str, added = save_data_uri_images_for_user(json_str, receiver_user_id)
        bytes_from_datauris += added
        total_bytes_written += added
        try:
            new_content_json = json.loads(json_str)
        except:
            new_content_json = file_obj.content_json.copy()
    
    if new_metadata.get('description'):
        desc, added = save_data_uri_images_for_user(new_metadata['description'], receiver_user_id)
        new_metadata['description'] = desc
        bytes_from_datauris += added
        total_bytes_written += added
    
    # Collect image filenames
    image_filenames = set()
    for content in [new_content_text, new_content_html, json_str if new_content_json else None]:
        if content:
            collect_images_from_content(content, image_filenames)
    
    if new_metadata.get('description'):
        collect_images_from_content(new_metadata['description'], image_filenames)
    
    # Copy images with deduplication
    mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
    total_bytes_written += image_bytes
    
    print(f"DEBUG: copy_file_to_user - mapping for file {file_id} -> mapping: {mapping}, total_bytes={total_bytes_written}")
    
    # Replace filenames in content
    if mapping:
        for old_fn, new_fn in mapping.items():
            if new_content_text:
                new_content_text = new_content_text.replace(old_fn, new_fn)
            if new_content_html:
                new_content_html = new_content_html.replace(old_fn, new_fn)
            if new_content_json:
                json_str = json.dumps(new_content_json)
                json_str = json_str.replace(old_fn, new_fn)
                try:
                    new_content_json = json.loads(json_str)
                except:
                    pass
            if new_metadata.get('description'):
                new_metadata['description'] = new_metadata['description'].replace(old_fn, new_fn)
    
    # Calculate content bytes
    content_bytes = 0
    if new_content_text:
        content_bytes += len(new_content_text.encode('utf-8'))
    if new_content_html:
        content_bytes += len(new_content_html.encode('utf-8'))
    if new_content_json:
        content_bytes += len(json.dumps(new_content_json).encode('utf-8'))
    if new_content_blob:
        content_bytes += len(new_content_blob)
    
    total_bytes_written += content_bytes
    
    # Create new file
    new_file = File(
        owner_id=receiver_user_id,
        folder_id=target_parent_id,
        type=file_obj.type,
        title=truncate(file_obj.title, 500),
        content_text=new_content_text,
        content_html=new_content_html,
        content_json=new_content_json,
        content_blob=new_content_blob,
        metadata_json=new_metadata,
        is_public=False
    )
    
    db.session.add(new_file)
    db.session.flush()  # Flush to get ID but don't commit
    
    # CRITICAL: Copy graph structure if this is a graph file
    if file_obj.type == 'proprietary_graph':
        from blueprints.p2.models import GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment
        
        # Get original graph workspace
        original_workspace = GraphWorkspace.query.filter_by(file_id=file_id).first()
        if original_workspace:
            # Create new graph workspace for receiver
            new_workspace = GraphWorkspace(
                file_id=new_file.id,
                owner_id=receiver_user_id,
                folder_id=target_parent_id,
                settings_json=original_workspace.settings_json.copy() if original_workspace.settings_json else {},
                metadata_json=original_workspace.metadata_json.copy() if original_workspace.metadata_json else {}
            )
            db.session.add(new_workspace)
            db.session.flush()  # Get workspace ID
            
            # Copy nodes and build ID mapping
            node_id_mapping = {}  # old_node_id -> new_node_id
            original_nodes = GraphNode.query.filter_by(graph_id=original_workspace.id).all()
            for original_node in original_nodes:
                new_node = GraphNode(
                    graph_id=new_workspace.id,
                    title=original_node.title,
                    summary=original_node.summary,
                    position_json=original_node.position_json.copy() if original_node.position_json else {},
                    size_json=original_node.size_json.copy() if original_node.size_json else {},
                    style_json=original_node.style_json.copy() if original_node.style_json else {},
                    metadata_json=original_node.metadata_json.copy() if original_node.metadata_json else {}
                )
                db.session.add(new_node)
                db.session.flush()  # Get new node ID
                node_id_mapping[original_node.id] = new_node.id
            
            # Copy edges (updating node references)
            original_edges = GraphEdge.query.filter_by(graph_id=original_workspace.id).all()
            for original_edge in original_edges:
                # Only copy edge if both nodes were copied
                if original_edge.source_node_id in node_id_mapping and original_edge.target_node_id in node_id_mapping:
                    new_edge = GraphEdge(
                        graph_id=new_workspace.id,
                        source_node_id=node_id_mapping[original_edge.source_node_id],
                        target_node_id=node_id_mapping[original_edge.target_node_id],
                        label=original_edge.label,
                        edge_type=original_edge.edge_type,
                        metadata_json=original_edge.metadata_json.copy() if original_edge.metadata_json else {}
                    )
                    db.session.add(new_edge)
            
            # Copy attachments (updating node references)
            original_attachments = db.session.query(GraphNodeAttachment).join(
                GraphNode, GraphNodeAttachment.node_id == GraphNode.id
            ).filter(GraphNode.graph_id == original_workspace.id).all()
            
            for original_attachment in original_attachments:
                # Only copy attachment if node was copied
                if original_attachment.node_id in node_id_mapping:
                    new_attachment = GraphNodeAttachment(
                        node_id=node_id_mapping[original_attachment.node_id],
                        attachment_type=original_attachment.attachment_type,
                        file_id=original_attachment.file_id,  # Keep reference to original file (not copied)
                        folder_id=original_attachment.folder_id,  # Keep reference to original folder (not copied)
                        url=original_attachment.url,
                        metadata_json=original_attachment.metadata_json.copy() if original_attachment.metadata_json else {}
                    )
                    db.session.add(new_attachment)
            
            print(f"DEBUG: copy_file_to_user - copied graph structure: workspace {original_workspace.id} -> {new_workspace.id}, {len(node_id_mapping)} nodes, {len(original_edges)} edges, {len(original_attachments)} attachments")
    
    print(f"DEBUG: copy_file_to_user - created new file {new_file.id} for receiver {receiver_user_id}, bytes={total_bytes_written}")
    return (new_file, total_bytes_written)
