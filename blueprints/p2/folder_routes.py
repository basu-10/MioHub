#folder routes
from flask import Blueprint, request, redirect, url_for, flash, render_template, session, jsonify, current_app
from flask_login import login_required, current_user
from blueprints.p2.models import Folder, File, db, User
from blueprints.p3.models import ChatSession
from . import folder_bp  # Import the blueprint instance
from datetime import datetime
from sqlalchemy.orm import load_only
from sqlalchemy import or_, func, desc


from blueprints.p2.folder_ops import (
    create_folder,
    rename_folder,
    delete_folder,
    delete_file_with_graph_cleanup,
    build_folder_breadcrumb, copy_folder_recursive, move_folder,
    get_or_create_folder_path, copy_folder_to_user,
    copy_file_to_user
)
from blueprints.p2.utils import collect_images_from_content, get_image_hash, get_existing_image_by_hash, format_bytes
from utilities_main import update_user_data_size
from values_main import UPLOAD_FOLDER
import os
import json


RECENT_PAGE_SIZE = 5
RECENT_MAX_LIMIT = 30


def get_display_prefs(user):
    """Return a safe, default-filled display preferences dict for the user."""
    prefs = user.user_prefs if isinstance(getattr(user, 'user_prefs', None), dict) else {}
    display = dict(prefs.get('display', {}) or {})
    display.setdefault('columns', 3)
    display.setdefault('view_mode', 'grid')
    display.setdefault('card_size', 'normal')
    display.setdefault('show_previews', True)
    return display


def get_recent_items_for_user(owner_id, limit=RECENT_PAGE_SIZE, offset=0):
    """Return a slice of recently modified files for a user, ordered newest first."""
    safe_limit = max(1, min(limit or RECENT_PAGE_SIZE, RECENT_MAX_LIMIT))
    safe_offset = max(0, offset or 0)

    last_modified_expr = func.coalesce(File.last_modified, File.created_at)
    query = File.query.filter_by(owner_id=owner_id).order_by(desc(last_modified_expr))

    total_count = query.count()
    files = query.offset(safe_offset).limit(safe_limit).all()

    recent_items = [
        {
            'item': file_obj,
            'type': 'file',
            'file_type': file_obj.type,
            'last_modified': file_obj.last_modified or file_obj.created_at,
            'title': file_obj.title,
            'folder_id': file_obj.folder_id
        }
        for file_obj in files
    ]

    return recent_items, total_count


# Helper function to get correct card partial based on file type
def get_file_card_partial(file_type):
    """Return the correct card partial template path for a given file type."""
    type_to_partial = {
        'proprietary_note': 'p2/partials/card_mionote.html',
        'proprietary_whiteboard': 'p2/partials/card_miodraw.html',
        'proprietary_blocks': 'p2/partials/card_miobook.html',
        'proprietary_infinite_whiteboard': 'p2/partials/card_infinite_whiteboard.html',
        'proprietary_graph': 'p2/partials/card_graph.html',
        'markdown': 'p2/partials/card_markdown.html',
        'code': 'p2/partials/card_code.html',
        'todo': 'p2/partials/card_todo.html',
        'diagram': 'p2/partials/card_diagram.html',
        'table': 'p2/partials/card_table.html',
        'blocks': 'p2/partials/card_blocks.html',
        'pdf': 'p2/partials/card_pdf.html',
    }
    return type_to_partial.get(file_type, 'p2/partials/card_diagram.html')  # Default fallback


def compute_folder_depths(folders):
    def dfs(folder, depth):
        folder.depth = depth
        result = [folder]
        for child in folder.children:
            result.extend(dfs(child, depth + 1))
        return result

    root_folders = [f for f in folders if f.parent_id is None]
    all_ordered = []
    for root in root_folders:
        all_ordered.extend(dfs(root, 0))
    return all_ordered


# @folder_bp.route('/product2')
# def product2():
#     print("Rendering product2 page")
#     return render_template('p2/home.html')








## view_folder ----------------------------------------------------------
@folder_bp.route('/<int:folder_id>')
@login_required
def view_folder(folder_id):
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Access denied to folder", 'error')
        return redirect(url_for('p2_bp.dashboard'))

    # Get sort parameter
    sort_by = request.args.get('sort', 'name')  # default to 'name'
    
    # Get items - query File table with type discriminator
    notes = File.query.filter_by(folder_id=folder.id, owner_id=current_user.id, type='proprietary_note').all()
    subfolders = folder.children
    boards = File.query.filter_by(folder_id=folder.id, owner_id=current_user.id, type='proprietary_whiteboard').all()
    
    # Get MioBook documents (Files with type='proprietary_blocks')
    books = File.query.filter_by(folder_id=folder.id, owner_id=current_user.id, type='proprietary_blocks').all()
    
    # Get regular files (exclude MioBooks which are shown in dedicated section)
    files = File.query.filter(
        File.folder_id == folder.id,
        File.owner_id == current_user.id,
        File.type != 'book'
    ).all()

    # Include chat attachments that were hash-deduped into other folders so the
    # session folder still shows every file the chat references.
    session_for_folder = ChatSession.query.filter_by(session_folder_id=folder.id).first()
    if session_for_folder:
        existing_ids = {file_obj.id for file_obj in files}
        for attachment in session_for_folder.attachments.all():
            if attachment.file and attachment.file.id not in existing_ids:
                files.append(attachment.file)
                existing_ids.add(attachment.file.id)
    
    # DEBUG: Print all notes and files found
    # print(f"\n{'='*80}")
    # print(f"DEBUG view_folder - Folder ID: {folder.id}, Name: '{folder.name}'")
    # print(f"Total notes from query: {len(notes)}")
    # print(f"Total boards from query: {len(boards)}")
    # print(f"Total files from query: {len(files)}")
    # print(f"Total books from query: {len(books)}")
    # for note in notes:
    #     print(f"  - Note ID: {note.id}, Title: '{note.title}', Content length: {len(note.content_html or '')}")
    # for board in boards:
    #     print(f"  - Board ID: {board.id}, Title: '{board.title}', Type: '{board.type}', Content length: {len(str(board.content_json or ''))}")
    # for file_obj in files:
    #     print(f"  - File ID: {file_obj.id}, Type: '{file_obj.type}', Title: '{file_obj.title}'")
    # for book in books:
    #     print(f"  - Book ID: {book.id}, Title: '{book.title}', Blocks: {len(book.content_json or [])}")
    # print(f"{'='*80}\n")
    
    # Combined docs are now only MioBooks (File with type='proprietary_blocks')
    combined_docs = books
    
    # Regular notes are all File objects with type='proprietary_note'
    regular_notes = notes
    
    # DEBUG: Print split results
    # print(f"DEBUG: Regular notes: {len(regular_notes)}, Combined docs: {len(combined_docs)}")
    # print(f"Regular note IDs: {[n.id for n in regular_notes]}")
    # print(f"Combined doc IDs: {[n.id for n in combined_docs]}\n")
    
    breadcrumb = build_folder_breadcrumb(folder)
    
    # Sort items based on sort_by parameter
    def sort_items(items, sort_by, item_type):
        """Sort items with pinned files appearing first, then unpinned files sorted normally."""
        # Separate pinned and unpinned items (only for file-based types)
        if item_type in ['note', 'board', 'combined', 'file']:
            pinned = [item for item in items if hasattr(item, 'is_pinned') and item.is_pinned]
            unpinned = [item for item in items if not (hasattr(item, 'is_pinned') and item.is_pinned)]
        else:
            pinned = []
            unpinned = items
        
        # CRITICAL: Pinned items ignore sort order and maintain insertion order
        # Only sort unpinned items according to sort_by parameter
        if sort_by == 'name':
            if item_type == 'folder':
                unpinned = sorted(unpinned, key=lambda x: x.name.lower())
            elif item_type in ['note', 'board', 'combined', 'file']:
                unpinned = sorted(unpinned, key=lambda x: (x.title or '').lower())
        elif sort_by == 'created':
            unpinned = sorted(unpinned, key=lambda x: x.created_at or x.id)
        elif sort_by == 'modified':
            unpinned = sorted(unpinned, key=lambda x: x.last_modified or x.created_at or x.id, reverse=True)
        elif sort_by == 'size':
            if item_type == 'folder':
                # For folders, count total items (notes + boards + subfolders)
                unpinned = sorted(unpinned, key=lambda x: len(x.notes) + len(x.boards) + len(x.children), reverse=True)
            elif item_type in ['proprietary_note', 'proprietary_whiteboard']:
                # For notes/boards, use content length (notes use content_html, boards use content_json)
                unpinned = sorted(unpinned, key=lambda x: len(x.content_html or '') if item_type == 'proprietary_note' else len(str(x.content_json or '')), reverse=True)
            elif item_type in ['combined', 'file']:
                # For combined (books) and files, use get_content_size() method if available
                # Legacy notes in combined list may not have this method
                unpinned = sorted(unpinned, key=lambda x: x.get_content_size() if hasattr(x, 'get_content_size') else len(x.content or ''), reverse=True)
        
        # Return pinned items first (in their original order), then unpinned items (sorted)
        return pinned + unpinned
    
    regular_notes = sort_items(regular_notes, sort_by, 'note')
    subfolders = sort_items(subfolders, sort_by, 'folder')
    boards = sort_items(boards, sort_by, 'board')
    combined_docs = sort_items(combined_docs, sort_by, 'combined')
    files = sort_items(files, sort_by, 'file')
    
    # Group files by type for separate sections
    files_by_type = {}
    for file_obj in files:
        file_type = file_obj.type or 'other'
        if file_type not in files_by_type:
            files_by_type[file_type] = []
        files_by_type[file_type].append(file_obj)
    
    # Get recently modified items if viewing root folder
    recent_items = []
    recent_total_count = 0
    recent_has_more = False
    recent_next_offset = 0

    # Prefer explicit root flag, fall back to legacy parent_id==None
    is_root_folder = bool(getattr(folder, 'is_root', False) or folder.parent_id is None)
    if is_root_folder:
        recent_items, recent_total_count = get_recent_items_for_user(
            current_user.id,
            limit=RECENT_PAGE_SIZE,
            offset=0
        )
        recent_has_more = len(recent_items) < recent_total_count
        recent_next_offset = len(recent_items)
    
    # store folder_id and breadcrumb in session
    session['current_folder_id'] = folder.id
    session['current_breadcrumb'] = [(f.id, f.name) for f in breadcrumb]

    all_folders_raw = Folder.query.filter_by(user_id=current_user.id).all()
    all_folders = compute_folder_depths(all_folders_raw)

    # Get display preferences from user_prefs
    display_prefs = get_display_prefs(current_user)

    # DEBUG: Final counts being sent to template
    # print(f"DEBUG: Sending to template - Regular notes: {len(regular_notes)}, Combined docs: {len(combined_docs)}")
    # print(f"DEBUG: Regular note IDs being sent: {[n.id for n in regular_notes]}")
    # print(f"DEBUG: Combined doc IDs being sent: {[n.id for n in combined_docs]}")
    # print(f"{'='*80}\n")

    # Parse description JSON for notes: supply note.descriptions as a list, or None if invalid
    import json as _json
    for note in regular_notes:
        note.descriptions = None
        note.description_parse_failed = False
        # Description is now in metadata_json['description']
        description = (note.metadata_json or {}).get('description', '') if note.metadata_json else ''
        if description:
            try:
                parsed = _json.loads(description)
                # Accept dict or list; convert dict to ordered list by numeric keys
                if isinstance(parsed, dict):
                    try:
                        # Try sorting keys as integers when they are number-like strings
                        keys = sorted(parsed.keys(), key=lambda k: int(k))
                    except Exception:
                        keys = sorted(parsed.keys())
                    # Build key/value pairs preserving original keys in order
                    kv_pairs = [(k, parsed[k].strip()) for k in keys if isinstance(parsed[k], str) and parsed[k].strip()]
                    if kv_pairs:
                        note.descriptions = kv_pairs
                        note.description_readable = '\n'.join([f"{k}: {v}" for k, v in kv_pairs])
                        # print(f"DEBUG: Note {note.id} descriptions parsed (dict): count={len(kv_pairs)}")
                    else:
                        note.descriptions = None
                elif isinstance(parsed, list):
                    # Convert list into (index, value) pairs and filter empty ones
                    kv_pairs = [(str(i + 1), v.strip()) for i, v in enumerate(parsed) if isinstance(v, str) and v.strip()]
                    if kv_pairs:
                        note.descriptions = kv_pairs
                        note.description_readable = '\n'.join([f"{k}: {v}" for k, v in kv_pairs])
                        # print(f"DEBUG: Note {note.id} descriptions parsed (list): count={len(kv_pairs)}")
                    else:
                        note.descriptions = None
                else:
                    # Not a dict/list; treat as invalid for our new format
                    # print(f"DEBUG: Note {note.id} description is not a JSON object/list; ignoring for display.")
                    note.descriptions = None
                    note.description_parse_failed = True
            except Exception:
                preview = (description or '')[:200]
                # print(f"DEBUG: Failed to parse JSON description for Note {note.id}; preview={preview!r}; ignoring description.")
                note.descriptions = None
                note.description_parse_failed = True

    # Also provide pinned users (pull from current_user.user_prefs 'pinned_users' list)
    pinned_users = []
    try:
        prefs = current_user.user_prefs or {}
        pinned_ids = prefs.get('pinned_users', []) if isinstance(prefs, dict) else []
        if pinned_ids:
            # Preserve pinned order while resolving to User objects
            pinned_users = [User.query.get(int(uid)) for uid in pinned_ids if User.query.get(int(uid))]
    except Exception:
        pinned_users = []

    return render_template(
        'p2/folder_view_miospace.html',
        folder=folder,
        notes=regular_notes,
        combined_docs=combined_docs,
        subfolders=subfolders,
        boards=boards,
        files=files,
        files_by_type=files_by_type,
        folder_breadcrumb=breadcrumb,
        all_folders=all_folders,
        current_sort=sort_by,
        display_prefs=display_prefs,
        pinned_users=pinned_users,
        recent_items=recent_items,
        recent_total_count=recent_total_count,
        recent_has_more=recent_has_more,
        recent_next_offset=recent_next_offset,
        recent_page_size=RECENT_PAGE_SIZE,
        is_root_folder=is_root_folder
    )


@folder_bp.route('/recent-items', methods=['GET'])
@login_required
def recent_items_partial():
    """HTMX endpoint to fetch the next slice of recently modified items."""
    offset = request.args.get('offset', 0, type=int) or 0
    limit = request.args.get('limit', RECENT_PAGE_SIZE, type=int) or RECENT_PAGE_SIZE

    limit = max(1, min(limit, RECENT_MAX_LIMIT))
    offset = max(0, offset)

    recent_items, total_count = get_recent_items_for_user(
        current_user.id,
        limit=limit,
        offset=offset
    )

    has_more = (offset + len(recent_items)) < total_count
    next_offset = offset + len(recent_items)

    display_prefs = get_display_prefs(current_user)

    return render_template(
        'p2/partials/recently_modified_append.html',
        recent_items=recent_items,
        display_prefs=display_prefs,
        recent_total_count=total_count,
        recent_has_more=has_more,
        recent_next_offset=next_offset,
        recent_page_size=RECENT_PAGE_SIZE,
        use_oob=True
    )


