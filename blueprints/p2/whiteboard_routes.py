from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user
from blueprints.p2.models import File, Folder, db
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime

from . import whiteboard_bp  # Import the blueprint instance

def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{(size_bytes / 1024):.1f} KB"
    else:
        return f"{(size_bytes / (1024 * 1024)):.1f} MB"

@whiteboard_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_board():
    # Get current folder from session (same pattern as new_note)
    current_folder_id = session.get('current_folder_id')
    
    if not current_folder_id:
        root_folder = Folder.query.filter_by(user_id=current_user.id, parent_id=None).first()
        current_folder_id = root_folder.id if root_folder else None

    if request.method == 'POST':
        print(f"[DEBUG] Creating new board")
        print(f"[DEBUG] Content type: {request.content_type}")
        print(f"[DEBUG] Content length: {request.content_length}")
        print(f"[DEBUG] Flask MAX_CONTENT_LENGTH: {current_app.config.get('MAX_CONTENT_LENGTH')}")
        
        try:
            # Use current folder as default, but allow form override
            folder_id = request.form.get("folder_id", type=int) or current_folder_id
            
            # Validate folder ownership
            if folder_id:
                valid_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first()
                if not valid_folder:
                    folder_id = current_folder_id

            title = request.form.get('title', '').strip() or f"Untitled {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            description = request.form.get('description', '')
            
            # Try form first, then JSON body fallback with better error handling
            content = None
            try:
                content = request.form.get('content')
                if content is None:
                    payload = request.get_json(silent=True) or {}
                    content = payload.get('content', '')
                    print(f"[DEBUG] Using JSON payload for content")
                    
                if content is not None:
                    print(f"[DEBUG] Content length: {len(content)}")
                else:
                    content = ''
                    print(f"[DEBUG] No content provided, using empty string")
                    
            except Exception as content_error:
                print(f"[ERROR] Failed to parse content: {content_error}")
                content = ''
                
            # Normalize literal "null" to empty string
            if isinstance(content, str) and content.strip().lower() == 'null':
                content = ''

            # Parse JSON string to Python object for storage in JSON column
            # SQLAlchemy's JSON column will serialize it, so we need to store the object
            import json as json_module
            try:
                if isinstance(content, str) and content.strip():
                    content_obj = json_module.loads(content)
                else:
                    content_obj = {}
            except (ValueError, json_module.JSONDecodeError) as e:
                print(f"[ERROR] Failed to parse content JSON: {e}")
                content_obj = {}

            # Create File with type='proprietary_whiteboard' and store content as JSON object
            board = File(
                owner_id=current_user.id,
                folder_id=folder_id,
                type='proprietary_whiteboard',
                title=title,
                content_json=content_obj,  # Store as Python object, SQLAlchemy will serialize
                metadata_json={'description': description} if description else {}
            )
            
            # Calculate size and check cap
            def calculate_content_size(content):
                return len(content.encode('utf-8')) if content else 0
            content_size = calculate_content_size(content)
            def check_guest_limit(user, additional_size):
                if getattr(user, 'user_type', None) == 'guest':
                    max_size = 50 * 1024 * 1024
                    if (user.total_data_size or 0) + additional_size > max_size:
                        flash("Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", "danger")
                        return False
                return True
            def update_user_data_size(user, delta):
                user.total_data_size = (user.total_data_size or 0) + delta
                db.session.commit()
            if not check_guest_limit(current_user, content_size):
                return jsonify({"ok": False, "error": "Data limit exceeded"}), 400
            
            try:
                db.session.add(board)
                db.session.commit()
                update_user_data_size(current_user, content_size)
                print(f"[DEBUG] New board created with ID: {board.id}")
                
                # Add notification for board creation
                from blueprints.p2.utils import add_notification
                def format_file_size(size_bytes):
                    if size_bytes < 1024:
                        return f"{size_bytes}B"
                    elif size_bytes < 1024 * 1024:
                        return f"{(size_bytes / 1024):.1f}KB"
                    else:
                        return f"{(size_bytes / (1024 * 1024)):.1f}MB"
                size_str = format_file_size(content_size)
                notif_msg = f"Created board '{title}' ({size_str})"
                add_notification(current_user.id, notif_msg, 'save')
                
            except Exception as db_error:
                print(f"[ERROR] Database error creating board: {db_error}")
                db.session.rollback()
                return jsonify({"ok": False, "error": "Database save failed"}), 500

            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"ok": True, "content_saved": bool(board.content_json), "content": board.content_json, "board_id": board.id})
            
            # Session asset cleanup removed - handled by dedicated cleanup function
            return redirect(url_for('boards.edit_board', board_id=board.id))
            
        except Exception as e:
            print(f"[ERROR] General error in new_board: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    # GET request - pass current folder context to template
    return render_template('p2/mioboard_v4.html', current_folder_id=current_folder_id)



@whiteboard_bp.route('/edit/<int:board_id>', methods=['GET', 'POST'])
@login_required
def edit_board(board_id):
    board = File.query.get_or_404(board_id)
    if board.owner_id != current_user.id:
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        print(f"[DEBUG] Editing board {board_id}")
        print(f"[DEBUG] Content type: {request.content_type}")
        print(f"[DEBUG] Content length: {request.content_length}")
        print(f"[DEBUG] Flask MAX_CONTENT_LENGTH: {current_app.config.get('MAX_CONTENT_LENGTH')}")
        
        # Handle large content requests
        try:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '')
            print(f"[DEBUG] Title: {title}")
            print(f"[DEBUG] Description: {description}")
            
            # Accept form or JSON with better error handling
            incoming_content = None
            try:
                incoming_content = request.form.get('content')
                if incoming_content is None:
                    payload = request.get_json(silent=True) or {}
                    incoming_content = payload.get('content', None)
                    print(f"[DEBUG] Using JSON payload for content")
                
                if incoming_content is not None:
                    print(f"[DEBUG] Content length: {len(incoming_content)}")
                    print(f"[DEBUG] Content preview: {incoming_content[:200]}...")
                else:
                    print(f"[DEBUG] No content in request")
                    
            except Exception as content_error:
                print(f"[ERROR] Failed to parse content: {content_error}")
                return jsonify({"ok": False, "error": "Failed to parse request content"}), 400

            # Normalize literal "null" -> None/empty
            if isinstance(incoming_content, str) and incoming_content.strip().lower() == 'null':
                incoming_content = ''
                print(f"[DEBUG] Normalized 'null' to empty string")

            # Parse JSON string to Python object before storing
            # SQLAlchemy's JSON column will serialize it, so we store the object
            import json as json_module
            content_to_store = None
            if incoming_content is not None:
                if isinstance(incoming_content, str) and incoming_content.strip():
                    try:
                        content_to_store = json_module.loads(incoming_content)
                        print(f"[DEBUG] Parsed JSON content: {len(str(content_to_store))} chars")
                    except (ValueError, json_module.JSONDecodeError) as e:
                        print(f"[ERROR] Failed to parse content JSON, using empty: {e}")
                        content_to_store = {}
                else:
                    content_to_store = {}
                    print(f"[DEBUG] Empty content, using {{}}")

            # If incoming_content is not None, the client sent content - update it.
            # If it's None, keep existing content.
            old_content = board.content_json or {}
            old_size = len(str(old_content).encode('utf-8')) if old_content else 0
            if content_to_store is not None:
                board.content_json = content_to_store
                print(f"[DEBUG] Updated board content")
            else:
                print(f"[DEBUG] Keeping existing content")

            board.title = title or board.title
            # Update description in metadata_json
            if not board.metadata_json:
                board.metadata_json = {}
            board.metadata_json['description'] = description
            print(f"DEBUG: Setting metadata_json for board {board.id}: {board.metadata_json}")
            flag_modified(board, 'metadata_json')
            flag_modified(board, 'content_json')
            board.last_modified = datetime.utcnow()
            
            new_content = board.content_json or ''
            new_size = len(str(new_content).encode('utf-8')) if new_content else 0
            delta = new_size - old_size
            def check_guest_limit(user, additional_size):
                if getattr(user, 'user_type', None) == 'guest':
                    max_size = 50 * 1024 * 1024
                    if (user.total_data_size or 0) + additional_size > max_size:
                        return False
                return True
            def update_user_data_size(user, delta):
                user.total_data_size = (user.total_data_size or 0) + delta
                db.session.commit()
            if not check_guest_limit(current_user, delta):
                return jsonify({"ok": False, "error": "Data limit exceeded"}), 400
            
            try:
                db.session.commit()
                update_user_data_size(current_user, delta)
                
                # Add notification for successful save
                from blueprints.p2.utils import add_notification
                size_str = f"{new_size / 1024:.1f} KB" if new_size < 1024 * 1024 else f"{new_size / (1024 * 1024):.1f} MB"
                notification_msg = f"Saved board: {board.title} ({size_str})"
                add_notification(current_user.id, notification_msg, 'save')
                
                print(f"[DEBUG] Board saved to database successfully")
            except Exception as db_error:
                print(f"[ERROR] Database error: {db_error}")
                db.session.rollback()
                return jsonify({"ok": False, "error": "Database save failed"}), 500
            
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # return the saved content so client can verify what was stored
                return jsonify({"ok": True, "content_saved": bool(board.content_json), "content": board.content_json})
            else:
                # For form submissions, use telemetry notification instead of flash
                size_str = format_file_size(new_size)
                return redirect(url_for('boards.edit_board', board_id=board_id, saved='board', size=size_str))
            
        except Exception as e:
            print(f"[ERROR] General error in edit_board: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    # GET request - loading existing board
    print(f"[DEBUG] Loading board {board_id} for editing")
    print(f"[DEBUG] Board title: {board.title}")
    content = board.content_json or ''
    print(f"[DEBUG] Board content length: {len(str(content))}")
    print(f"[DEBUG] Board content preview: {str(content)[:200] if content else 'None'}...")

    return render_template('p2/mioboard_v4.html', board=board)


