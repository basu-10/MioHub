"""
File routes for universal File model.

Handles CRUD operations for markdown, PDFs, todos, diagrams, and other file types
stored in the new 'files' table. Coexists with legacy Note/Board routes.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, current_app
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
import json

from .models import File, Folder, User
from extensions import db
from .utils import save_data_uri_images_for_user, cleanup_orphaned_images_for_user, collect_images_from_content
from .graph_service import ensure_workspace
from utilities_main import update_user_data_size, calculate_content_size
from . import file_bp


def _default_todo_title_if_blank(title: str) -> str:
    """Return a datetime-based title when a todo title is missing/blank."""
    normalized = (title or '').strip()
    if normalized:
        return normalized
    # Match the UI's intent: a simple local datetime stamp.
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{(size_bytes / 1024):.1f}KB"
    else:
        return f"{(size_bytes / (1024 * 1024)):.1f}MB"


@file_bp.route('/files/new/<file_type>', methods=['GET', 'POST'])
@login_required
def new_file(file_type):
    """
    Create a new file of specified type with default values and redirect to edit.
    Supported types: markdown, code, todo, diagram, note, whiteboard, table, blocks, proprietary_graph, timeline
    """
    # Allow callers (e.g., Graph Workspace) to explicitly target a folder.
    # This is validated against current_user and then persisted to session to
    # keep behavior consistent with existing flows.
    folder_override_id = (
        request.args.get('folder_id', type=int)
        or request.form.get('folder_id', type=int)
    )

    current_folder_id = session.get('current_folder_id')

    if folder_override_id:
        override_folder = Folder.query.filter_by(id=folder_override_id, user_id=current_user.id).first()
        if override_folder:
            current_folder_id = folder_override_id
            session['current_folder_id'] = current_folder_id
    
    # Ensure user has a root folder
    if not current_folder_id:
        current_folder = Folder.query.filter_by(user_id=current_user.id, parent_id=None).first()
        if current_folder:
            current_folder_id = current_folder.id
            session['current_folder_id'] = current_folder_id
        else:
            from blueprints.p2.utils import add_notification
            add_notification(current_user.id, "Error: No root folder found. Please contact support.", 'error')
            return redirect(url_for('folders.view_folder'))
    
    # Validate folder ownership
    folder = Folder.query.filter_by(id=current_folder_id, user_id=current_user.id).first()
    if not folder:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Error: Invalid folder", 'error')
        return redirect(url_for('folders.view_folder'))
    
    # GET request - create file with defaults and redirect to edit template
    if request.method == 'GET':
        # Default title is current datetime
        default_title = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        default_description = ''
        
        # Create new file with type-specific defaults
        new_file = File(
            owner_id=current_user.id,
            folder_id=current_folder_id,
            type=file_type,
            title=default_title,
            is_public=False,
            metadata_json={"description": default_description}
        )
        
        # Initialize content based on type
        if file_type == 'markdown':
            new_file.content_text = ''
            
        elif file_type == 'code':
            new_file.content_text = ''
            new_file.metadata_json['language'] = 'plaintext'
            
        elif file_type == 'todo':
            new_file.content_json = {'items': []}
            
        elif file_type == 'diagram':
            new_file.content_json = {}
            
        elif file_type == 'table':
            # Default Luckysheet sheet
            new_file.content_json = [{
                "name": "Sheet1",
                "color": "",
                "status": 1,
                "order": 0,
                "data": [
                    ["Column A", "Column B", "Column C"],
                    ["", "", ""]
                ],
                "config": {},
                "index": 0
            }]
            
        elif file_type == 'blocks':
            # Default Editor.js state
            new_file.content_json = {
                "root": {
                    "children": [
                        {
                            "children": [],
                            "direction": None,
                            "format": "",
                            "indent": 0,
                            "type": "paragraph",
                            "version": 1
                        }
                    ],
                    "direction": None,
                    "format": "",
                    "indent": 0,
                    "type": "root",
                    "version": 1
                }
            }
            
        elif file_type == 'proprietary_graph':
            new_file.content_json = {
                'nodes': [],
                'edges': [],
                'settings': {},
                'metadata': {}
            }
            
        elif file_type == 'timeline':
            new_file.content_json = []
            
        elif file_type == 'whiteboard':
            new_file.content_json = {}
            
        else:
            from blueprints.p2.utils import add_notification
            add_notification(current_user.id, f"Error: Unsupported file type '{file_type}'", 'error')
            return redirect(url_for('folders.view_folder'))
        
        flag_modified(new_file, 'metadata_json')
        
        try:
            db.session.add(new_file)
            db.session.flush()
            
            if file_type == 'proprietary_graph':
                ensure_workspace(new_file, current_user.id, current_folder_id)
            
            # Update folder last_modified
            folder.last_modified = datetime.utcnow()
            db.session.commit()
            
            # Calculate and update storage (minimal for empty file)
            content_size = new_file.get_content_size()
            update_user_data_size(current_user, content_size)
            
            # Redirect to edit template with new flag
            if file_type == 'proprietary_graph':
                return redirect(url_for('graph.view_graph', file_id=new_file.id, is_new=1))
            else:
                return redirect(url_for('file.edit_file', file_id=new_file.id, is_new=1))
                
        except SQLAlchemyError as e:
            db.session.rollback()
            from blueprints.p2.utils import add_notification
            add_notification(current_user.id, f"Error creating {file_type}: {str(e)}", 'error')
            return redirect(url_for('folders.view_folder'))
    
    # POST request - this is now handled by edit_file route
    # This should not be reached, but redirect to folder view as fallback
    return redirect(url_for('folders.view_folder', folder_id=current_folder_id))


@file_bp.route('/files/<int:file_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_file(file_id):
    """Edit an existing file."""
    file_obj = File.query.get(file_id)

    if current_app.config.get('TESTING'):
        print(f"[edit_file] testing request user={getattr(current_user, 'id', None)} owner={getattr(file_obj, 'owner_id', None)} file_id={file_id}")

    # In tests, current_user may be disabled; fallback to session user id for ownership checks
    request_user_id = current_user.id if current_user.is_authenticated else session.get('_user_id')

    if not file_obj or (request_user_id is None) or (file_obj.owner_id != int(request_user_id)):
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "File not found or unauthorized", 'error')
        target_folder_id = getattr(file_obj, 'folder_id', None) or session.get('current_folder_id') or 0
        return redirect(url_for('folders.view_folder', folder_id=target_folder_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if file_obj.type == 'todo':
            title = _default_todo_title_if_blank(title)
        file_obj.title = title
        description = request.form.get('description', '').strip()
        file_obj.is_public = request.form.get('is_public') == 'on'

        # Ensure metadata_json is always a dict and keep description optional
        if file_obj.metadata_json is None or not isinstance(file_obj.metadata_json, dict):
            file_obj.metadata_json = {}

        if description:
            file_obj.metadata_json['description'] = description
        else:
            file_obj.metadata_json.pop('description', None)

        flag_modified(file_obj, 'metadata_json')
        
        # Handle content updates based on type
        old_size = file_obj.get_content_size()
        
        if file_obj.type == 'markdown':
            file_obj.content_text = request.form.get('content', '')
            
        elif file_obj.type == 'code':
            # Update code content and language
            file_obj.content_text = request.form.get('content', '')
            language = request.form.get('language', 'plaintext')
            
            if not file_obj.metadata_json:
                file_obj.metadata_json = {}
            file_obj.metadata_json['language'] = language
            if description:
                file_obj.metadata_json['description'] = description
            flag_modified(file_obj, 'metadata_json')
            
        elif file_obj.type == 'todo':
            try:
                # Frontend sends {items: [...]} structure
                content_str = request.form.get('content', '{}')
                print(f"DEBUG: Received content string: {content_str[:200]}")  # Log first 200 chars
                
                content_data = json.loads(content_str)
                print(f"DEBUG: Parsed content_data type: {type(content_data)}, value: {content_data}")
                
                if isinstance(content_data, dict) and 'items' in content_data:
                    # Already in correct format
                    file_obj.content_json = content_data
                elif isinstance(content_data, list):
                    # Legacy format - wrap in items object
                    file_obj.content_json = {'items': list(content_data)}
                else:
                    file_obj.content_json = {'items': []}

                # Ensure SQLAlchemy picks up JSON changes and flush immediately for size calc/tests
                flag_modified(file_obj, 'content_json')
                db.session.flush()
            except json.JSONDecodeError as e:
                print(f"DEBUG: JSONDecodeError - {e}")
                print(f"DEBUG: Content that failed: {request.form.get('content', 'EMPTY')}")
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, f"Error: Invalid todo data format. {str(e)}", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': f'Invalid todo data format: {str(e)}'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
            except Exception as e:
                print(f"DEBUG: Unexpected error - {type(e).__name__}: {e}")
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, f"Error saving todo: {str(e)}", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': f'Error saving todo: {str(e)}'}), 500
                return redirect(url_for('file.edit_file', file_id=file_id))
                
        elif file_obj.type == 'blocks':
            try:
                blocks_data = json.loads(request.form.get('content', '{}'))
                file_obj.content_json = blocks_data
                flag_modified(file_obj, 'content_json')
            except json.JSONDecodeError as e:
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, "Error: Invalid blocks data format", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Invalid blocks data format'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
            
        elif file_obj.type == 'diagram':
            try:
                diagram_data = json.loads(request.form.get('content', '{}'))
                file_obj.content_json = diagram_data
                flag_modified(file_obj, 'content_json')
            except json.JSONDecodeError as e:
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, "Error: Invalid diagram data format", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Invalid diagram data format'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
            
        elif file_obj.type == 'whiteboard':
            try:
                canvas_data = json.loads(request.form.get('content', '{}'))
                file_obj.content_json = canvas_data
                flag_modified(file_obj, 'content_json')
            except json.JSONDecodeError as e:
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, "Error: Invalid canvas data format", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Invalid canvas data format'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
                
        elif file_obj.type == 'table':
            try:
                table_data = json.loads(request.form.get('content', '[]'))
                # Ensure it's in Luckysheet format (array of sheets)
                if isinstance(table_data, list) and len(table_data) > 0:
                    file_obj.content_json = table_data
                else:
                    # If not valid, create default sheet
                    file_obj.content_json = [{
                        "name": "Sheet1",
                        "color": "",
                        "status": 1,
                        "order": 0,
                        "data": [[""]],
                        "config": {},
                        "index": 0
                    }]
                flag_modified(file_obj, 'content_json')
            except json.JSONDecodeError as e:
                print(f"DEBUG: Table JSONDecodeError - {e}")
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, "Error: Invalid table data format", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Invalid table data format'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
            except Exception as e:
                print(f"DEBUG: Table error - {type(e).__name__}: {e}")
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, f"Error saving table: {str(e)}", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': f'Error saving table: {str(e)}'}), 500
                return redirect(url_for('file.edit_file', file_id=file_id))
        
        elif file_obj.type == 'timeline':
            try:
                timeline_data = json.loads(request.form.get('content_json', '[]'))
                if not isinstance(timeline_data, list):
                    timeline_data = []
                file_obj.content_json = timeline_data
                flag_modified(file_obj, 'content_json')
            except json.JSONDecodeError as e:
                from blueprints.p2.utils import add_notification
                add_notification(current_user.id, "Error: Invalid timeline data format", 'error')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': 'Invalid timeline data format'}), 400
                return redirect(url_for('file.edit_file', file_id=file_id))
        
        # Update storage quota
        new_size = file_obj.get_content_size()
        size_delta = new_size - old_size
        update_user_data_size(current_user, size_delta)
        
        # Update last_modified timestamp
        file_obj.last_modified = datetime.utcnow()
        
        try:
            db.session.commit()
            
            # Add notification for successful save
            from blueprints.p2.utils import add_notification
            size_str = format_file_size(new_size)
            notification_msg = f"Saved {file_obj.type}: {file_obj.title} ({size_str})"
            add_notification(current_user.id, notification_msg, 'save')

            # Avoid stale instances in the scoped session (tests query immediately after)
            db.session.expire_all()
            
            # No flash message - use telemetry panel notification via query param
            
            # Check if this is an AJAX request (return JSON instead of redirect)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'File saved successfully',
                    'size': size_str,
                    'file_type': file_obj.type,
                    'last_modified': file_obj.last_modified.isoformat()
                })
            
            if file_obj.type in ['todo', 'timeline']:
                # Stay on the edit page for these types so the user does not lose context
                return redirect(url_for('file.edit_file', file_id=file_obj.id, saved=file_obj.type, size=size_str))
            return redirect(url_for('folders.view_folder', folder_id=file_obj.folder_id, saved=file_obj.type, size=size_str))
        except SQLAlchemyError as e:
            db.session.rollback()
            add_notification(current_user.id, f"Error updating file: {str(e)}", 'error')
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': f"Error updating file: {str(e)}"
                }), 500
            return redirect(url_for('file.edit_file', file_id=file_id))
    
    # GET request - show edit form
    # Special case: redirect infinite whiteboards to their dedicated route
    if file_obj.type == 'proprietary_infinite_whiteboard':
        return redirect(url_for('infinite_boards.edit_infinite_board', board_id=file_obj.id))
    
    return render_template(f'p2/file_edit_{file_obj.type}.html', file=file_obj)


@file_bp.route('/files/<int:file_id>/delete', methods=['POST'])
@login_required
def delete_file(file_id):
    """Delete a file."""
    file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()
    
    if not file_obj:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "File not found or unauthorized", 'error')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
        if is_ajax:
            return jsonify({'success': False, 'message': 'File not found or unauthorized'}), 404
        return redirect(url_for('folders.view_folder'))
    
    folder_id = file_obj.folder_id
    file_title = file_obj.title
    content_size = file_obj.get_content_size()
    
    try:
        db.session.delete(file_obj)
        db.session.commit()
        
        # Update storage quota
        update_user_data_size(current_user, -content_size)
        
        # Add notification for deletion
        from blueprints.p2.utils import add_notification
        notif_msg = f"Deleted {file_obj.type} '{file_title}'"
        add_notification(current_user.id, notif_msg, 'delete')
        
        # Clean up orphaned images for HTML-based files (not note files anymore)
        if file_obj.type in ['diagram'] and file_obj.content_html:
            try:
                deleted_count, freed_bytes = cleanup_orphaned_images_for_user(current_user.id)
                if deleted_count > 0:
                    print(f"[DELETE FILE] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
            except Exception as e:
                print(f"[DELETE FILE] Image cleanup failed: {e}")
        
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
        if is_ajax:
            return jsonify({'success': True, 'message': f"Deleted {file_obj.type} '{file_title}'"})
        
        # Notification already added for deletion above
        # No flash message needed
        pass
    except SQLAlchemyError as e:
        db.session.rollback()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, f"Error deleting file: {str(e)}", 'error')
        if is_ajax:
            return jsonify({'success': False, 'message': f'Error deleting file: {str(e)}'}), 500
    
    return redirect(url_for('folders.view_folder', folder_id=folder_id))


@file_bp.route('/files/<int:file_id>/view')
@login_required
def view_file(file_id):
    """View a file (read-only)."""
    file_obj = File.query.filter_by(id=file_id).first()
    
    if not file_obj:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "File not found", 'error')
        return redirect(url_for('folders.view_folder'))
    
    # Check access permissions
    if file_obj.owner_id != current_user.id and not file_obj.is_public:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "You don't have permission to view this file", 'error')
        return redirect(url_for('folders.view_folder'))
    
    # MioBooks use the combined print view template
    if file_obj.type == 'proprietary_blocks':
        return redirect(url_for('combined.print_view', document_id=file_obj.id))
    
    # Infinite whiteboards use their dedicated view route
    if file_obj.type == 'proprietary_infinite_whiteboard':
        return redirect(url_for('infinite_boards.view_infinite_board', board_id=file_obj.id))
    
    return render_template(f'p2/file_view_{file_obj.type}.html', file=file_obj)


@file_bp.route('/public/file/<int:file_id>')
def public_file(file_id):
    """Public view of a file (no login required)."""
    file_obj = File.query.filter_by(id=file_id, is_public=True).first()
    
    if not file_obj:
        # No notification for anonymous users viewing public files
        return redirect(url_for('core.index'))
    
    # MioBooks (type='proprietary_blocks') need special handling for public view
    if file_obj.type == 'proprietary_blocks':
        # Render combined print view with public context
        content_blocks = file_obj.content_json if file_obj.content_json else []
        if not isinstance(content_blocks, list):
            content_blocks = []
        return render_template('p2/miobook_print_view.html', 
                             document=file_obj,
                             content_blocks=content_blocks,
                             public_view=True)
    
    return render_template(f'p2/file_view_{file_obj.type}.html', file=file_obj, public_view=True)


@file_bp.route('/api/files/<int:file_id>/content', methods=['GET'])
@login_required
def get_file_content(file_id):
    """API endpoint to get file content as JSON."""
    file_obj = File.query.filter_by(id=file_id).first()
    
    if not file_obj:
        return jsonify({"error": "File not found"}), 404
    
    # Check access
    if file_obj.owner_id != current_user.id and not file_obj.is_public:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Return all content fields separately for download functionality
    return jsonify({
        "id": file_obj.id,
        "type": file_obj.type,
        "title": file_obj.title,
        "content_text": file_obj.content_text,
        "content_html": file_obj.content_html,
        "content_json": file_obj.content_json,
        "metadata_json": file_obj.metadata_json,
        "created_at": file_obj.created_at.isoformat() if file_obj.created_at else None,
        "last_modified": file_obj.last_modified.isoformat() if file_obj.last_modified else None
    })


@file_bp.route('/files/<int:file_id>/move', methods=['POST'])
@login_required
def move_file(file_id):
    """Move a file to a different folder."""
    from blueprints.p2.utils import add_notification
    
    file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()
    
    if not file_obj:
        from blueprints.p2.utils import add_notification
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            add_notification(current_user.id, "File not found or unauthorized", 'error')
            return jsonify({'success': False, 'message': 'File not found or unauthorized'}), 403
        return redirect(url_for('folders.view_folder'))
    
    target_folder_id = request.form.get('target_folder')
    target_folder = Folder.query.filter_by(id=target_folder_id, user_id=current_user.id).first()
    
    if not target_folder:
        add_notification(current_user.id, "Invalid target folder", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid target folder'}), 400
        return redirect(request.referrer or url_for('folders.view_folder'))
    
    old_folder_name = file_obj.folder.name if file_obj.folder else 'root'
    file_obj.folder_id = target_folder.id
    file_obj.last_modified = datetime.utcnow()
    
    try:
        db.session.commit()
        
        # Add notification
        notif_msg = f"Moved {file_obj.type} '{file_obj.title}' from '{old_folder_name}' to '{target_folder.name}'"
        add_notification(current_user.id, notif_msg, 'transfer')
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': f"Moved {file_obj.type} '{file_obj.title}' to '{target_folder.name}'",
                'file': {
                    'id': file_obj.id,
                    'title': file_obj.title,
                    'type': 'file',
                    'file_type': file_obj.type
                }
            })
        
        # Notification already added above for move
        return redirect(request.referrer or url_for('folders.view_folder'))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, f"Error moving file: {str(e)}", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Error moving file: {str(e)}'}), 500
        return redirect(request.referrer or url_for('folders.view_folder'))


@file_bp.route('/files/<int:file_id>/duplicate', methods=['POST'])
@login_required
def duplicate_file(file_id):
    """Duplicate/copy a file to a target folder."""
    from blueprints.p2.utils import add_notification
    
    original = File.query.filter_by(id=file_id, owner_id=current_user.id).first()
    
    if not original:
        add_notification(current_user.id, "File not found or unauthorized", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'File not found or unauthorized'}), 403
        return redirect(url_for('folders.view_folder'))
    
    target_folder_id = request.form.get('target_folder')
    target_folder = Folder.query.filter_by(id=target_folder_id, user_id=current_user.id).first()
    
    if not target_folder:
        add_notification(current_user.id, "Invalid target folder", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid target folder'}), 400
        return redirect(request.referrer or url_for('folders.view_folder'))
    
    # Create duplicate
    new_title = original.title + " (copy)"
    duplicate = File(
        owner_id=current_user.id,
        folder_id=target_folder.id,
        type=original.type,
        title=new_title,
        content_text=original.content_text,
        content_html=original.content_html,
        content_json=original.content_json,
        content_blob=original.content_blob,
        metadata_json=original.metadata_json.copy() if original.metadata_json else {},
        is_public=False  # Copies are private by default
    )
    
    # Calculate size and check quota
    content_size = duplicate.get_content_size()
    
    if current_user.user_type == 'guest':
        GUEST_LIMIT = 50 * 1024 * 1024  # 50MB
        if (current_user.total_data_size or 0) + content_size > GUEST_LIMIT:
            add_notification(current_user.id, "Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", 'error')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Data limit exceeded (50MB max for guests)'}), 400
            return redirect(request.referrer or url_for('folders.view_folder'))
    
    try:
        db.session.add(duplicate)
        db.session.commit()
        
        # Update user data size
        update_user_data_size(current_user, content_size)
        
        # Add notification
        size_str = format_file_size(content_size)
        notif_msg = f"Duplicated {original.type} '{original.title}' to '{target_folder.name}' ({size_str})"
        add_notification(current_user.id, notif_msg, 'transfer')
        
        # Return JSON for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response_data = {
                'success': True,
                'message': f"Duplicated {original.type} as '{new_title}'",
                'file': {
                    'id': duplicate.id,
                    'title': duplicate.title,
                    'type': 'file',
                    'file_type': duplicate.type
                }
            }
            
            # HTMX support: return HTML fragment for dynamic insertion
            if request.form.get('htmx') == 'true':
                display_prefs = current_user.user_prefs.get('display', {}) if current_user.user_prefs else {
                    'view_mode': 'grid',
                    'columns': 3,
                    'card_size': 'normal',
                    'show_previews': True
                }
                
                new_item_html = render_template(
                    'p2/partials/file_card.html',
                    file=duplicate,
                    display_prefs=display_prefs
                )
                
                response_data['new_item_html'] = new_item_html
                response_data['new_item_id'] = duplicate.id
                response_data['item_type'] = duplicate.type  # markdown, todo, diagram, etc.
            
            return jsonify(response_data)
        
        # Notification already added above
        return redirect(request.referrer or url_for('folders.view_folder'))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        add_notification(current_user.id, f"Error duplicating file: {str(e)}", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Error duplicating file: {str(e)}'}), 500
        return redirect(request.referrer or url_for('folders.view_folder'))


@file_bp.route('/files/<int:file_id>/rename', methods=['POST'])
@login_required
def rename_file(file_id):
    """Rename a file."""
    file_obj = File.query.filter_by(id=file_id, owner_id=current_user.id).first()
    
    if not file_obj:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "File not found or unauthorized", 'error')
        if request.content_type == 'application/x-www-form-urlencoded' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'File not found or unauthorized'}), 403
        return redirect(url_for('folders.view_folder'))
    
    new_title = request.form.get('new_name') or request.form.get('title', '').strip()
    new_description = request.form.get('description', '').strip()
    
    if not new_title:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "File title cannot be empty", 'error')
        if request.content_type == 'application/x-www-form-urlencoded' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'File title cannot be empty'}), 400
        return redirect(request.referrer or url_for('folders.view_folder'))
    
    old_title = file_obj.title
    file_obj.title = new_title
    
    # Update description in metadata_json
    if not file_obj.metadata_json:
        file_obj.metadata_json = {}
    file_obj.metadata_json['description'] = new_description
    flag_modified(file_obj, 'metadata_json')
    
    file_obj.last_modified = datetime.utcnow()
    
    try:
        db.session.commit()
        
        # Add notification for rename if title changed
        if new_title != old_title:
            from blueprints.p2.utils import add_notification
            notif_msg = f"Renamed {file_obj.type} '{old_title}' to '{new_title}'"
            add_notification(current_user.id, notif_msg, 'info')
        
        if request.content_type == 'application/x-www-form-urlencoded' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': f'{file_obj.type.capitalize()} renamed successfully'})
        
        # Notification already added above for rename
        return redirect(request.referrer or url_for('folders.view_folder'))
        
    except SQLAlchemyError as e:
        db.session.rollback()
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, f"Error renaming file: {str(e)}", 'error')
        if request.content_type == 'application/x-www-form-urlencoded' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Error renaming file: {str(e)}'}), 500
        return redirect(request.referrer or url_for('folders.view_folder'))