@folder_bp.route('/create', methods=['POST'])
@login_required
def create_folder_route():
    from blueprints.p2.utils import add_notification
    
    # Safely extract form fields and coerce parent_id to int when possible.
    name = (request.form.get('name') or '').strip()
    description = (request.form.get('description') or '').strip()
    parent_id_raw = request.form.get('parent_id')

    # Normalize parent_id: treat empty, 'None', or virtual ids like 'home' as None
    if parent_id_raw in (None, '', 'None', 'home'):
        parent_id = None
    else:
        try:
            parent_id = int(parent_id_raw)
        except (ValueError, TypeError):
            parent_id = None

    if not name:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Folder name cannot be empty", 'error')
        return redirect(request.referrer or url_for('p2_bp.dashboard'))

    # Debug log to help trace parent_id issues during development
    print(f"DEBUG create_folder_route - name={name!r}, parent_id_raw={parent_id_raw!r}, parent_id_coerced={parent_id!r}")

    new_folder = create_folder(name, parent_id, description if description else None)
    
    # Add notification instead of flash message
    add_notification(current_user.id, f"Created folder '{name}'", 'info')
    
    return redirect(request.referrer or url_for('p2_bp.dashboard'))


@folder_bp.route('/rename/<int:folder_id>', methods=['POST'])
@login_required
def rename_folder_route(folder_id):
    from blueprints.p2.utils import add_notification
    from blueprints.p2.models import Folder
    
    folder = Folder.query.get(folder_id)
    old_name = folder.name if folder else 'Unknown'
    new_name = request.form.get("name")
    new_description = request.form.get("description")
    success = rename_folder(folder_id, new_name, new_description)
    
    # Add notification for successful rename
    if success and new_name and new_name != old_name:
        notif_msg = f"Renamed folder '{old_name}' to '{new_name}'"
        add_notification(current_user.id, notif_msg, 'info')
    
    # Check if this is an AJAX request (check for fetch API characteristic)
    if request.content_type == 'application/x-www-form-urlencoded':
        if success:
            return jsonify({'success': True, 'message': 'Folder updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Update failed'}), 400
    
    # Regular form submission - notification already added in rename_folder function
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/delete/<int:folder_id>', methods=['POST'])
@login_required
def delete_folder_route(folder_id):
    from blueprints.p2.utils import add_notification, format_bytes
    
    # Calculate total size to subtract for all files in folder (recursive)
    from blueprints.p2.models import Folder
    def calculate_content_size(content):
        return len(content.encode('utf-8')) if content else 0
    folder = Folder.query.get(folder_id)
    size_to_subtract = 0
    folder_name = folder.name if folder else 'Unknown'
    def recursive_size(f):
        nonlocal size_to_subtract
        # Get all files (notes, boards, and other types) in this folder
        for file_obj in f.files:
            size_to_subtract += file_obj.get_content_size()
        for child in f.children:
            recursive_size(child)
    user_id = current_user.id
    if folder and folder.user_id == current_user.id:
        recursive_size(folder)
    success, reason = delete_folder(folder_id, acting_user=current_user, with_reason=True)
    # Update user data size
    user = current_user
    if success and user:
        user.total_data_size = (user.total_data_size or 0) - size_to_subtract
        db.session.commit()
    
    # Clean up orphaned images after folder deletion
    if success:
        from .utils import cleanup_orphaned_images_for_user
        try:
            deleted_count, freed_bytes = cleanup_orphaned_images_for_user(user_id)
            if deleted_count > 0:
                print(f"[DELETE FOLDER] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
        except Exception as e:
            print(f"[DELETE FOLDER] Image cleanup failed: {e}")
        
        # Add notification for successful deletion
        notif_msg = f"Deleted folder '{folder_name}' ({format_bytes(size_to_subtract)} freed)"
        add_notification(current_user.id, notif_msg, 'delete')
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if is_ajax:
        if success:
            return jsonify({'success': True, 'message': 'Folder deleted successfully'})
        else:
            detail = reason or 'Could not delete folder'
            return jsonify({'success': False, 'message': detail}), 400
    # Regular form submission - notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/move/<int:folder_id>', methods=['POST'])
@login_required
def move_folder_route(folder_id):
    target_parent_id = request.form.get("target_folder")
    success = move_folder(folder_id, int(target_parent_id))
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if success:
            folder = Folder.query.get(folder_id)
            return jsonify({
                'success': True,
                'message': 'Folder moved successfully',
                'folder': {
                    'id': folder.id,
                    'name': folder.name,
                    'type': 'folder'
                }
            })
        return jsonify({'success': False, 'message': 'Move failed'}), 500
    
    # Regular form submission - notification handled in move_folder function
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/copy/<int:folder_id>', methods=['POST'])
@login_required
def copy_folder_route(folder_id):
    from blueprints.p2.utils import add_notification
    
    # Verify folder ownership
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        add_notification(current_user.id, "Access denied to copy folder", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))
    
    target_parent_id = request.form.get("target_folder")
    copied = copy_folder_recursive(folder_id, int(target_parent_id))
    
    # Add notification
    if copied:
        original_folder = Folder.query.get(folder_id)
        target_folder = Folder.query.get(int(target_parent_id))
        if original_folder and target_folder:
            notif_msg = f"Copied folder '{original_folder.name}' to '{target_folder.name}'"
            add_notification(current_user.id, notif_msg, 'transfer')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if copied:
            response_data = {
                'success': True,
                'message': 'Folder copied successfully',
                'folder': {
                    'id': copied.id,
                    'name': copied.name,
                    'type': 'folder'
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
                    'p2/partials/folder_card.html',
                    sub=copied,
                    display_prefs=display_prefs
                )
                
                response_data['new_item_html'] = new_item_html
                response_data['new_item_id'] = copied.id
                response_data['item_type'] = 'folder'
            
            return jsonify(response_data)
        return jsonify({'success': False, 'message': 'Copy failed'}), 500

    # Regular form submission - notification already added above
    return redirect(request.referrer or url_for('dashboard'))

@folder_bp.route('/send_to', methods=['POST'])
@login_required
def send_to_user_route():
    # Accept either form-encoded or JSON
    data = request.get_json(force=False, silent=True) or request.form
    item_type = (data.get('item_type') or '').lower()
    try:
        item_id = int(data.get('item_id'))
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid item_id'}), 400
    try:
        recipient_id = int(data.get('recipient_id'))
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid recipient_id'}), 400

    # VALIDATION 1: Check recipient exists BEFORE expensive operations
    receiver = User.query.get(recipient_id)
    if not receiver:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    
    # VALIDATION 2: Prevent sending to self
    if recipient_id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot send items to yourself'}), 400

    # File type mapping (consistent with batch_send_to)
    file_type_aliases = {
        'file': None,
        'note': 'proprietary_note',
        'proprietary_note': 'proprietary_note',
        'board': 'proprietary_whiteboard',
        'whiteboard': 'proprietary_whiteboard',
        'proprietary_whiteboard': 'proprietary_whiteboard',
        'infinite_whiteboard': 'proprietary_infinite_whiteboard',
        'proprietary_infinite_whiteboard': 'proprietary_infinite_whiteboard',
        'book': 'proprietary_blocks',
        'combined': 'proprietary_blocks',
        'proprietary_blocks': 'proprietary_blocks',
        'markdown': 'markdown',
        'todo': 'todo',
        'diagram': 'diagram',
        'table': 'table',
        'blocks': 'blocks',
        'code': 'code',
        'pdf': 'pdf',
        'timeline': 'timeline'
    }
    size_category_map = {
        'proprietary_note': 'note',
        'proprietary_whiteboard': 'board',
        'proprietary_infinite_whiteboard': 'board'
    }

    # VALIDATION 3: Ensure current user owns the item
    if item_type == 'folder':
        original = Folder.query.get(item_id)
        if not original or original.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied to folder'}), 403
        size_type = 'folder'
        resolved_type = 'folder'
    else:
        # Handle all file types using unified File model
        if item_type not in file_type_aliases:
            return jsonify({'success': False, 'message': f'Unsupported item type: {item_type}'}), 400
        
        type_filter = file_type_aliases[item_type]
        query = File.query.filter_by(id=item_id, owner_id=current_user.id)
        if type_filter:
            query = query.filter_by(type=type_filter)
        original = query.first()
        if not original:
            return jsonify({'success': False, 'message': f'Access denied to {item_type}'}), 403
        
        resolved_type = original.type
        size_type = size_category_map.get(resolved_type, 'file')

    # Calculate expected size (for quota pre-check)
    from blueprints.p2.utils import calculate_copy_size_for_item
    estimated_size, breakdown = calculate_copy_size_for_item(size_type, original, recipient_id)
    print(f"DEBUG send_to - estimated size: {estimated_size} (content={breakdown.get('content_bytes')} image={breakdown.get('image_bytes')} images={breakdown.get('images_count')})")

    # VALIDATION 4: Check guest limits BEFORE starting copy
    if getattr(receiver, 'user_type', None) == 'guest':
        content_limit = 50 * 1024 * 1024
        available = content_limit - (receiver.total_data_size or 0)
        if (receiver.total_data_size or 0) + estimated_size > content_limit:
            return jsonify({'success': False, 'message': 'Recipient data limit exceeded (guest)', 'required_space': estimated_size, 'available_space': available}), 400

    # Track copied files for cleanup on failure
    copied_files = []
    
    # Wrap entire copy operation in transaction with rollback
    try:
        # Perform copy (copy functions now return tuple: (item, actual_bytes_written))
        if item_type == 'folder':
            result = copy_folder_to_user(item_id, recipient_id, sender_username=current_user.username)
            if not result or result[0] is None:
                db.session.rollback()
                return jsonify({'success': False, 'message': 'Failed to copy folder'}), 500
            cloned, actual_bytes = result
            
            # Update receiver's total data size with ACTUAL bytes written
            update_user_data_size(receiver, actual_bytes)
            
            size_diff = actual_bytes - estimated_size
            if abs(size_diff) > 1024:  # Log if difference > 1KB
                print(f"DEBUG send_to - size difference: estimated={estimated_size}, actual={actual_bytes}, diff={size_diff}")
            
            print(f"DEBUG send_to - folder copy result: original {item_id} -> new {cloned.id}; receiver.total_data_size updated to {receiver.total_data_size}")
            current_app.logger.info("Folder %s sent to %s", original.name, receiver.username)
            
            # Add notification
            from blueprints.p2.utils import add_notification, format_bytes
            notif_msg = f"Sent folder '{original.name}' to {receiver.username} ({format_bytes(actual_bytes)})"
            add_notification(current_user.id, notif_msg, 'transfer')
            
            return jsonify({'success': True, 'message': 'Folder sent', 'new_folder_id': cloned.id})
            
        else:
            # Handle all file types using unified copy_file_to_user
            result = copy_file_to_user(item_id, recipient_id, sender_username=current_user.username)
            if not result or result[0] is None:
                db.session.rollback()
                return jsonify({'success': False, 'message': f'Failed to copy {resolved_type}'}), 500
            new_file, actual_bytes = result
            
            # Update receiver's total data size with ACTUAL bytes written
            update_user_data_size(receiver, actual_bytes)
            
            size_diff = actual_bytes - estimated_size
            if abs(size_diff) > 1024:
                print(f"DEBUG send_to - size difference: estimated={estimated_size}, actual={actual_bytes}, diff={size_diff}")
            
            print(f"DEBUG send_to - file copy result: original {item_id} -> new {new_file.id}; receiver.total_data_size updated to {receiver.total_data_size}")
            current_app.logger.info("%s %s sent to %s", resolved_type.capitalize(), original.title, receiver.username)
            
            # Add notification
            from blueprints.p2.utils import add_notification, format_bytes
            notif_msg = f"Sent {resolved_type} '{original.title}' to {receiver.username} ({format_bytes(actual_bytes)})"
            add_notification(current_user.id, notif_msg, 'transfer')
            
            return jsonify({'success': True, 'message': f'{resolved_type.capitalize()} sent', 'new_file_id': new_file.id})
            
    except Exception as e:
        # Rollback database changes
        db.session.rollback()
        print(f"ERROR send_to - exception during copy: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({'success': False, 'message': f'Copy operation failed: {str(e)}'}), 500



@folder_bp.route('/batch_send_to', methods=['POST'])
@login_required
def batch_send_to_user_route():
    """Send multiple items (folders, notes, boards, files) to a single user."""
    # Accept either form-encoded or JSON
    data = request.get_json(force=False, silent=True) or request.form
    
    # items is expected to be a JSON array of {type, id} objects
    try:
        items = data.get('items')
        if isinstance(items, str):
            items = json.loads(items)
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({'success': False, 'message': 'No items provided'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Invalid items format: {str(e)}'}), 400
    
    try:
        recipient_id = int(data.get('recipient_id'))
    except Exception:
        return jsonify({'success': False, 'message': 'Invalid recipient_id'}), 400

    # VALIDATION 1: Check recipient exists BEFORE expensive operations
    receiver = User.query.get(recipient_id)
    if not receiver:
        return jsonify({'success': False, 'message': 'Recipient not found'}), 404
    
    # VALIDATION 2: Prevent sending to self
    if recipient_id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot send items to yourself'}), 400

    # VALIDATION 3: Ensure current user owns all items
    file_type_aliases = {
        'file': None,
        'note': 'proprietary_note',
        'proprietary_note': 'proprietary_note',
        'board': 'proprietary_whiteboard',
        'whiteboard': 'proprietary_whiteboard',
        'proprietary_whiteboard': 'proprietary_whiteboard',
        'infinite_whiteboard': 'proprietary_infinite_whiteboard',
        'proprietary_infinite_whiteboard': 'proprietary_infinite_whiteboard',
        'book': 'proprietary_blocks',
        'combined': 'proprietary_blocks',
        'proprietary_blocks': 'proprietary_blocks',
        'markdown': 'markdown',
        'todo': 'todo',
        'diagram': 'diagram',
        'table': 'table',
        'blocks': 'blocks',
        'code': 'code',
        'pdf': 'pdf',
        'timeline': 'timeline'
    }
    size_category_map = {
        'proprietary_note': 'note',
        'proprietary_whiteboard': 'board',
        'proprietary_infinite_whiteboard': 'board'
    }

    validated_items = []
    for item in items:
        item_type = (item.get('type') or '').lower()
        try:
            item_id = int(item.get('id'))
        except Exception:
            return jsonify({'success': False, 'message': f'Invalid item ID: {item.get("id")}'}), 400
        
        if item_type == 'folder':
            original = Folder.query.get(item_id)
            if not original or original.user_id != current_user.id:
                return jsonify({'success': False, 'message': f'Access denied to folder {item_id}'}), 403
            validated_items.append({
                'type': item_type,
                'id': item_id,
                'object': original,
                'size_type': 'folder',
                'resolved_type': 'folder'
            })
            continue

        if item_type not in file_type_aliases:
            return jsonify({'success': False, 'message': f'Unsupported item type: {item_type}'}), 400

        type_filter = file_type_aliases[item_type]
        query = File.query.filter_by(id=item_id, owner_id=current_user.id)
        if type_filter:
            query = query.filter_by(type=type_filter)
        original = query.first()
        if not original:
            return jsonify({'success': False, 'message': f'Access denied to {item_type} {item_id}'}), 403

        resolved_type = original.type
        size_type = size_category_map.get(resolved_type, 'file')
        validated_items.append({
            'type': item_type,
            'id': item_id,
            'object': original,
            'size_type': size_type,
            'resolved_type': resolved_type
        })

    # Calculate total expected size (for quota pre-check)
    from blueprints.p2.utils import calculate_copy_size_for_item
    total_estimated_size = 0
    for item in validated_items:
        size_key = item.get('size_type', item['type'])
        estimated_size, breakdown = calculate_copy_size_for_item(size_key, item['object'], recipient_id)
        total_estimated_size += estimated_size

    print(f"DEBUG batch_send_to - estimated total size: {total_estimated_size} for {len(validated_items)} items")

    # VALIDATION 4: Check guest limits BEFORE starting copy
    if getattr(receiver, 'user_type', None) == 'guest':
        content_limit = 50 * 1024 * 1024
        available = content_limit - (receiver.total_data_size or 0)
        if (receiver.total_data_size or 0) + total_estimated_size > content_limit:
            return jsonify({
                'success': False, 
                'message': 'Recipient data limit exceeded (guest)', 
                'required_space': total_estimated_size, 
                'available_space': available
            }), 400

    # Track total actual bytes written
    total_actual_bytes = 0
    results = []
    
    # Wrap entire copy operation in transaction with rollback
    try:
        for item in validated_items:
            item_type = item['type']
            item_id = item['id']
            original = item['object']
            resolved_type = item.get('resolved_type', item_type)
            
            # Perform copy based on type
            if item_type == 'folder':
                result = copy_folder_to_user(item_id, recipient_id, sender_username=current_user.username)
                if not result or result[0] is None:
                    raise Exception(f'Failed to copy folder {item_id}')
                cloned, actual_bytes = result
                results.append({'type': 'folder', 'original_id': item_id, 'new_id': cloned.id, 'bytes': actual_bytes, 'title': original.name})
                total_actual_bytes += actual_bytes
                
            else:
                result = copy_file_to_user(original.id, recipient_id, sender_username=current_user.username)
                if not result or result[0] is None:
                    raise Exception(f'Failed to copy {resolved_type} {item_id}')
                new_file, actual_bytes = result
                results.append({
                    'type': resolved_type,
                    'original_id': item_id,
                    'new_id': new_file.id,
                    'bytes': actual_bytes,
                    'title': original.title
                })
                total_actual_bytes += actual_bytes
        
        # Update receiver's total data size with ACTUAL bytes written
        update_user_data_size(receiver, total_actual_bytes)
        
        size_diff = total_actual_bytes - total_estimated_size
        if abs(size_diff) > 1024:  # Log if difference > 1KB
            print(f"DEBUG batch_send_to - size difference: estimated={total_estimated_size}, actual={total_actual_bytes}, diff={size_diff}")
        
        print(f"DEBUG batch_send_to - successfully sent {len(results)} items; receiver.total_data_size updated to {receiver.total_data_size}")
        current_app.logger.info("Batch sent %d items to %s", len(results), receiver.username)
        
        # Add notification
        from blueprints.p2.utils import add_notification, format_bytes
        notif_msg = f"Sent {len(results)} item{'s' if len(results) > 1 else ''} to {receiver.username} ({format_bytes(total_actual_bytes)})"
        add_notification(current_user.id, notif_msg, 'transfer')
        
        return jsonify({
            'success': True, 
            'message': f'Successfully sent {len(results)} items', 
            'results': results,
            'total_bytes': total_actual_bytes
        })
            
    except Exception as e:
        # Rollback database changes
        db.session.rollback()
        print(f"ERROR batch_send_to - exception during copy: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return jsonify({'success': False, 'message': f'Batch copy operation failed: {str(e)}'}), 500



@folder_bp.route('/move_note/<int:note_id>', methods=['POST'])
@login_required
def move_note_route(note_id):
    from blueprints.p2.models import Folder
    note = File.query.filter_by(id=note_id, type='proprietary_note').first()
    if not note:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Note not found", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        return redirect(url_for('dashboard'))
    
    if note.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Access denied to move note", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    target_folder_id = request.form.get("target_folder")
    target_folder = Folder.query.get(target_folder_id)

    if not target_folder or target_folder.user_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Invalid target folder for note move", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid target folder'}), 400
        return redirect(request.referrer or url_for('dashboard'))

    note.folder_id = target_folder.id
    db.session.commit()
    
    # Add notification
    from blueprints.p2.utils import add_notification
    notif_msg = f"Moved note '{note.title}' to '{target_folder.name}'"
    add_notification(current_user.id, notif_msg, 'transfer')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': f"Moved note '{note.title}' to '{target_folder.name}'",
            'note': {
                'id': note.id,
                'title': note.title,
                'type': 'note'
            }
        })
    
    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/duplicate_note/<int:note_id>', methods=['POST'])
@login_required
def duplicate_note(note_id):
    original = File.query.filter_by(id=note_id, type='proprietary_note').first()
    if not original:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Note not found", 'error')
        return redirect(url_for('dashboard'))

    if original.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Unauthorized note duplication attempt", 'error')
        return redirect(url_for('dashboard'))

    target_folder_id = request.form.get("target_folder")
    target_folder = Folder.query.get(target_folder_id)

    if not target_folder or target_folder.user_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Invalid target folder for note duplication", 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # Create a new note with the same data
    new_title = original.title + " (copy)"
    duplicate = File(
        title=new_title,
        type='proprietary_note',
        content_html=original.content_html,
        metadata_json=original.metadata_json.copy() if original.metadata_json else {},
        owner_id=current_user.id,
        folder_id=target_folder.id
    )
    
    # Calculate size and check cap
    content_size = original.get_content_size()
    def check_guest_limit(user, additional_size):
        if getattr(user, 'user_type', None) == 'guest':
            max_size = 50 * 1024 * 1024
            if (user.total_data_size or 0) + additional_size > max_size:
                from blueprints.p2.utils import add_notification
                add_notification(user.id, "Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", 'error')
                return False
        return True
    def update_user_data_size(user, delta):
        user.total_data_size = (user.total_data_size or 0) + delta
        db.session.commit()
    if not check_guest_limit(current_user, content_size):
        return redirect(request.referrer or url_for('dashboard'))
    
    db.session.add(duplicate)
    db.session.commit()
    update_user_data_size(current_user, content_size)
    
    # Add notification
    from blueprints.p2.utils import add_notification, format_bytes
    notif_msg = f"Duplicated note '{original.title}' to '{target_folder.name}' ({format_bytes(content_size)})"
    add_notification(current_user.id, notif_msg, 'transfer')

    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response_data = {
            'success': True,
            'message': f"Duplicated note as '{new_title}'",
            'note': {
                'id': duplicate.id,
                'title': duplicate.title,
                'type': 'note'
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
            
            partial = get_file_card_partial(duplicate.type)
            new_item_html = render_template(
                partial,
                file=duplicate,
                display_prefs=display_prefs
            )
            
            response_data['new_item_html'] = new_item_html
            response_data['new_item_id'] = duplicate.id
            response_data['item_type'] = 'file'
        
        return jsonify(response_data)

    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


# for whiteboard


@folder_bp.route('/rename_board/<int:board_id>', methods=['POST'])
@login_required
def rename_board_route(board_id):
    from blueprints.p2.utils import add_notification
    
    board = File.query.filter_by(id=board_id, type='proprietary_whiteboard').first()
    if not board:
        add_notification(current_user.id, "MioDraw not found", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'MioDraw not found'}), 404
        return redirect(url_for('dashboard'))
    
    if board.owner_id != current_user.id:
        add_notification(current_user.id, "Access denied to rename MioDraw", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    old_title = board.title
    new_title = request.form.get("new_name") or request.form.get("title", "")
    new_title = new_title.strip()
    new_description = request.form.get("description", "")
    
    if not new_title:
        add_notification(current_user.id, "MioDraw title cannot be empty", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'MioDraw title cannot be empty'}), 400
        return redirect(request.referrer or url_for('dashboard'))

    board.title = new_title
    # Store description in metadata_json
    if not board.metadata_json:
        board.metadata_json = {}
    board.metadata_json['description'] = new_description
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(board, 'metadata_json')
    db.session.commit()
    
    # Add notification for rename if title changed
    if new_title != old_title:
        notif_msg = f"Renamed board '{old_title}' to '{new_title}'"
        add_notification(current_user.id, notif_msg, 'info')
    
    if request.content_type == 'application/x-www-form-urlencoded':
        return jsonify({'success': True, 'message': 'MioDraw renamed successfully'})
    # Notification already added above if title changed
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/move_board/<int:board_id>', methods=['POST'])
@login_required
def move_board_route(board_id):
    from blueprints.p2.models import Folder
    
    board = File.query.filter_by(id=board_id, type='proprietary_whiteboard').first()
    if not board:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "MioDraw not found", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'MioDraw not found'}), 404
        return redirect(url_for('dashboard'))
    
    if board.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Access denied to move MioDraw", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    target_folder_id = request.form.get("target_folder")
    target_folder = Folder.query.get(target_folder_id)

    if not target_folder or target_folder.user_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Invalid target folder for MioDraw move", 'error')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid target folder'}), 400
        return redirect(request.referrer or url_for('dashboard'))

    board.folder_id = target_folder.id
    db.session.commit()
    
    # Add notification
    from blueprints.p2.utils import add_notification
    notif_msg = f"Moved board '{board.title}' to '{target_folder.name}'"
    add_notification(current_user.id, notif_msg, 'transfer')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': f"Moved MioDraw '{board.title}' to '{target_folder.name}'",
            'board': {
                'id': board.id,
                'title': board.title,
                'type': 'board'
            }
        })
    
    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/duplicate_board/<int:board_id>', methods=['POST'])
@login_required
def duplicate_board_route(board_id):
    original = File.query.filter_by(id=board_id, type='proprietary_whiteboard').first()
    if not original:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "MioDraw not found", 'error')
        return redirect(url_for('dashboard'))

    if original.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Unauthorized MioDraw duplication attempt", 'error')
        return redirect(url_for('dashboard'))

    target_folder_id = request.form.get("target_folder")
    target_folder = Folder.query.get(target_folder_id)

    if not target_folder or target_folder.user_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Invalid target folder for MioDraw duplication", 'error')
        return redirect(request.referrer or url_for('dashboard'))

    # Create a new board with the same data
    new_title = original.title + " (copy)"
    duplicate = File(
        title=new_title,
        type='proprietary_whiteboard',
        content_json=original.content_json,
        metadata_json=original.metadata_json.copy() if original.metadata_json else {},
        owner_id=current_user.id,
        folder_id=target_folder.id
    )
    
    # Calculate size and check cap
    content_size = original.get_content_size()
    def check_guest_limit(user, additional_size):
        if getattr(user, 'user_type', None) == 'guest':
            max_size = 50 * 1024 * 1024
            if (user.total_data_size or 0) + additional_size > max_size:
                from blueprints.p2.utils import add_notification
                add_notification(user.id, "Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", 'error')
                return False
        return True
    def update_user_data_size(user, delta):
        user.total_data_size = (user.total_data_size or 0) + delta
        db.session.commit()
    if not check_guest_limit(current_user, content_size):
        return redirect(request.referrer or url_for('dashboard'))
    
    db.session.add(duplicate)
    db.session.commit()
    update_user_data_size(current_user, content_size)
    
    # Add notification
    from blueprints.p2.utils import add_notification, format_bytes
    notif_msg = f"Duplicated board '{original.title}' to '{target_folder.name}' ({format_bytes(content_size)})"
    add_notification(current_user.id, notif_msg, 'transfer')

    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response_data = {
            'success': True,
            'message': f"Duplicated MioDraw as '{new_title}'",
            'board': {
                'id': duplicate.id,
                'title': duplicate.title,
                'type': 'board'
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
            
            partial = get_file_card_partial(duplicate.type)
            new_item_html = render_template(
                partial,
                file=duplicate,
                display_prefs=display_prefs
            )
            
            response_data['new_item_html'] = new_item_html
            response_data['new_item_id'] = duplicate.id
            response_data['item_type'] = 'file'
        
        return jsonify(response_data)

    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/delete_board/<int:board_id>', methods=['POST'])
@login_required
def delete_board_route(board_id):
    from blueprints.p2.utils import add_notification
    
    board = File.query.filter_by(id=board_id, type='proprietary_whiteboard').first()
    if not board:
        add_notification(current_user.id, "MioDraw not found", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'MioDraw not found'}), 404
        return redirect(url_for('dashboard'))
    
    if board.owner_id != current_user.id:
        add_notification(current_user.id, "Access denied to delete MioDraw", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    board_title = board.title
    user_id = board.owner_id
    size_to_subtract = board.get_content_size()
    board_user = current_user
    db.session.delete(board)
    db.session.commit()
    # Update user data size
    if board_user:
        board_user.total_data_size = (board_user.total_data_size or 0) - size_to_subtract
        db.session.commit()
    
    # Add notification for deletion
    notif_msg = f"Deleted board '{board_title}'"
    add_notification(current_user.id, notif_msg, 'delete')
    
    # Clean up orphaned images
    from .utils import cleanup_orphaned_images_for_user
    try:
        deleted_count, freed_bytes = cleanup_orphaned_images_for_user(user_id)
        if deleted_count > 0:
            print(f"[DELETE BOARD] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
    except Exception as e:
        print(f"[DELETE BOARD] Image cleanup failed: {e}")
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if is_ajax:
        return jsonify({'success': True, 'message': f"Deleted MioDraw '{board_title}'"})
    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/rename_note/<int:note_id>', methods=['POST'])
@login_required
def rename_note_route(note_id):
    from blueprints.p2.utils import add_notification
    
    note = File.query.filter_by(id=note_id, type='proprietary_note').first()
    if not note:
        add_notification(current_user.id, "Note not found", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        return redirect(url_for('dashboard'))
    
    if note.owner_id != current_user.id:
        add_notification(current_user.id, "Access denied to rename note", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    old_title = note.title
    new_title = request.form.get("new_name") or request.form.get("title")
    new_description = request.form.get("description", "")
    
    if new_title:
        note.title = new_title
        # Store description in metadata_json
        if not note.metadata_json:
            note.metadata_json = {}
        note.metadata_json['description'] = new_description
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(note, 'metadata_json')
        db.session.commit()
        
        # Add notification for rename if title changed
        if new_title != old_title:
            notif_msg = f"Renamed note '{old_title}' to '{new_title}'"
            add_notification(current_user.id, notif_msg, 'info')
        
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': True, 'message': 'Note renamed successfully'})
        # Notification already added above
    else:
        add_notification(current_user.id, "Invalid note title", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Invalid note title'}), 400
    
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note_route(note_id):
    from blueprints.p2.utils import add_notification
    
    note = File.query.filter_by(id=note_id, type='proprietary_note').first()
    if not note:
        add_notification(current_user.id, "Note not found", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        return redirect(url_for('dashboard'))
    
    if note.owner_id != current_user.id:
        add_notification(current_user.id, "Access denied to delete note", 'error')
        if request.content_type == 'application/x-www-form-urlencoded':
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        return redirect(url_for('dashboard'))

    note_title = note.title
    user_id = note.owner_id
    db.session.delete(note)
    db.session.commit()
    
    # Add notification for deletion
    notif_msg = f"Deleted note '{note_title}'"
    add_notification(current_user.id, notif_msg, 'delete')
    
    # Clean up orphaned images
    from .utils import cleanup_orphaned_images_for_user
    try:
        deleted_count, freed_bytes = cleanup_orphaned_images_for_user(user_id)
        if deleted_count > 0:
            print(f"[DELETE NOTE] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
    except Exception as e:
        print(f"[DELETE NOTE] Image cleanup failed: {e}")
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json
    if is_ajax:
        return jsonify({'success': True, 'message': f"Deleted note '{note_title}'"})
    
    # Notification already added above
    return redirect(request.referrer or url_for('dashboard'))


@folder_bp.route('/set_public', methods=['POST'])
@login_required
def set_public_route():
    """Set the is_public flag for a folder, note, board, or file.

    POST parameters (form or JSON):
      - item_type: 'folder' | 'note' | 'board' | 'file' | 'markdown' | 'todo' | 'diagram' | 'book' | 'blocks' | 'table'
      - item_id: integer
      - public: '1'|'0' or true/false
    If item_type == 'folder', the change is applied recursively to children, notes, boards, and files.
    """
    data = request.form if request.form else (request.get_json() or {})
    item_type = data.get('item_type') or data.get('type')
    item_id = data.get('item_id') or data.get('id')
    public_val = data.get('public')

    if not item_type or not item_id:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    try:
        item_id = int(item_id)
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid item id'}), 400

    is_public = str(public_val).lower() in ('1', 'true', 'yes', 'on')

    # Folder
    if item_type == 'folder':
        folder = Folder.query.get_or_404(item_id)
        if folder.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403

        affected = {'folders': [], 'notes': [], 'boards': [], 'files': []}

        def recurse_set(f):
            f.is_public = is_public
            affected['folders'].append(f.id)
            # set all files in this folder (notes, boards, and other types)
            for file_obj in f.files:
                try:
                    file_obj.is_public = is_public
                    # Track by type
                    if file_obj.type == 'proprietary_note':
                        affected['notes'].append(file_obj.id)
                    elif file_obj.type == 'proprietary_whiteboard':
                        affected['boards'].append(file_obj.id)
                    else:
                        affected['files'].append(file_obj.id)
                except Exception:
                    pass
            for child in f.children:
                recurse_set(child)

        recurse_set(folder)
        db.session.commit()
        return jsonify({'success': True, 'message': f"Folder {'public' if is_public else 'private'} set", 'affected': affected, 'is_public': is_public})

    # Note
    elif item_type == 'proprietary_note':
        note = File.query.filter_by(id=item_id, type='proprietary_note').first()
        if not note:
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        if note.owner_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        note.is_public = is_public
        db.session.commit()
        return jsonify({'success': True, 'message': f"Note {'public' if is_public else 'private'} set", 'affected': {'notes': [note.id], 'folders': [], 'boards': [], 'files': []}, 'is_public': is_public})

    # Board
    elif item_type == 'proprietary_whiteboard':
        board = File.query.filter_by(id=item_id, type='proprietary_whiteboard').first()
        if not board:
            return jsonify({'success': False, 'message': 'Board not found'}), 404
        if board.owner_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        board.is_public = is_public
        db.session.commit()
        return jsonify({'success': True, 'message': f"Board {'public' if is_public else 'private'} set", 'affected': {'boards': [board.id], 'notes': [], 'folders': [], 'files': []}, 'is_public': is_public})

    # File (covers all file types including proprietary ones)
    elif item_type in ['file', 'markdown', 'todo', 'diagram', 'proprietary_blocks', 'blocks', 'table', 'timeline', 'code', 'pdf', 'proprietary_infinite_whiteboard', 'proprietary_graph']:
        file_obj = File.query.get_or_404(item_id)
        if file_obj.owner_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied'}), 403
        file_obj.is_public = is_public
        db.session.commit()
        return jsonify({'success': True, 'message': f"File {'public' if is_public else 'private'} set", 'affected': {'files': [file_obj.id], 'notes': [], 'boards': [], 'folders': []}, 'is_public': is_public})

    else:
        return jsonify({'success': False, 'message': f'Unknown item type: {item_type}'}), 400


@folder_bp.route('/public/copy/note/<int:note_id>', methods=['POST'])
@login_required
def public_copy_note(note_id):
    """Copy a public note into the current user's folder (or root)."""
    from blueprints.p2.models import Folder
    note = File.query.filter_by(id=note_id, type='proprietary_note').first()
    if not note:
        return jsonify({'success': False, 'message': 'Note not found'}), 404
    if not getattr(note, 'is_public', False) and note.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not allowed'}), 403

    # Determine target folder: use session current_folder_id or user's root
    target_folder_id = session.get('current_folder_id')
    target_folder = None
    if target_folder_id:
        target_folder = Folder.query.get(target_folder_id)
    if not target_folder or target_folder.user_id != current_user.id:
        # fallback to first root folder for user
        target_folder = Folder.query.filter_by(user_id=current_user.id).first()
    if not target_folder:
        # create a root folder
        target_folder = create_folder('root', None, None)

    # duplicate note
    # quota checks (guest limit)
    size = note.get_content_size()

    def check_guest_limit(user, additional_size):
        if getattr(user, 'user_type', None) == 'guest':
            max_size = 50 * 1024 * 1024
            if (user.total_data_size or 0) + additional_size > max_size:
                return False
        return True

    if not check_guest_limit(current_user, size):
        # return quota info as well
        def quota_info(user):
            if getattr(user, 'user_type', None) == 'guest':
                total = 50 * 1024 * 1024
                used = user.total_data_size or 0
                remaining = max(0, total - used)
                return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
            else:
                return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

        print(f"[DEBUG public_copy_note] quota exceeded for user {getattr(current_user,'id',None)}; size requested: {size}")
        return jsonify({'success': False, 'message': 'Storage quota exceeded (50MB for guests)', 'quota': quota_info(current_user)}), 403

    duplicate = File(
        title=(note.title or '') + ' (copy)',
        type='proprietary_note',
        content_html=note.content_html,
        metadata_json=note.metadata_json.copy() if note.metadata_json else {},
        owner_id=current_user.id,
        folder_id=target_folder.id
    )
    try:
        db.session.add(duplicate)
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_note] Failed to create duplicate note for note_id={note_id} user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Copy failed (db error)'}), 500

    # update user data size and return quota info
    try:
        current_user.total_data_size = (current_user.total_data_size or 0) + size
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_note] Failed updating total_data_size after copy for user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        try:
            db.session.rollback()
        except Exception:
            pass

    # build quota info
    def quota_info(user):
        if getattr(user, 'user_type', None) == 'guest':
            total = 50 * 1024 * 1024
            used = user.total_data_size or 0
            remaining = max(0, total - used)
            return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
        else:
            return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

    print(f"[INFO public_copy_note] Note {note_id} copied -> new_id={duplicate.id} for user {getattr(current_user,'id',None)} folder={duplicate.folder_id}")
    return jsonify({'success': True, 'message': 'Note copied', 'new_id': duplicate.id, 'quota': quota_info(current_user)})


@folder_bp.route('/public/copy/board/<int:board_id>', methods=['POST'])
@login_required
def public_copy_board(board_id):
    """Copy a public board into the current user's folder (or root)."""
    from blueprints.p2.models import Folder
    board = File.query.filter_by(id=board_id, type='proprietary_whiteboard').first()
    if not board:
        return jsonify({'success': False, 'message': 'Board not found'}), 404
    if not getattr(board, 'is_public', False) and board.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not allowed'}), 403

    target_folder_id = session.get('current_folder_id')
    target_folder = None
    if target_folder_id:
        target_folder = Folder.query.get(target_folder_id)
    if not target_folder or target_folder.user_id != current_user.id:
        target_folder = Folder.query.filter_by(user_id=current_user.id).first()
    if not target_folder:
        target_folder = create_folder('root', None, None)

    duplicate = File(
        title=(board.title or '') + ' (copy)',
        type='proprietary_whiteboard',
        content_json=board.content_json,
        metadata_json=board.metadata_json.copy() if board.metadata_json else {},
        owner_id=current_user.id,
        folder_id=target_folder.id
    )
    # quota checks
    size = board.get_content_size()

    def check_guest_limit(user, additional_size):
        if getattr(user, 'user_type', None) == 'guest':
            max_size = 50 * 1024 * 1024
            if (user.total_data_size or 0) + additional_size > max_size:
                return False
        return True

    if not check_guest_limit(current_user, size):
        def quota_info(user):
            if getattr(user, 'user_type', None) == 'guest':
                total = 50 * 1024 * 1024
                used = user.total_data_size or 0
                remaining = max(0, total - used)
                return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
            else:
                return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

        print(f"[DEBUG public_copy_board] quota exceeded for user {getattr(current_user,'id',None)}; size requested: {size}")
        return jsonify({'success': False, 'message': 'Storage quota exceeded (50MB for guests)', 'quota': quota_info(current_user)}), 403

    try:
        db.session.add(duplicate)
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_board] Failed to create duplicate board for board_id={board_id} user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Copy failed (db error)'}), 500

    try:
        current_user.total_data_size = (current_user.total_data_size or 0) + size
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_board] Failed updating total_data_size after copy for user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        try:
            db.session.rollback()
        except Exception:
            pass

    def quota_info(user):
        if getattr(user, 'user_type', None) == 'guest':
            total = 50 * 1024 * 1024
            used = user.total_data_size or 0
            remaining = max(0, total - used)
            return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
        else:
            return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

    print(f"[INFO public_copy_board] Board {board_id} copied -> new_id={duplicate.id} for user {getattr(current_user,'id',None)} folder={duplicate.folder_id}")
    return jsonify({'success': True, 'message': 'Board copied', 'new_id': duplicate.id, 'quota': quota_info(current_user)})


@folder_bp.route('/public/copy/folder/<int:folder_id>', methods=['POST'])
@login_required
def public_copy_folder(folder_id):
    """Attempt to copy a public folder recursively into current user's folder.
    This will try to reuse copy_folder_recursive. If that fails, return error."""
    from blueprints.p2.models import Folder
    folder = Folder.query.get_or_404(folder_id)
    if not getattr(folder, 'is_public', False) and folder.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not allowed'}), 403

    # target parent is user's root
    target_parent = Folder.query.filter_by(user_id=current_user.id).first()
    if not target_parent:
        target_parent = create_folder('root', None, None)

    # compute total size of all files in the folder tree
    def calculate_folder_size(f):
        total = 0
        # Calculate size of all files (notes, boards, and other types)
        for file_obj in f.files:
            total += file_obj.get_content_size()
        for child in f.children:
            total += calculate_folder_size(child)
        return total

    try:
        size_to_add = calculate_folder_size(folder)

        def check_guest_limit(user, additional_size):
            if getattr(user, 'user_type', None) == 'guest':
                max_size = 50 * 1024 * 1024
                if (user.total_data_size or 0) + additional_size > max_size:
                    return False
            return True

        if not check_guest_limit(current_user, size_to_add):
            def quota_info(user):
                if getattr(user, 'user_type', None) == 'guest':
                    total = 50 * 1024 * 1024
                    used = user.total_data_size or 0
                    remaining = max(0, total - used)
                    return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
                else:
                    return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

            return jsonify({'success': False, 'message': 'Storage quota exceeded (50MB for guests)', 'quota': quota_info(current_user)}), 403

        copied = copy_folder_recursive(folder_id, target_parent.id, allow_external=True)
        if not copied:
            print(f"[ERROR public_copy_folder] copy_folder_recursive returned False for folder {folder_id}")
            return jsonify({'success': False, 'message': 'Copy failed'}), 500

        # update user data size
        try:
            current_user.total_data_size = (current_user.total_data_size or 0) + size_to_add
            db.session.commit()
        except Exception:
            db.session.rollback()

        def quota_info(user):
            if getattr(user, 'user_type', None) == 'guest':
                total = 50 * 1024 * 1024
                used = user.total_data_size or 0
                remaining = max(0, total - used)
                return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
            else:
                return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

        print(f"[INFO public_copy_folder] Folder {folder_id} copied into target_parent={target_parent.id} for user {getattr(current_user,'id',None)} size_added={size_to_add}")
        return jsonify({'success': True, 'message': 'Folder copied', 'quota': quota_info(current_user), 'target_folder_id': target_parent.id})
    except Exception as e:
        import traceback
        # Ensure session is clean before doing any ORM attribute access
        try:
            db.session.rollback()
        except Exception:
            pass
        # Use get_id() to avoid triggering lazy loads on the user object
        try:
            uid = current_user.get_id()
        except Exception:
            uid = None
        print(f"[EXCEPTION public_copy_folder] Exception copying folder {folder_id} for user {uid}: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Copy failed due to internal error'}), 500


@folder_bp.route('/public/copy/file/<int:file_id>', methods=['POST'])
@login_required
def public_copy_file(file_id):
    """Copy a public file into the current user's folder (or root)."""
    from blueprints.p2.models import File, Folder
    file = File.query.get_or_404(file_id)
    if not getattr(file, 'is_public', False) and file.owner_id != current_user.id:
        return jsonify({'success': False, 'message': 'Not allowed'}), 403

    # Determine target folder: use session current_folder_id or user's root
    target_folder_id = session.get('current_folder_id')
    target_folder = None
    if target_folder_id:
        target_folder = Folder.query.get(target_folder_id)
    if not target_folder or target_folder.user_id != current_user.id:
        # fallback to first root folder for user
        target_folder = Folder.query.filter_by(user_id=current_user.id).first()
    if not target_folder:
        # create a root folder
        target_folder = create_folder('root', None, None)

    # Calculate file size for quota check
    size = file.get_content_size()

    def check_guest_limit(user, additional_size):
        if getattr(user, 'user_type', None) == 'guest':
            max_size = 50 * 1024 * 1024
            if (user.total_data_size or 0) + additional_size > max_size:
                return False
        return True

    if not check_guest_limit(current_user, size):
        def quota_info(user):
            if getattr(user, 'user_type', None) == 'guest':
                total = 50 * 1024 * 1024
                used = user.total_data_size or 0
                remaining = max(0, total - used)
                return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
            else:
                return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

        print(f"[DEBUG public_copy_file] quota exceeded for user {getattr(current_user,'id',None)}; size requested: {size}")
        return jsonify({'success': False, 'message': 'Storage quota exceeded (50MB for guests)', 'quota': quota_info(current_user)}), 403

    # Create duplicate file
    duplicate = File(
        title=(file.title or '') + ' (copy)',
        type=file.type,
        content_text=file.content_text,
        content_html=file.content_html,
        content_json=file.content_json,
        content_blob=file.content_blob,
        metadata_json=file.metadata_json.copy() if file.metadata_json else {},
        owner_id=current_user.id,
        folder_id=target_folder.id
    )
    try:
        db.session.add(duplicate)
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_file] Failed to create duplicate file for file_id={file_id} user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Copy failed (db error)'}), 500

    # Update user data size
    try:
        current_user.total_data_size = (current_user.total_data_size or 0) + size
        db.session.commit()
    except Exception as e:
        import traceback
        print(f"[ERROR public_copy_file] Failed updating total_data_size after copy for user_id={getattr(current_user,'id',None)}: {e}")
        traceback.print_exc()
        try:
            db.session.rollback()
        except Exception:
            pass

    # Build quota info
    def quota_info(user):
        if getattr(user, 'user_type', None) == 'guest':
            total = 50 * 1024 * 1024
            used = user.total_data_size or 0
            remaining = max(0, total - used)
            return {'is_guest': True, 'quota_total': total, 'quota_used': used, 'quota_remaining': remaining}
        else:
            return {'is_guest': False, 'quota_total': None, 'quota_used': None, 'quota_remaining': None}

    print(f"[INFO public_copy_file] File {file_id} copied -> new_id={duplicate.id} for user {getattr(current_user,'id',None)} folder={duplicate.folder_id}")
    return jsonify({'success': True, 'message': 'File copied', 'new_id': duplicate.id, 'quota': quota_info(current_user)})


@folder_bp.route('/api/save-display-preferences', methods=['POST'])
@login_required
def save_display_preferences():
    """Save user display preferences for folder view"""
    from blueprints.p2.models import User
    
    data = request.get_json()
    # Debug: log incoming payload
    #print('[save_display_preferences] Incoming request content_type:', request.content_type)
    #print('[save_display_preferences] Raw JSON payload:', data)
    if not data:
        print('[save_display_preferences] No data provided in request')
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Get current user preferences or initialize
    user_prefs = current_user.user_prefs or {}

    # Update display preferences (merge incoming keys)
    if 'display' not in user_prefs:
        user_prefs['display'] = {}

    # Make a shallow copy for debug comparison
    before_display = dict(user_prefs.get('display', {}))
    #print(f"[save_display_preferences] user_prefs before update (display): {before_display}")

    # Update individual settings with type coercion and debug prints
    if 'columns' in data:
        try:
            user_prefs['display']['columns'] = int(data['columns'])
            #print(f"[save_display_preferences] Set columns -> {user_prefs['display']['columns']}")
        except Exception as e:
            print('[save_display_preferences] Failed to parse columns:', data.get('columns'), 'error:', e)
    if 'view_mode' in data:
        user_prefs['display']['view_mode'] = data['view_mode']
        #print(f"[save_display_preferences] Set view_mode -> {user_prefs['display']['view_mode']}")
    if 'card_size' in data:
        user_prefs['display']['card_size'] = data['card_size']
        #print(f"[save_display_preferences] Set card_size -> {user_prefs['display']['card_size']}")
    if 'show_previews' in data:
        # handle string booleans too
        val = data['show_previews']
        if isinstance(val, str):
            val_l = val.lower()
            parsed = val_l in ['1', 'true', 'yes', 'on']
        else:
            parsed = bool(val)
        user_prefs['display']['show_previews'] = parsed
        #print(f"[save_display_preferences] Set show_previews -> {user_prefs['display']['show_previews']}")

    after_display = dict(user_prefs.get('display', {}))
    #print(f"[save_display_preferences] user_prefs after update (display): {after_display}")

    # Save to database
    try:
        #print('[save_display_preferences] Attempting to save preferences to current_user and commit...')
        # Ensure we assign a fresh object so SQLAlchemy detects the change
        try:
            import copy
            prefs_to_save = copy.deepcopy(user_prefs)
        except Exception:
            # Fallback to JSON round-trip if deepcopy fails for any reason
            import json
            prefs_to_save = json.loads(json.dumps(user_prefs))

        current_user.user_prefs = prefs_to_save
        # Flag modified to ensure SQLAlchemy sees the JSON column change
        try:
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(current_user, 'user_prefs')
            #print('[save_display_preferences] flag_modified called for user_prefs')
        except Exception as e:
            print('[save_display_preferences] flag_modified failed:', e)
        #print('[save_display_preferences] Assigned prefs_to_save (id={}): {}'.format(id(prefs_to_save), prefs_to_save))
        db.session.commit()
        #print('[save_display_preferences] Commit successful')
        # Refresh current_user from db to reflect persisted state
        try:
            from sqlalchemy import inspect
            db.session.refresh(current_user)
            #print('[save_display_preferences] Refreshed current_user from DB')
        except Exception as e:
            print('[save_display_preferences] Could not refresh current_user:', e)

            # Also explicitly re-query the user to guarantee we read DB value
        try:
            from blueprints.p2.models import User
            user_from_db = User.query.get(current_user.id)
            if user_from_db is not None:
                print('[save_display_preferences] Queried user_from_db.user_prefs:', user_from_db.user_prefs)
            else:
                print('[save_display_preferences] Queried user_from_db is None')
        except Exception as e:
            print('[save_display_preferences] Could not query user from DB:', e)

        #print('[save_display_preferences] Persisted user_prefs (current_user):', current_user.user_prefs)
        return jsonify({'success': True, 'message': 'Display preferences saved', 'preferences': current_user.user_prefs.get('display')})
    except Exception as e:
        import traceback
        print('[save_display_preferences] Exception during save/commit:', str(e))
        traceback.print_exc()
        try:
            db.session.rollback()
            print('[save_display_preferences] Rolled back session after exception')
        except Exception as rb_err:
            print('[save_display_preferences] Exception during rollback:', rb_err)
        return jsonify({'success': False, 'message': str(e)}), 500


@folder_bp.route('/api/folder-tree', methods=['GET'])
@login_required
def get_folder_tree():
    """Get complete folder tree structure for the folder browser"""
    
    def build_tree_recursive(folder):
        """Recursively build folder tree with counts"""
        children_data = []
        for child in sorted(folder.children, key=lambda x: x.name.lower()):
            children_data.append(build_tree_recursive(child))
        
        folder_data = {
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'children': children_data,
            'note_count': len(folder.notes),
            'board_count': len(folder.boards),
            'subfolder_count': len(folder.children),
            'created_at': folder.created_at.isoformat() if folder.created_at else None
        }
        
        return folder_data
    
    # Get all root folders (folders with no parent) for current user
    root_folders = Folder.query.filter(
        Folder.user_id == current_user.id,
        or_(Folder.parent_id == None, Folder.parent_id == 0)
    ).order_by(Folder.name).all()
    
    tree_data = []
    for root in root_folders:
        tree_data.append(build_tree_recursive(root))
    
    total_folders = Folder.query.filter_by(user_id=current_user.id).count()
    
    return jsonify({
        'success': True,
        'folders': tree_data,
        'total_count': total_folders,
        'user_id': current_user.id,
        'username': current_user.username
    })


@folder_bp.route('/api/folder/<int:folder_id>', methods=['GET'])
@login_required
def get_folder_api(folder_id):
    """Return minimal folder details as JSON (used by client-side UI)."""
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    return jsonify({
        'success': True,
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'description': folder.description
        }
    })


@folder_bp.route('/api/picker/folders_and_files', methods=['GET'])
@login_required
def get_folders_and_files_for_picker():
    """Get folder hierarchy with files for picker modal."""
    
    def build_folder_with_files(folder):
        """Recursively build folder tree with files."""
        children_data = []
        for child in sorted(folder.children, key=lambda x: x.name.lower()):
            children_data.append(build_folder_with_files(child))
        
        # Get files in this folder
        files = File.query.filter_by(
            owner_id=current_user.id,
            folder_id=folder.id
        ).order_by(File.title).all()
        
        files_data = [{
            'id': f.id,
            'title': f.title,
            'type': f.type,
            'created_at': f.created_at.isoformat() if f.created_at else None
        } for f in files]
        
        return {
            'id': folder.id,
            'name': folder.name,
            'parent_id': folder.parent_id,
            'children': children_data,
            'files': files_data
        }
    
    # Get root folders for current user
    root_folders = Folder.query.filter_by(
        user_id=current_user.id,
        parent_id=None
    ).order_by(Folder.name).all()
    
    tree_data = [build_folder_with_files(root) for root in root_folders]

    # Files placed directly in the root (no parent folder)
    root_files = File.query.filter(
        File.owner_id == current_user.id,
        or_(File.folder_id == None, File.folder_id == 0)
    ).order_by(File.title).all()

    # Defensive: if the above returned empty, attempt a second pass without the folder filter
    # to catch any legacy rows that may carry unexpected sentinel values.
    if not root_files:
        root_files = File.query.filter_by(owner_id=current_user.id).filter(
            or_(File.folder_id == None, File.folder_id == 0)
        ).order_by(File.title).all()

    root_files_data = [{
        'id': f.id,
        'title': f.title,
        'type': f.type,
        'created_at': f.created_at.isoformat() if f.created_at else None
    } for f in root_files]
    
    return jsonify({
        'success': True,
        'folders': tree_data,
        'root_files': root_files_data
    })


@folder_bp.route('/api/folder/<int:folder_id>/size', methods=['GET'])
@login_required
def calculate_folder_size(folder_id):
    """Calculate total size of a folder recursively (all notes, boards, and subfolders)."""
    folder = Folder.query.get_or_404(folder_id)
    if folder.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    
    def format_bytes(bytes_size):
        """Convert bytes to human-readable format."""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.2f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.2f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
    
    def calculate_recursive(folder):
        """Recursively calculate total size of folder and its descendants."""
        total_size = 0
        item_counts = {'notes': 0, 'boards': 0, 'subfolders': 0}
        
        # Add size from notes in this folder
        for note in folder.notes:
            total_size += len(note.content or '')
            item_counts['notes'] += 1
        
        # Add size from boards in this folder
        for board in folder.boards:
            total_size += len(board.content or '')
            item_counts['boards'] += 1
        
        # Recursively add size from subfolders
        for subfolder in folder.children:
            subfolder_size, subfolder_counts = calculate_recursive(subfolder)
            total_size += subfolder_size
            item_counts['notes'] += subfolder_counts['notes']
            item_counts['boards'] += subfolder_counts['boards']
            item_counts['subfolders'] += subfolder_counts['subfolders'] + 1
        
        return total_size, item_counts
    
    total_bytes, counts = calculate_recursive(folder)
    
    return jsonify({
        'success': True,
        'folder_id': folder_id,
        'folder_name': folder.name,
        'total_bytes': total_bytes,
        'formatted_size': format_bytes(total_bytes),
        'counts': counts
    })


@folder_bp.route('/<int:folder_id>/preview', methods=['GET'])
@login_required
def folder_preview(folder_id):
    """Lightweight preview for folder contents (first few children only)."""
    folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first_or_404()

    limit = request.args.get('limit', 8, type=int) or 8
    limit = max(1, min(limit, 50))

    # Pull minimal columns to avoid heavy loads for previews
    subfolders = (
        Folder.query.options(load_only(Folder.id, Folder.name, Folder.last_modified, Folder.created_at))
        .filter_by(parent_id=folder.id, user_id=current_user.id)
        .order_by(Folder.last_modified.desc())
        .limit(limit + 1)
        .all()
    )

    files = (
        File.query.options(load_only(File.id, File.title, File.type, File.last_modified, File.created_at))
        .filter_by(folder_id=folder.id, owner_id=current_user.id)
        .order_by(File.last_modified.desc())
        .limit(limit + 1)
        .all()
    )

    items = []
    for f in subfolders:
        ts = f.last_modified or f.created_at or datetime.utcnow()
        items.append({
            'id': f.id,
            'type': 'folder',
            'name': f.name,
            'last_modified': ts.isoformat()
        })

    for file_obj in files:
        ts = file_obj.last_modified or file_obj.created_at or datetime.utcnow()
        items.append({
            'id': file_obj.id,
            'type': file_obj.type,
            'name': file_obj.title,
            'last_modified': ts.isoformat()
        })

    # Sort combined list by last modified and trim to limit
    items.sort(key=lambda x: x['last_modified'], reverse=True)
    more_count = max(len(items) - limit, 0)
    items = items[:limit]

    return jsonify({
        'success': True,
        'items': items,
        'more_count': more_count
    })


@folder_bp.route('/api/item_metadata', methods=['GET'])
@login_required
def get_item_metadata():
    """Return created/modified timestamps and size info for preview panel."""
    requested_type = (request.args.get('type') or '').strip().lower()
    item_id = request.args.get('id', type=int)

    if not requested_type or not item_id:
        return jsonify({'success': False, 'message': 'Missing parameters'}), 400

    if requested_type == 'folder':
        item = Folder.query.filter_by(id=item_id, user_id=current_user.id).first()
        if not item:
            return jsonify({'success': False, 'message': 'Folder not found'}), 404
        created_at = item.created_at
        last_modified = item.last_modified
        size_bytes = sum(
            file_obj.get_content_size()
            for file_obj in item.files
            if hasattr(file_obj, 'get_content_size')
        )
    else:
        file_obj = File.query.filter_by(id=item_id, owner_id=current_user.id).first()
        if not file_obj:
            return jsonify({'success': False, 'message': 'File not found'}), 404
        created_at = file_obj.created_at
        last_modified = file_obj.last_modified
        size_bytes = file_obj.get_content_size() if hasattr(file_obj, 'get_content_size') else 0

    def _iso(dt):
        return dt.isoformat() if dt else None

    return jsonify({
        'success': True,
        'data': {
            'id': item_id,
            'type': requested_type,
            'created_at': _iso(created_at),
            'last_modified': _iso(last_modified),
            'size_bytes': size_bytes,
            'size_display': format_bytes(size_bytes) if size_bytes is not None else None
        }
    })


@folder_bp.route('/batch_paste', methods=['POST'])
@login_required
def batch_paste_route():
    """Batch paste operation for multiple items (cut or copy)"""
    from blueprints.p2.utils import add_notification
    
    try:
        items_json = request.form.get('items')
        action = request.form.get('action')  # 'cut' or 'copy'
        target_folder_id = request.form.get('target_folder')
        
        if not items_json or not action or not target_folder_id:
            return jsonify({'success': False, 'message': 'Missing parameters'}), 400
        
        items = json.loads(items_json)
        target_folder_id = int(target_folder_id)
        
        # Verify target folder ownership
        target_folder = Folder.query.get(target_folder_id)
        if not target_folder or target_folder.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Invalid target folder'}), 403
        
        success_count = 0
        failed_items = []
        
        alias_map = {
            'note': 'proprietary_note',
            'board': 'proprietary_whiteboard',
            'whiteboard': 'proprietary_whiteboard',
        }

        for item in items:
            raw_type = item.get('type')
            item_type = alias_map.get(raw_type, raw_type)
            item_id = item.get('id')
            
            try:
                if action == 'cut':
                    # Move operation
                    if item_type == 'folder':
                        if move_folder(item_id, target_folder_id):
                            success_count += 1
                        else:
                            failed_items.append(f"folder {item_id}")
                    elif item_type == 'proprietary_note':
                        note = File.query.filter_by(id=item_id, type='proprietary_note').first()
                        if note and note.owner_id == current_user.id:
                            note.folder_id = target_folder_id
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"note {item_id}")
                    elif item_type == 'proprietary_whiteboard':
                        board = File.query.filter_by(id=item_id, type='proprietary_whiteboard').first()
                        if board and board.owner_id == current_user.id:
                            board.folder_id = target_folder_id
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"board {item_id}")
                    elif item_type in ['file', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph', 'timeline', 'markdown', 'todo', 'diagram', 'table', 'blocks', 'code', 'pdf']:
                        # Handle both generic 'file' type and specific 'book' type (MioBooks are Files with type='proprietary_blocks')
                        file_obj = File.query.get(item_id)
                        if file_obj and file_obj.owner_id == current_user.id:
                            file_obj.folder_id = target_folder_id
                            file_obj.last_modified = datetime.utcnow()
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"{item_type} {item_id}")
                            
                elif action == 'copy':
                    # Copy/duplicate operation
                    if item_type == 'folder':
                        if copy_folder_recursive(item_id, target_folder_id):
                            success_count += 1
                        else:
                            failed_items.append(f"folder {item_id}")
                    elif item_type == 'proprietary_note':
                        original = File.query.filter_by(id=item_id, type='proprietary_note').first()
                        if original and original.owner_id == current_user.id:
                            # Check guest limit
                            content_size = original.get_content_size()
                            if getattr(current_user, 'user_type', None) == 'guest':
                                max_size = 50 * 1024 * 1024
                                if (current_user.total_data_size or 0) + content_size > max_size:
                                    failed_items.append(f"note {item_id} (quota exceeded)")
                                    continue
                            
                            new_note = File(
                                title=(original.title or '') + ' (copy)',
                                type='proprietary_note',
                                content_html=original.content_html,
                                metadata_json=original.metadata_json.copy() if original.metadata_json else {},
                                owner_id=current_user.id,
                                folder_id=target_folder_id
                            )
                            db.session.add(new_note)
                            db.session.commit()
                            current_user.total_data_size = (current_user.total_data_size or 0) + content_size
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"note {item_id}")
                    elif item_type == 'proprietary_whiteboard':
                        original = File.query.filter_by(id=item_id, type='proprietary_whiteboard').first()
                        if original and original.owner_id == current_user.id:
                            # Check guest limit
                            content_size = original.get_content_size()
                            if getattr(current_user, 'user_type', None) == 'guest':
                                max_size = 50 * 1024 * 1024
                                if (current_user.total_data_size or 0) + content_size > max_size:
                                    failed_items.append(f"board {item_id} (quota exceeded)")
                                    continue
                            
                            new_board = File(
                                title=(original.title or '') + ' (copy)',
                                type='proprietary_whiteboard',
                                content_json=original.content_json,
                                metadata_json=original.metadata_json.copy() if original.metadata_json else {},
                                owner_id=current_user.id,
                                folder_id=target_folder_id
                            )
                            db.session.add(new_board)
                            db.session.commit()
                            current_user.total_data_size = (current_user.total_data_size or 0) + content_size
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"board {item_id}")
                    elif item_type in ['file', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph', 'timeline', 'markdown', 'todo', 'diagram', 'table', 'blocks', 'code', 'pdf']:
                        # Handle all file types
                        original = File.query.get(item_id)
                        if original and original.owner_id == current_user.id:
                            # Check guest limit
                            content_size = original.get_content_size()
                            if getattr(current_user, 'user_type', None) == 'guest':
                                max_size = 50 * 1024 * 1024
                                if (current_user.total_data_size or 0) + content_size > max_size:
                                    failed_items.append(f"{item_type} {item_id} (quota exceeded)")
                                    continue
                            
                            new_file = File(
                                owner_id=current_user.id,
                                folder_id=target_folder_id,
                                type=original.type,
                                title=(original.title or '') + ' (copy)',
                                content_text=original.content_text,
                                content_html=original.content_html,
                                content_json=original.content_json,
                                content_blob=original.content_blob,
                                metadata_json=original.metadata_json.copy() if original.metadata_json else {},
                                is_public=False
                            )
                            db.session.add(new_file)
                            db.session.commit()
                            current_user.total_data_size = (current_user.total_data_size or 0) + content_size
                            db.session.commit()
                            success_count += 1
                        else:
                            failed_items.append(f"{item_type} {item_id}")
            except Exception as e:
                print(f"Error processing {item_type} {item_id}: {e}")
                failed_items.append(f"{item_type} {item_id}")
                continue
        
        message = f"Successfully processed {success_count} items"
        if failed_items:
            message += f". Failed: {', '.join(failed_items)}"
        
        # Add notification for batch operation
        operation_type = 'cut' if action == 'cut' else 'copy'
        notif_msg = f"Batch {operation_type}: {success_count} items to '{target_folder.name}'"
        if failed_items:
            notif_msg += f" ({len(failed_items)} failed)"
        add_notification(current_user.id, notif_msg, 'transfer')
        
        # Fetch the pasted items to return their HTML for AJAX insertion
        pasted_items = {
            'folders': [],
            'notes': [],
            'boards': [],
            'files': []
        }
        
        if action == 'copy':
            # For copy operations, we need to fetch the newly created items
            # Get items created in the target folder in the last few seconds
            for item in items:
                item_type = item.get('type')
                if item_type == 'folder':
                    # Get latest subfolder in target
                    latest = Folder.query.filter_by(
                        user_id=current_user.id,
                        parent_id=target_folder_id
                    ).order_by(Folder.created_at.desc()).first()
                    if latest:
                        pasted_items['folders'].append(latest)
                elif item_type == 'proprietary_note':
                    latest = File.query.filter_by(
                        owner_id=current_user.id,
                        folder_id=target_folder_id,
                        type='proprietary_note'
                    ).order_by(File.created_at.desc()).first()
                    if latest:
                        pasted_items['notes'].append(latest)
                elif item_type == 'proprietary_whiteboard':
                    latest = File.query.filter_by(
                        owner_id=current_user.id,
                        folder_id=target_folder_id,
                        type='proprietary_whiteboard'
                    ).order_by(File.created_at.desc()).first()
                    if latest:
                        pasted_items['boards'].append(latest)
                elif item_type in ['file', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph', 'timeline', 'markdown', 'todo', 'diagram', 'table', 'blocks', 'code', 'pdf']:
                    latest = File.query.filter_by(
                        owner_id=current_user.id,
                        folder_id=target_folder_id
                    ).order_by(File.created_at.desc()).first()
                    if latest:
                        pasted_items['files'].append(latest)
        
        # Render HTML for each pasted item
        from flask import render_template_string
        pasted_html = {
            'folders': [],
            'notes': [],
            'boards': [],
            'files': []
        }
        
        # Get display preferences
        display_prefs = current_user.user_prefs.get('display', {
            'columns': 3,
            'view_mode': 'grid',
            'card_size': 'normal',
            'show_previews': True
        }) if current_user.user_prefs else {
            'columns': 3,
            'view_mode': 'grid',
            'card_size': 'normal',
            'show_previews': True
        }
        
        for folder in pasted_items['folders']:
            html = render_template('p2/partials/folder_card.html', folder=folder, display_prefs=display_prefs)
            pasted_html['folders'].append(html)
        
        # Use type-specific card partials for all file types (notes, boards, files)
        for note in pasted_items['notes']:
            partial = get_file_card_partial(note.type)
            html = render_template(partial, file=note, display_prefs=display_prefs)
            pasted_html['notes'].append(html)
        
        for board in pasted_items['boards']:
            partial = get_file_card_partial(board.type)
            html = render_template(partial, file=board, display_prefs=display_prefs)
            pasted_html['boards'].append(html)
        
        for file_obj in pasted_items['files']:
            partial = get_file_card_partial(file_obj.type)
            html = render_template(partial, file=file_obj, display_prefs=display_prefs)
            pasted_html['files'].append(html)
        
        # Build response
        response_data = {
            'success': True,
            'message': message,
            'success_count': success_count,
            'failed_count': len(failed_items),
            'failed_items': failed_items,
            'pasted_html': pasted_html
        }
        
        # HTMX support: return array of HTML fragments for dynamic insertion
        if request.form.get('htmx') == 'true':
            new_items_html = []
            
            # Add folders
            for folder in pasted_items['folders']:
                html = render_template('p2/partials/folder_card.html', sub=folder, display_prefs=display_prefs)
                new_items_html.append({
                    'html': html,
                    'type': 'folder',
                    'id': folder.id
                })
            
            # Add notes with type-specific card
            for note in pasted_items['notes']:
                partial = get_file_card_partial(note.type)
                html = render_template(partial, file=note, display_prefs=display_prefs)
                new_items_html.append({
                    'html': html,
                    'type': 'file',  # Use 'file' for JS compatibility
                    'id': note.id
                })
            
            # Add boards with type-specific card
            for board in pasted_items['boards']:
                partial = get_file_card_partial(board.type)
                html = render_template(partial, file=board, display_prefs=display_prefs)
                new_items_html.append({
                    'html': html,
                    'type': 'file',  # Use 'file' for JS compatibility
                    'id': board.id
                })
            
            # Add files with type-specific card
            for file_obj in pasted_items['files']:
                partial = get_file_card_partial(file_obj.type)
                html = render_template(partial, file=file_obj, display_prefs=display_prefs)
                new_items_html.append({
                    'html': html,
                    'type': 'file',  # Use 'file' for JS compatibility
                    'id': file_obj.id
                })
            
            response_data['new_items_html'] = new_items_html
        
        return jsonify(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Batch paste failed: {str(e)}'}), 500


@folder_bp.route('/batch_delete', methods=['POST'])
@login_required
def batch_delete_route():
    """Batch delete operation for multiple items"""
    try:
        items_json = request.form.get('items')
        if not items_json:
            return jsonify({'success': False, 'message': 'Missing items parameter'}), 400
        
        items = json.loads(items_json)
        success_count = 0
        failed_items = []
        total_size_freed = 0
        deleted_items_info = []  # Track deleted items for notifications
        
        for item in items:
            item_type = item.get('type')
            item_id = item.get('id')
            
            try:
                if item_type == 'folder':
                    folder = Folder.query.get(item_id)
                    if not folder:
                        failed_items.append(f"folder {item_id}: not found")
                        continue
                    
                    folder_name = folder.name
                    # Calculate size to subtract
                    def calculate_folder_size_recursive(f):
                        size = 0
                        for file_obj in f.files:
                            size += file_obj.get_content_size()
                        for child in f.children:
                            size += calculate_folder_size_recursive(child)
                        return size
                    
                    size_to_subtract = calculate_folder_size_recursive(folder)
                    success, reason = delete_folder(item_id, acting_user=current_user, with_reason=True)
                    if success:
                        total_size_freed += size_to_subtract
                        success_count += 1
                        deleted_items_info.append(('folder', folder_name, size_to_subtract))
                    else:
                        failed_items.append(f"folder {item_id}: {reason or 'unknown error'}")
                        
                elif item_type == 'proprietary_note':
                    note = File.query.filter(
                        File.id == item_id,
                        File.owner_id == current_user.id,
                        File.type.in_(['proprietary_note', 'note'])
                    ).first()
                    if note:
                        note_title = note.title
                        size = note.get_content_size()
                        db.session.delete(note)
                        db.session.commit()
                        total_size_freed += size
                        success_count += 1
                        deleted_items_info.append((note.type, note_title, size))
                    else:
                        failed_items.append(f"note {item_id}")
                        
                elif item_type == 'proprietary_whiteboard':
                    board = File.query.filter(
                        File.id == item_id,
                        File.owner_id == current_user.id,
                        File.type.in_(['proprietary_whiteboard', 'board', 'whiteboard'])
                    ).first()
                    if board:
                        board_title = board.title
                        size = board.get_content_size()
                        db.session.delete(board)
                        db.session.commit()
                        total_size_freed += size
                        success_count += 1
                        deleted_items_info.append((board.type, board_title, size))
                    else:
                        failed_items.append(f"board {item_id}")
                        
                elif item_type in ['file', 'book', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph', 'timeline', 'markdown', 'todo', 'diagram', 'table', 'blocks', 'code', 'pdf']:
                    # Handle all file types (markdown, todo, diagram, table, blocks, code, book, etc.)
                    file_obj = File.query.filter_by(id=item_id, owner_id=current_user.id).first()
                    if file_obj:
                        file_title = file_obj.title
                        file_actual_type = file_obj.type  # Get actual type from File model
                        size = file_obj.get_content_size()
                        delete_file_with_graph_cleanup(file_obj)
                        db.session.commit()
                        total_size_freed += size
                        success_count += 1
                        deleted_items_info.append((file_actual_type, file_title, size))
                    else:
                        failed_items.append(f"{item_type} {item_id}")
                else:
                    # Fallback: attempt deletion for any legacy/unknown file types
                    file_obj = File.query.filter_by(id=item_id, owner_id=current_user.id).first()
                    if file_obj:
                        file_title = file_obj.title
                        file_actual_type = file_obj.type
                        size = file_obj.get_content_size()
                        db.session.delete(file_obj)
                        db.session.commit()
                        total_size_freed += size
                        success_count += 1
                        deleted_items_info.append((file_actual_type, file_title, size))
                    else:
                        failed_items.append(f"{item_type} {item_id}")
            except Exception as e:
                print(f"Error deleting {item_type} {item_id}: {e}")
                failed_items.append(f"{item_type} {item_id}: {e}")
                continue
        
        # Update user data size
        if total_size_freed > 0:
            current_user.total_data_size = (current_user.total_data_size or 0) - total_size_freed
            db.session.commit()
        
        # Clean up orphaned images
        from .utils import cleanup_orphaned_images_for_user
        try:
            deleted_count, freed_bytes = cleanup_orphaned_images_for_user(current_user.id)
            if deleted_count > 0:
                print(f"[BATCH DELETE] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
        except Exception as e:
            print(f"[BATCH DELETE] Image cleanup failed: {e}")
        
        # Add notifications for deleted items
        from .utils import add_notification, format_bytes
        for item_type, item_title, item_size in deleted_items_info:
            # Create user-friendly type names
            type_display = {
                'proprietary_note': 'note',
                'proprietary_whiteboard': 'board',
                'proprietary_blocks': 'book',
                'proprietary_infinite_whiteboard': 'infinite board',
                'proprietary_graph': 'graph workspace',
                'markdown': 'markdown',
                'todo': 'todo',
                'diagram': 'diagram',
                'table': 'table',
                'blocks': 'blocks',
                'code': 'code'
            }.get(item_type, item_type)
            
            notif_msg = f"Deleted {type_display}: {item_title} ({format_bytes(item_size)} freed)"
            add_notification(current_user.id, notif_msg, 'delete')
        
        message = f"Successfully deleted {success_count} items"
        if failed_items:
            message += f". Failed: {', '.join(failed_items)}"
        
        return jsonify({
            'success': len(failed_items) == 0,
            'message': message,
            'success_count': success_count,
            'failed_count': len(failed_items),
            'failed_items': failed_items
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Batch delete failed: {str(e)}'}), 500


@folder_bp.route('/batch_set_public', methods=['POST'])
@login_required
def batch_set_public_route():
    """Batch set public operation for multiple items"""
    print(f"\n[BATCH SET PUBLIC] Route called by user {current_user.id}")
    try:
        items_json = request.form.get('items')
        print(f"[BATCH SET PUBLIC] Items JSON: {items_json}")
        if not items_json:
            print("[BATCH SET PUBLIC] ERROR: Missing items parameter")
            return jsonify({'success': False, 'message': 'Missing items parameter'}), 400
        
        items = json.loads(items_json)
        print(f"[BATCH SET PUBLIC] Parsed items: {items}")
        success_count = 0
        failed_items = []
        
        for item in items:
            item_type = item.get('type')
            item_id = item.get('id')
            print(f"[BATCH SET PUBLIC] Processing {item_type} {item_id}")
            
            try:
                if item_type == 'folder':
                    folder = Folder.query.get(item_id)
                    if folder and folder.user_id == current_user.id:
                        print(f"[BATCH SET PUBLIC] Setting folder {item_id} as public")
                        # Recursively set folder and all contents as public
                        def set_folder_public_recursive(f):
                            f.is_public = True
                            for file_obj in f.files:
                                file_obj.is_public = True
                            for child in f.children:
                                set_folder_public_recursive(child)
                        
                        set_folder_public_recursive(folder)
                        db.session.commit()
                        print(f"[BATCH SET PUBLIC] Folder {item_id} committed as public")
                        success_count += 1
                    else:
                        print(f"[BATCH SET PUBLIC] Folder {item_id} not found or access denied")
                        failed_items.append(f"folder {item_id}")
                        
                else:
                    # All non-folder items are Files
                    file_obj = File.query.get(item_id)
                    if file_obj and file_obj.owner_id == current_user.id:
                        print(f"[BATCH SET PUBLIC] Setting {item_type} {item_id} as public")
                        file_obj.is_public = True
                        db.session.commit()
                        print(f"[BATCH SET PUBLIC] {item_type.capitalize()} {item_id} committed as public")
                        success_count += 1
                    else:
                        print(f"[BATCH SET PUBLIC] {item_type} {item_id} not found or access denied")
                        failed_items.append(f"{item_type} {item_id}")
            except Exception as e:
                print(f"[BATCH SET PUBLIC] Error setting {item_type} {item_id} as public: {e}")
                import traceback
                traceback.print_exc()
                failed_items.append(f"{item_type} {item_id}")
                db.session.rollback()
                continue
        
        message = f"Successfully set {success_count} items as public"
        if failed_items:
            message += f". Failed: {', '.join(failed_items)}"
        
        print(f"[BATCH SET PUBLIC] Complete. Success: {success_count}, Failed: {len(failed_items)}")
        return jsonify({
            'success': True,
            'message': message,
            'success_count': success_count,
            'failed_count': len(failed_items),
            'failed_items': failed_items
        })
        
    except Exception as e:
        import traceback
        print(f"[BATCH SET PUBLIC] Fatal error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Batch set public failed: {str(e)}'}), 500


@folder_bp.route('/batch_toggle_pin', methods=['POST'])
@login_required
def batch_toggle_pin_route():
    """Batch toggle pin operation for multiple files"""
    # print(f"\n[BATCH TOGGLE PIN] Route called by user {current_user.id}")
    try:
        from sqlalchemy.orm.attributes import flag_modified
        
        items_json = request.form.get('items')
        # print(f"[BATCH TOGGLE PIN] Items JSON: {items_json}")
        if not items_json:
            # print("[BATCH TOGGLE PIN] ERROR: Missing items parameter")
            return jsonify({'success': False, 'message': 'Missing items parameter'}), 400
        
        items = json.loads(items_json)
        # print(f"[BATCH TOGGLE PIN] Parsed items: {items}")
        success_count = 0
        failed_items = []
        pinned_count = 0
        unpinned_count = 0
        
        for item in items:
            item_type = item.get('type')
            item_id = item.get('id')
            # print(f"[BATCH TOGGLE PIN] Processing {item_type} {item_id}")
            
            try:
                file_obj = None
                
                # Map item types to File queries - all use File model now
                if item_type == 'folder':
                    # Skip folders - they don't support pinning
                    # print(f"[BATCH TOGGLE PIN] Skipping folder {item_id} - folders cannot be pinned")
                    continue
                
                # All items are Files - just get by ID and verify ownership
                file_obj = File.query.get(item_id)
                
                if not file_obj:
                    # print(f"[BATCH TOGGLE PIN] File {item_id} not found")
                    failed_items.append(f"{item_type} {item_id}")
                    continue
                
                if file_obj and file_obj.owner_id == current_user.id:
                    # Initialize metadata_json if None
                    if file_obj.metadata_json is None:
                        file_obj.metadata_json = {}
                    
                    # Toggle pin state
                    current_pin_state = file_obj.metadata_json.get('is_pinned', False)
                    new_pin_state = not current_pin_state
                    file_obj.metadata_json['is_pinned'] = new_pin_state
                    
                    # CRITICAL: Flag modified for SQLAlchemy to detect JSON changes
                    flag_modified(file_obj, 'metadata_json')
                    
                    # print(f"[BATCH TOGGLE PIN] Toggling {item_type} {item_id}: {current_pin_state} -> {new_pin_state}")
                    
                    if new_pin_state:
                        pinned_count += 1
                    else:
                        unpinned_count += 1
                    
                    success_count += 1
                else:
                    # print(f"[BATCH TOGGLE PIN] {item_type} {item_id} not found or access denied")
                    failed_items.append(f"{item_type} {item_id}")
            
            except Exception as e:
                # print(f"[BATCH TOGGLE PIN] Error toggling pin for {item_type} {item_id}: {e}")
                import traceback
                traceback.print_exc()
                failed_items.append(f"{item_type} {item_id}")
                db.session.rollback()
                continue
        
        # Commit all changes at once
        if success_count > 0:
            db.session.commit()
            # print(f"[BATCH TOGGLE PIN] Committed {success_count} changes")
        
        # Build message
        message_parts = []
        if pinned_count > 0:
            message_parts.append(f"Pinned {pinned_count} item{'s' if pinned_count > 1 else ''}")
        if unpinned_count > 0:
            message_parts.append(f"Unpinned {unpinned_count} item{'s' if unpinned_count > 1 else ''}")
        
        message = ", ".join(message_parts) if message_parts else "No changes made"
        
        if failed_items:
            message += f". Failed: {', '.join(failed_items)}"
        
        # print(f"[BATCH TOGGLE PIN] Complete. Success: {success_count}, Failed: {len(failed_items)}")
        return jsonify({
            'success': True,
            'message': message,
            'success_count': success_count,
            'failed_count': len(failed_items),
            'pinned_count': pinned_count,
            'unpinned_count': unpinned_count
        })
    
    except Exception as e:
        db.session.rollback()
        import traceback
        # print(f"[BATCH TOGGLE PIN] Fatal error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Batch toggle pin failed: {str(e)}'}), 500


@folder_bp.route('/batch_toggle_pin_htmx', methods=['POST'])
@login_required
def batch_toggle_pin_htmx():
    """HTMX version of batch_toggle_pin that returns rearranged HTML partials"""
    print("\n" + "="*80)
    print("[BATCH PIN HTMX] Route called")
    print(f"[BATCH PIN HTMX] User: {current_user.id}")
    print(f"[BATCH PIN HTMX] Request method: {request.method}")
    print(f"[BATCH PIN HTMX] Request form: {request.form}")
    print(f"[BATCH PIN HTMX] Request headers: {dict(request.headers)}")
    print("="*80 + "\n")
    
    try:
        from sqlalchemy.orm.attributes import flag_modified
        
        items_json = request.form.get('items')
        folder_id = request.form.get('folder_id')
        
        print(f"[BATCH PIN HTMX] items_json: {items_json}")
        print(f"[BATCH PIN HTMX] folder_id: {folder_id}")
        
        if not items_json:
            print("[BATCH PIN HTMX] ERROR: Missing items parameter")
            return '<div class="alert alert-danger">Missing items parameter</div>', 400
        
        if not folder_id:
            print("[BATCH PIN HTMX] ERROR: Missing folder_id parameter")
            return '<div class="alert alert-danger">Missing folder_id parameter</div>', 400
        
        items = json.loads(items_json)
        folder_id = int(folder_id)
        
        print(f"[BATCH PIN HTMX] Parsed items: {items}")
        print(f"[BATCH PIN HTMX] Parsed folder_id: {folder_id}")
        print(f"[BATCH PIN HTMX] Number of items to process: {len(items)}")
        
        # Verify folder access
        folder = Folder.query.get_or_404(folder_id)
        print(f"[BATCH PIN HTMX] Folder found: {folder.name} (ID: {folder.id})")
        if folder.user_id != current_user.id:
            print(f"[BATCH PIN HTMX] ERROR: Access denied - folder owner {folder.user_id} != current user {current_user.id}")
            return '<div class="alert alert-danger">Access denied</div>', 403
        
        success_count = 0
        pinned_count = 0
        unpinned_count = 0
        affected_sections = set()  # Track which sections need to be re-rendered
        
        print(f"[BATCH PIN HTMX] Starting to process {len(items)} items...")
        for idx, item in enumerate(items):
            print(f"\n[BATCH PIN HTMX] --- Processing item {idx + 1}/{len(items)} ---")
            item_type = item.get('type')
            item_id = item.get('id')
            
            print(f"[BATCH PIN HTMX] Item type: {item_type}, ID: {item_id}")
            
            try:
                file_obj = None
                
                # All items are Files - just get by ID
                if item_type == 'folder':
                    # Skip folders - they don't support pinning
                    continue
                
                print(f"[BATCH PIN HTMX] Querying file with ID {item_id}")
                file_obj = File.query.get(item_id)
                print(f"[BATCH PIN HTMX] File found: {file_obj is not None}")
                
                if file_obj:
                    # Track affected sections based on file type
                    if file_obj.type == 'proprietary_note':
                        affected_sections.add('notes')
                    elif file_obj.type == 'proprietary_whiteboard':
                        affected_sections.add('boards')
                    elif file_obj.type == 'proprietary_blocks':
                        affected_sections.add('combined')
                    else:
                        affected_sections.add(f'file_{file_obj.type}')
                
                if file_obj and file_obj.owner_id == current_user.id:
                    print(f"[BATCH PIN HTMX] File object valid, owner matches")
                    print(f"[BATCH PIN HTMX] Current metadata_json: {file_obj.metadata_json}")
                    
                    if file_obj.metadata_json is None:
                        file_obj.metadata_json = {}
                        print(f"[BATCH PIN HTMX] Initialized empty metadata_json")
                    
                    current_pin_state = file_obj.metadata_json.get('is_pinned', False)
                    new_pin_state = not current_pin_state
                    file_obj.metadata_json['is_pinned'] = new_pin_state
                    
                    print(f"[BATCH PIN HTMX] Pin state change: {current_pin_state} -> {new_pin_state}")
                    
                    flag_modified(file_obj, 'metadata_json')
                    print(f"[BATCH PIN HTMX] Flagged metadata_json as modified")
                    
                    if new_pin_state:
                        pinned_count += 1
                    else:
                        unpinned_count += 1
                    
                    success_count += 1
                    print(f"[BATCH PIN HTMX] Success count: {success_count}")
                elif file_obj:
                    print(f"[BATCH PIN HTMX] ERROR: Owner mismatch - file owner {file_obj.owner_id} != current user {current_user.id}")
                else:
                    print(f"[BATCH PIN HTMX] ERROR: File object not found for {item_type} {item_id}")
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.session.rollback()
                continue
        
        print(f"\n[BATCH PIN HTMX] Processing complete:")
        print(f"[BATCH PIN HTMX] - Success count: {success_count}")
        print(f"[BATCH PIN HTMX] - Pinned: {pinned_count}")
        print(f"[BATCH PIN HTMX] - Unpinned: {unpinned_count}")
        print(f"[BATCH PIN HTMX] - Affected sections: {affected_sections}")
        
        if success_count > 0:
            print(f"[BATCH PIN HTMX] Committing database changes...")
            db.session.commit()
            print(f"[BATCH PIN HTMX] Database commit successful")
        else:
            print(f"[BATCH PIN HTMX] No changes to commit")
        
        # Get sort parameter from session or request
        sort_by = request.args.get('sort', session.get('folder_sort_by', 'name'))
        print(f"[BATCH PIN HTMX] Sort by: {sort_by}")
        
        # Helper function to sort items (pinned first, then unpinned sorted)
        def sort_items(items, sort_by, item_type):
            """Sort items with pinned files appearing first, then unpinned files sorted normally."""
            if item_type in ['note', 'board', 'combined', 'file']:
                pinned = [item for item in items if hasattr(item, 'is_pinned') and item.is_pinned]
                unpinned = [item for item in items if not (hasattr(item, 'is_pinned') and item.is_pinned)]
            else:
                pinned = []
                unpinned = items
            
            # Pinned items ignore sort order (maintain insertion order)
            # Only sort unpinned items according to sort_by parameter
            if sort_by == 'name':
                if item_type == 'folder':
                    unpinned = sorted(unpinned, key=lambda x: x.name.lower())
                elif item_type in ['note', 'board', 'combined', 'file']:
                    unpinned = sorted(unpinned, key=lambda x: (x.title or '').lower())
            elif sort_by == 'created':
                unpinned = sorted(unpinned, key=lambda x: x.created_at or x.id)
            elif sort_by == 'modified':
                unpinned = sorted(unpinned, key=lambda x: x.last_modified or x.created_at or x.id, reverse=True)
            elif sort_by == 'size':
                if item_type == 'folder':
                    unpinned = sorted(unpinned, key=lambda x: len(x.notes) + len(x.boards) + len(x.children), reverse=True)
                elif item_type in ['note', 'board']:
                    unpinned = sorted(unpinned, key=lambda x: len(x.content_html or '') if item_type == 'note' else len(str(x.content_json or '')), reverse=True)
                elif item_type in ['combined', 'file']:
                    unpinned = sorted(unpinned, key=lambda x: x.get_content_size() if hasattr(x, 'get_content_size') else len(x.content or ''), reverse=True)
            
            return pinned + unpinned
        
        # Get user display preferences
        user_prefs = current_user.user_prefs or {}
        display_prefs = user_prefs.get('display', {})
        display_prefs.setdefault('columns', 3)
        display_prefs.setdefault('view_mode', 'grid')
        display_prefs.setdefault('card_size', 'normal')
        display_prefs.setdefault('show_previews', True)
        
        # Re-render affected sections with proper sorting
        html_parts = []
        
        # Notes section
        if 'notes' in affected_sections:
            notes = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_note').all()
            notes = sort_items(notes, sort_by, 'note')
            html_parts.append(render_template('p2/partials/notes_section_cards.html', 
                                            notes=notes, 
                                            display_prefs=display_prefs))
        
        # Boards section
        if 'boards' in affected_sections:
            boards = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_whiteboard').all()
            boards = sort_items(boards, sort_by, 'board')
            html_parts.append(render_template('p2/partials/boards_section_cards.html', 
                                            boards=boards, 
                                            display_prefs=display_prefs))
        
        # Combined/MioBook section
        if 'combined' in affected_sections:
            combined_docs = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_blocks').all()
            combined_docs = sort_items(combined_docs, sort_by, 'combined')
            html_parts.append(render_template('p2/partials/combined_section_cards.html', 
                                            combined_docs=combined_docs, 
                                            display_prefs=display_prefs))
        
        # File sections (markdown, todo, diagram, etc.)
        for section in affected_sections:
            if section.startswith('file_'):
                file_type = section.replace('file_', '')
                files = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type=file_type).all()
                files = sort_items(files, sort_by, 'file')
                html_parts.append(render_template('p2/partials/files_section_cards.html', 
                                                files=files, 
                                                file_type=file_type,
                                                display_prefs=display_prefs))
        
        # Build response with HTMX OOB (Out Of Band) swaps for multiple targets
        response_parts = []
        print(f"\n[BATCH PIN HTMX] Building HTML response...")
        
        # Notes section
        if 'notes' in affected_sections:
            print(f"[BATCH PIN HTMX] Rendering notes section...")
            notes = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_note').all()
            notes = sort_items(notes, sort_by, 'note')
            notes_html = render_template('p2/partials/notes_section_cards.html', 
                                        notes=notes, 
                                        display_prefs=display_prefs)
            response_parts.append(f'<div id="notes-grid" hx-swap-oob="innerHTML:#notes-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{notes_html}</div>')
        
        # Boards section
        if 'boards' in affected_sections:
            boards = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_whiteboard').all()
            boards = sort_items(boards, sort_by, 'board')
            boards_html = render_template('p2/partials/boards_section_cards.html', 
                                        boards=boards, 
                                        display_prefs=display_prefs)
            response_parts.append(f'<div id="boards-grid" hx-swap-oob="innerHTML:#boards-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{boards_html}</div>')
        
        # Combined/MioBook section
        if 'combined' in affected_sections:
            combined_docs = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_blocks').all()
            combined_docs = sort_items(combined_docs, sort_by, 'combined')
            combined_html = render_template('p2/partials/combined_section_cards.html', 
                                          combined_docs=combined_docs, 
                                          display_prefs=display_prefs)
            response_parts.append(f'<div id="combined-grid" hx-swap-oob="innerHTML:#combined-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{combined_html}</div>')
        
        # File sections (markdown, todo, diagram, etc.)
        for section in affected_sections:
            if section.startswith('file_'):
                file_type = section.replace('file_', '')
                files = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type=file_type).all()
                files = sort_items(files, sort_by, 'file')
                files_html = render_template('p2/partials/files_section_cards.html', 
                                           files=files, 
                                           file_type=file_type,
                                           display_prefs=display_prefs)
                response_parts.append(f'<div id="{file_type}-grid" hx-swap-oob="innerHTML:#{file_type}-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{files_html}</div>')
        
        # Add success notification to telemetry
        message_parts = []
        if pinned_count > 0:
            message_parts.append(f"Pinned {pinned_count}")
        if unpinned_count > 0:
            message_parts.append(f"Unpinned {unpinned_count}")
        message = ", ".join(message_parts) if message_parts else "No changes"
        
        # Add cleanup and notification script as OOB swap
        cleanup_script = f"""
        <div id="htmx-pin-notification" hx-swap-oob="true">
            <script>
            (function() {{
                if (window.TelemetryPanel) {{
                    window.TelemetryPanel.setIdle('{message}');
                }}

                // Re-attach listeners after swaps to keep single-item actions working
                setTimeout(() => {{
                    if (typeof window.attachCardClickListeners === 'function') {{
                        document.querySelectorAll('.item-card .item-body').forEach(body => {{
                            window.attachCardClickListeners(body);
                        }});
                    }}
                }}, 100);
            }})();
            </script>
        </div>
        """
        
        # Primary response (empty div as anchor)
        primary_response = '<div style="display:none;"></div>'
        
        # Combine all parts
        full_response = primary_response + '\n'.join(response_parts) + cleanup_script
        
        print(f"\n[BATCH PIN HTMX] Response ready:")
        print(f"[BATCH PIN HTMX] - Response parts: {len(response_parts)}")
        print(f"[BATCH PIN HTMX] - Response length: {len(full_response)} chars")
        print(f"[BATCH PIN HTMX] - Response preview (first 500 chars):")
        print(full_response[:500])
        print("\n" + "="*80)
        print("[BATCH PIN HTMX] Returning response to client")
        print("="*80 + "\n")
        
        return full_response
    
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"\n[BATCH PIN HTMX] *** EXCEPTION OCCURRED ***")
        print(f"[BATCH PIN HTMX] Error: {str(e)}")
        traceback.print_exc()
        print("\n")
        return f'<div class="alert alert-danger">Pin operation failed: {str(e)}</div>', 500


@folder_bp.route('/batch_toggle_public_htmx', methods=['POST'])
@login_required
def batch_toggle_public_htmx():
    """HTMX version of batch_toggle_public that returns rearranged HTML partials"""
    print("\n" + "="*80)
    print("[BATCH PUBLIC HTMX] Route called")
    print(f"[BATCH PUBLIC HTMX] User: {current_user.id}")
    print(f"[BATCH PUBLIC HTMX] Request method: {request.method}")
    print(f"[BATCH PUBLIC HTMX] Request form: {request.form}")
    print(f"[BATCH PUBLIC HTMX] Request headers: {dict(request.headers)}")
    print("="*80 + "\n")
    
    try:
        items_json = request.form.get('items')
        folder_id = request.form.get('folder_id')
        
        print(f"[BATCH PUBLIC HTMX] items_json: {items_json}")
        print(f"[BATCH PUBLIC HTMX] folder_id: {folder_id}")
        
        if not items_json:
            print("[BATCH PUBLIC HTMX] ERROR: Missing items parameter")
            return '<div class="alert alert-danger">Missing items parameter</div>', 400
        
        if not folder_id:
            print("[BATCH PUBLIC HTMX] ERROR: Missing folder_id parameter")
            return '<div class="alert alert-danger">Missing folder_id parameter</div>', 400
        
        items = json.loads(items_json)
        folder_id = int(folder_id)
        
        print(f"[BATCH PUBLIC HTMX] Parsed items: {items}")
        print(f"[BATCH PUBLIC HTMX] Parsed folder_id: {folder_id}")
        print(f"[BATCH PUBLIC HTMX] Number of items to process: {len(items)}")
        
        # Verify folder access
        folder = Folder.query.get_or_404(folder_id)
        print(f"[BATCH PUBLIC HTMX] Folder found: {folder.name} (ID: {folder.id})")
        if folder.user_id != current_user.id:
            print(f"[BATCH PUBLIC HTMX] ERROR: Access denied - folder owner {folder.user_id} != current user {current_user.id}")
            return '<div class="alert alert-danger">Access denied</div>', 403
        
        success_count = 0
        made_public_count = 0
        made_private_count = 0
        affected_sections = set()  # Track which sections need to be re-rendered
        
        print(f"[BATCH PUBLIC HTMX] Starting to process {len(items)} items...")
        for idx, item in enumerate(items):
            print(f"\n[BATCH PUBLIC HTMX] --- Processing item {idx + 1}/{len(items)} ---")
            item_type = item.get('type')
            item_id = item.get('id')
            
            print(f"[BATCH PUBLIC HTMX] Item type: {item_type}, ID: {item_id}")
            
            try:
                obj = None
                
                # Handle folders separately (toggle recursively)
                if item_type == 'folder':
                    print(f"[BATCH PUBLIC HTMX] Querying folder with ID {item_id}")
                    obj = Folder.query.get(item_id)
                    if obj and obj.user_id == current_user.id:
                        current_public_state = obj.is_public
                        new_public_state = not current_public_state
                        
                        # Recursively toggle folder and all contents
                        def toggle_folder_public_recursive(f, new_state):
                            f.is_public = new_state
                            for file_obj in f.files:
                                file_obj.is_public = new_state
                            for child in f.children:
                                toggle_folder_public_recursive(child, new_state)
                        
                        toggle_folder_public_recursive(obj, new_public_state)
                        
                        print(f"[BATCH PUBLIC HTMX] Public state change for folder: {current_public_state} -> {new_public_state}")
                        
                        if new_public_state:
                            made_public_count += 1
                        else:
                            made_private_count += 1
                        
                        success_count += 1
                        affected_sections.add('folders')
                    elif obj:
                        print(f"[BATCH PUBLIC HTMX] ERROR: Owner mismatch - folder owner {obj.user_id} != current user {current_user.id}")
                    else:
                        print(f"[BATCH PUBLIC HTMX] ERROR: Folder not found for ID {item_id}")
                    continue
                
                # Map item types to File queries
                if item_type == 'proprietary_note' or item_type == 'note':  # Support both new and legacy type
                    print(f"[BATCH PUBLIC HTMX] Querying note with ID {item_id}")
                    obj = File.query.filter_by(id=item_id, type='proprietary_note').first()
                    affected_sections.add('notes')
                    print(f"[BATCH PUBLIC HTMX] Note found: {obj is not None}")
                elif item_type == 'board' or item_type == 'whiteboard' or item_type == 'proprietary_whiteboard':
                    print(f"[BATCH PUBLIC HTMX] Querying board with ID {item_id}")
                    obj = File.query.filter_by(id=item_id, type='proprietary_whiteboard').first()
                    affected_sections.add('boards')
                    print(f"[BATCH PUBLIC HTMX] Board found: {obj is not None}")
                elif item_type == 'proprietary_blocks' or item_type == 'book':  # Support both new and legacy type
                    obj = File.query.filter_by(id=item_id, type='proprietary_blocks').first()
                    affected_sections.add('combined')
                elif item_type == 'proprietary_infinite_whiteboard':
                    print(f"[BATCH PUBLIC HTMX] Querying infinite whiteboard with ID {item_id}")
                    obj = File.query.filter_by(id=item_id, type='proprietary_infinite_whiteboard').first()
                    affected_sections.add('infinite_whiteboards')
                    print(f"[BATCH PUBLIC HTMX] Infinite whiteboard found: {obj is not None}")
                elif item_type == 'proprietary_graph':
                    print(f"[BATCH PUBLIC HTMX] Querying graph with ID {item_id}")
                    obj = File.query.filter_by(id=item_id, type='proprietary_graph').first()
                    affected_sections.add('graphs')
                    print(f"[BATCH PUBLIC HTMX] Graph found: {obj is not None}")
                elif item_type == 'timeline':
                    print(f"[BATCH PUBLIC HTMX] Querying timeline with ID {item_id}")
                    obj = File.query.filter_by(id=item_id, type='timeline').first()
                    affected_sections.add('timelines')
                    print(f"[BATCH PUBLIC HTMX] Timeline found: {obj is not None}")
                elif item_type == 'file':
                    obj = File.query.get(item_id)
                    if obj:
                        affected_sections.add(f'file_{obj.type}')
                elif item_type in ['markdown', 'todo', 'diagram', 'table', 'blocks', 'code', 'pdf']:
                    obj = File.query.filter_by(id=item_id, type=item_type).first()
                    affected_sections.add(f'file_{item_type}')
                
                if obj and hasattr(obj, 'owner_id') and obj.owner_id == current_user.id:
                    print(f"[BATCH PUBLIC HTMX] Object valid, owner matches")
                    print(f"[BATCH PUBLIC HTMX] Current is_public: {obj.is_public}")
                    
                    current_public_state = obj.is_public
                    new_public_state = not current_public_state
                    obj.is_public = new_public_state
                    
                    print(f"[BATCH PUBLIC HTMX] Public state change: {current_public_state} -> {new_public_state}")
                    
                    if new_public_state:
                        made_public_count += 1
                    else:
                        made_private_count += 1
                    
                    success_count += 1
                    print(f"[BATCH PUBLIC HTMX] Success count: {success_count}")
                elif obj:
                    print(f"[BATCH PUBLIC HTMX] ERROR: Owner mismatch - object owner != current user {current_user.id}")
                else:
                    print(f"[BATCH PUBLIC HTMX] ERROR: Object not found for {item_type} {item_id}")
            
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.session.rollback()
                continue
        
        print(f"\n[BATCH PUBLIC HTMX] Processing complete:")
        print(f"[BATCH PUBLIC HTMX] - Success count: {success_count}")
        print(f"[BATCH PUBLIC HTMX] - Made public: {made_public_count}")
        print(f"[BATCH PUBLIC HTMX] - Made private: {made_private_count}")
        print(f"[BATCH PUBLIC HTMX] - Affected sections: {affected_sections}")
        
        if success_count > 0:
            print(f"[BATCH PUBLIC HTMX] Committing database changes...")
            db.session.commit()
            print(f"[BATCH PUBLIC HTMX] Database commit successful")
        else:
            print(f"[BATCH PUBLIC HTMX] No changes to commit")
        
        # Get sort parameter from session or request
        sort_by = request.args.get('sort', session.get('folder_sort_by', 'name'))
        print(f"[BATCH PUBLIC HTMX] Sort by: {sort_by}")
        
        # Helper function to sort items (pinned first, then unpinned sorted)
        def sort_items(items, sort_by, item_type):
            """Sort items with pinned files appearing first, then unpinned files sorted normally."""
            if item_type in ['note', 'board', 'combined', 'file']:
                pinned = [item for item in items if hasattr(item, 'is_pinned') and item.is_pinned]
                unpinned = [item for item in items if not (hasattr(item, 'is_pinned') and item.is_pinned)]
            else:
                pinned = []
                unpinned = items
            
            # Pinned items ignore sort order (maintain insertion order)
            # Only sort unpinned items according to sort_by parameter
            if sort_by == 'name':
                if item_type == 'folder':
                    unpinned = sorted(unpinned, key=lambda x: x.name.lower())
                elif item_type in ['note', 'board', 'combined', 'file']:
                    unpinned = sorted(unpinned, key=lambda x: (x.title or '').lower())
            elif sort_by == 'created':
                unpinned = sorted(unpinned, key=lambda x: x.created_at or x.id)
            elif sort_by == 'modified':
                unpinned = sorted(unpinned, key=lambda x: x.last_modified or x.created_at or x.id, reverse=True)
            elif sort_by == 'size':
                if item_type == 'folder':
                    unpinned = sorted(unpinned, key=lambda x: len(x.notes) + len(x.boards) + len(x.children), reverse=True)
                elif item_type in ['note', 'board']:
                    unpinned = sorted(unpinned, key=lambda x: len(x.content_html or '') if item_type == 'note' else len(str(x.content_json or '')), reverse=True)
                elif item_type in ['combined', 'file']:
                    unpinned = sorted(unpinned, key=lambda x: x.get_content_size() if hasattr(x, 'get_content_size') else len(x.content or ''), reverse=True)
            
            return pinned + unpinned
        
        # Get user display preferences
        user_prefs = current_user.user_prefs or {}
        display_prefs = user_prefs.get('display', {})
        display_prefs.setdefault('columns', 3)
        display_prefs.setdefault('view_mode', 'grid')
        display_prefs.setdefault('card_size', 'normal')
        display_prefs.setdefault('show_previews', True)
        
        # Build response with HTMX OOB (Out Of Band) swaps for multiple targets
        response_parts = []
        print(f"\n[BATCH PUBLIC HTMX] Building HTML response...")
        
        # Folders section (if affected)
        if 'folders' in affected_sections:
            print(f"[BATCH PUBLIC HTMX] Rendering folders section...")
            subfolders = Folder.query.filter_by(parent_id=folder_id, user_id=current_user.id).all()
            subfolders = sort_items(subfolders, sort_by, 'folder')
            folders_html = render_template('p2/partials/folders_section_cards.html', 
                                          subfolders=subfolders, 
                                          display_prefs=display_prefs)
            response_parts.append(f'<div id="folders-grid" hx-swap-oob="innerHTML:#folders-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{folders_html}</div>')
        
        # Notes section
        if 'notes' in affected_sections:
            print(f"[BATCH PUBLIC HTMX] Rendering notes section...")
            notes = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_note').all()
            notes = sort_items(notes, sort_by, 'note')
            notes_html = render_template('p2/partials/notes_section_cards.html', 
                                        notes=notes, 
                                        display_prefs=display_prefs)
            response_parts.append(f'<div id="notes-grid" hx-swap-oob="innerHTML:#notes-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{notes_html}</div>')
        
        # Boards section
        if 'boards' in affected_sections:
            boards = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_whiteboard').all()
            boards = sort_items(boards, sort_by, 'board')
            boards_html = render_template('p2/partials/boards_section_cards.html', 
                                        boards=boards, 
                                        display_prefs=display_prefs)
            response_parts.append(f'<div id="boards-grid" hx-swap-oob="innerHTML:#boards-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{boards_html}</div>')
        
        # Combined/MioBook section
        if 'combined' in affected_sections:
            combined_docs = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type='proprietary_blocks').all()
            combined_docs = sort_items(combined_docs, sort_by, 'combined')
            combined_html = render_template('p2/partials/combined_section_cards.html', 
                                          combined_docs=combined_docs, 
                                          display_prefs=display_prefs)
            response_parts.append(f'<div id="combined-grid" hx-swap-oob="innerHTML:#combined-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{combined_html}</div>')
        
        # File sections (markdown, todo, diagram, etc.)
        for section in affected_sections:
            if section.startswith('file_'):
                file_type = section.replace('file_', '')
                files = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id, type=file_type).all()
                files = sort_items(files, sort_by, 'file')
                files_html = render_template('p2/partials/files_section_cards.html', 
                                           files=files, 
                                           file_type=file_type,
                                           display_prefs=display_prefs)
                response_parts.append(f'<div id="{file_type}-grid" hx-swap-oob="innerHTML:#{file_type}-grid" class="content-grid row row-cols-1 row-cols-md-2 row-cols-lg-{display_prefs["columns"]} g-4" data-view-mode="{display_prefs["view_mode"]}" data-card-size="{display_prefs["card_size"]}">{files_html}</div>')
        
        # Add success notification to telemetry
        message_parts = []
        if made_public_count > 0:
            message_parts.append(f"Made public: {made_public_count}")
        if made_private_count > 0:
            message_parts.append(f"Made private: {made_private_count}")
        message = ", ".join(message_parts) if message_parts else "No changes"
        
        # Add cleanup and notification script as OOB swap
        cleanup_script = f"""
        <div id="htmx-public-notification" hx-swap-oob="true">
            <script>
            (function() {{
                if (window.TelemetryPanel) {{
                    window.TelemetryPanel.setIdle('{message}');
                }}

                // Re-attach listeners after swaps to keep single-item actions working
                setTimeout(() => {{
                    if (typeof window.attachCardClickListeners === 'function') {{
                        document.querySelectorAll('.item-card .item-body').forEach(body => {{
                            window.attachCardClickListeners(body);
                        }});
                    }}
                }}, 100);
            }})();
            </script>
        </div>
        """
        
        # Primary response (empty div as anchor)
        primary_response = '<div style="display:none;"></div>'
        
        # Combine all parts
        full_response = primary_response + '\n'.join(response_parts) + cleanup_script
        
        print(f"\n[BATCH PUBLIC HTMX] Response ready:")
        print(f"[BATCH PUBLIC HTMX] - Response parts: {len(response_parts)}")
        print(f"[BATCH PUBLIC HTMX] - Response length: {len(full_response)} chars")
        print(f"[BATCH PUBLIC HTMX] - Response preview (first 500 chars):")
        print(full_response[:500])
        print("\n" + "="*80)
        print("[BATCH PUBLIC HTMX] Returning response to client")
        print("="*80 + "\n")
        
        return full_response
    
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"\n[BATCH PUBLIC HTMX] *** EXCEPTION OCCURRED ***")
        print(f"[BATCH PUBLIC HTMX] Error: {str(e)}")
        traceback.print_exc()
        print("\n")
        return f'<div class="alert alert-danger">Public toggle operation failed: {str(e)}</div>', 500


