from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_required, current_user
from blueprints.p2.models import File, Folder, db
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
import hashlib
import json
import time

# Create dedicated blueprint for infinite whiteboard
infinite_whiteboard_bp = Blueprint('infinite_boards', __name__, url_prefix='/infinite_boards')

def format_file_size(size_bytes):
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{(size_bytes / 1024):.1f} KB"
    else:
        return f"{(size_bytes / (1024 * 1024)):.1f} MB"

@infinite_whiteboard_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_infinite_board():
    """Create new infinite whiteboard."""
    # Allow explicit folder targeting (e.g., Graph Workspace) for GET and POST.
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
    
    if not current_folder_id:
        root_folder = Folder.query.filter_by(user_id=current_user.id, parent_id=None).first()
        current_folder_id = root_folder.id if root_folder else None

    # For GET requests, immediately create the board and redirect to edit
    if request.method == 'GET':
        # Create empty infinite whiteboard
        title = f"Infinite Canvas {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        initial_content = {
            'objects': [],
            'nextObjectId': 1,
            'viewport': {
                'x': 0,
                'y': 0,
                'scale': 1.0
            }
        }
        
        board = File(
            owner_id=current_user.id,
            folder_id=current_folder_id,
            type='proprietary_infinite_whiteboard',
            title=title,
            content_json=initial_content,
            metadata_json={}
        )
        
        try:
            db.session.add(board)
            db.session.commit()
            print(f"[DEBUG] Created new infinite whiteboard with ID: {board.id}")
            
            # Add notification for creation
            from blueprints.p2.utils import add_notification
            notif_msg = f"Created infinite whiteboard '{title}'"
            add_notification(current_user.id, notif_msg, 'save')
            
            # Redirect to edit page with the new board ID
            return redirect(url_for('infinite_boards.edit_infinite_board', board_id=board.id))
        except Exception as e:
            print(f"[ERROR] Failed to create infinite whiteboard: {e}")
            db.session.rollback()
            from blueprints.p2.utils import add_notification
            add_notification(current_user.id, "Failed to create infinite whiteboard.", 'error')
            return redirect(url_for('p2_bp.folder_view'))

    if request.method == 'POST':
        print(f"[DEBUG] Creating new infinite whiteboard")
        print(f"[DEBUG] Content type: {request.content_type}")
        print(f"[DEBUG] Content length: {request.content_length}")
        print(f"[DEBUG] Flask MAX_CONTENT_LENGTH: {current_app.config.get('MAX_CONTENT_LENGTH')}")
        payload = request.get_json(silent=True) or {}
        
        try:
            # Use current folder as default, but allow form override
            folder_id = request.form.get("folder_id", type=int)
            if folder_id is None:
                folder_id = payload.get("folder_id", current_folder_id)
            
            # Validate folder ownership
            if folder_id:
                valid_folder = Folder.query.filter_by(id=folder_id, user_id=current_user.id).first()
                if not valid_folder:
                    folder_id = current_folder_id

            title = (request.form.get('title') or payload.get('title') or '').strip() or f"Infinite Canvas {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            description = (request.form.get('description') or payload.get('description') or '')
            
            # Try form first, then JSON body fallback with better error handling
            content = None
            try:
                content = request.form.get('content')
                if content is None:
                    content = payload.get('content', '')
                    if content:
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
                    content_obj = {
                        'objects': [],
                        'nextObjectId': 1,
                        'viewport': {
                            'x': 0,
                            'y': 0,
                            'scale': 1.0
                        }
                    }
            except (ValueError, json_module.JSONDecodeError) as e:
                print(f"[ERROR] Failed to parse content JSON: {e}")
                content_obj = {
                    'objects': [],
                    'nextObjectId': 1,
                    'viewport': {
                        'x': 0,
                        'y': 0,
                        'scale': 1.0
                    }
                }

            # Create File with type='proprietary_infinite_whiteboard' and store content as JSON object
            board = File(
                owner_id=current_user.id,
                folder_id=folder_id,
                type='proprietary_infinite_whiteboard',
                title=title,
                content_json=content_obj,
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
                        from blueprints.p2.utils import add_notification
                        add_notification(user.id, "Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", 'error')
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
                print(f"[DEBUG] New infinite whiteboard created with ID: {board.id}")
            except Exception as db_error:
                print(f"[ERROR] Database error creating infinite whiteboard: {db_error}")
                db.session.rollback()
                return jsonify({"ok": False, "error": "Database save failed"}), 500

            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    "ok": True,
                    "content_saved": bool(board.content_json),
                    "content": board.content_json,
                    "board_id": board.id
                })
            
            return redirect(url_for('infinite_boards.edit_infinite_board', board_id=board.id))
            
        except Exception as e:
            print(f"[ERROR] General error in new_infinite_board: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    # GET request - pass current folder context to template
    return render_template('p2/infinite_whiteboard.html', current_folder_id=current_folder_id)


@infinite_whiteboard_bp.route('/edit/<int:board_id>', methods=['GET', 'POST'])
@login_required
def edit_infinite_board(board_id):
    """Edit existing infinite whiteboard."""
    board = File.query.get_or_404(board_id)
    
    # Verify ownership
    if board.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Access denied to infinite whiteboard.", 'error')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Verify it's an infinite whiteboard
    if board.type != 'proprietary_infinite_whiteboard':
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "This is not an infinite whiteboard.", 'error')
        return redirect(url_for('p2_bp.dashboard'))

    if request.method == 'POST':
        print(f"[DEBUG] Editing infinite whiteboard {board_id}")
        print(f"[DEBUG] Content type: {request.content_type}")
        print(f"[DEBUG] Content length: {request.content_length}")
        print(f"[DEBUG] Flask MAX_CONTENT_LENGTH: {current_app.config.get('MAX_CONTENT_LENGTH')}")
        # Simple per-user rate limit (per board) to avoid save spam
        now_ts = time.time()
        last_save_map = session.get('iwb_last_save_ts', {}) or {}
        last_ts = last_save_map.get(str(board_id))
        if last_ts and now_ts - last_ts < 5:
            msg = "Rate limited, try again momentarily"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"ok": False, "error": msg}), 429
            flash(msg, 'warning')
            return redirect(url_for('infinite_boards.edit_infinite_board', board_id=board_id))
        last_save_map[str(board_id)] = now_ts
        session['iwb_last_save_ts'] = last_save_map
        payload = request.get_json(silent=True) or {}
        
        # Handle large content requests
        try:
            title = (request.form.get('title') or payload.get('title') or '').strip()
            description = (request.form.get('description') or payload.get('description') or '')
            print(f"[DEBUG] Title: {title}")
            print(f"[DEBUG] Description: {description}")
            
            # Accept form or JSON with better error handling
            incoming_content = None
            try:
                incoming_content = request.form.get('content')
                if incoming_content is None:
                    incoming_content = payload.get('content', None)
                    if incoming_content is not None:
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

            def compute_hash(raw: str):
                return hashlib.sha256(raw.encode('utf-8')).hexdigest()

            incoming_hash = compute_hash(incoming_content) if isinstance(incoming_content, str) else None
            stored_hash = None
            current_description = board.metadata_json.get('description', '') if board.metadata_json else ''
            if board.metadata_json and isinstance(board.metadata_json, dict):
                stored_hash = board.metadata_json.get('content_sha')
            new_title = title or board.title
            new_description = description
            same_content = False
            if incoming_content is None:
                same_content = True  # no content sent means caller isn't changing content
            elif incoming_hash and stored_hash and incoming_hash == stored_hash:
                same_content = True

            if same_content and new_title == board.title and new_description == current_description:
                print(f"[DEBUG] No changes detected for board {board_id}; skipping DB commit")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        "ok": True,
                        "content_saved": False,
                        "skipped": True,
                        "reason": "No changes"
                    })
                return redirect(url_for('infinite_boards.edit_infinite_board', board_id=board_id))

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
                        content_to_store = {
                            'objects': [],
                            'nextObjectId': 1,
                            'viewport': {
                                'x': 0,
                                'y': 0,
                                'scale': 1.0
                            }
                        }
                else:
                    content_to_store = {
                        'objects': [],
                        'nextObjectId': 1,
                        'viewport': {
                            'x': 0,
                            'y': 0,
                            'scale': 1.0
                        }
                    }
                    print(f"[DEBUG] Empty content, using default structure")

            # If incoming_content is not None, the client sent content - update it.
            # If it's None, keep existing content.
            old_content = board.content_json or {}
            old_size = len(str(old_content).encode('utf-8')) if old_content else 0
            if content_to_store is not None:
                # Process data URI images and save to disk
                from blueprints.p2.utils import save_data_uri_images_in_json
                content_to_store, images_bytes_added = save_data_uri_images_in_json(content_to_store, current_user.id)
                print(f"[DEBUG] Processed images in infinite whiteboard content: {images_bytes_added} bytes added")
                
                board.content_json = content_to_store
                print(f"[DEBUG] Updated infinite whiteboard content")
            else:
                print(f"[DEBUG] Keeping existing content")

            board.title = title or board.title
            # Update description in metadata_json
            if not board.metadata_json:
                board.metadata_json = {}
            board.metadata_json['description'] = description
            print(f"DEBUG: Setting metadata_json for infinite whiteboard {board.id}: {board.metadata_json}")
            # Track hash to short-circuit unchanged saves
            try:
                serialized_content = json.dumps(board.content_json, sort_keys=True)
                board.metadata_json['content_sha'] = compute_hash(serialized_content)
            except Exception as hash_err:
                print(f"[WARN] Failed to compute content hash: {hash_err}")

            flag_modified(board, 'metadata_json')
            flag_modified(board, 'content_json')
            board.last_modified = datetime.utcnow()
            
            new_content = board.content_json or ''
            new_size = len(str(new_content).encode('utf-8')) if new_content else 0
            
            # CRITICAL FIX: Only generate thumbnails on MANUAL saves, not autosaves
            # Check if this is a manual save (has 'generate_thumbnail' flag in request)
            should_generate_thumbnail = (request.form.get('generate_thumbnail') == 'true' or 
                                        payload.get('generate_thumbnail') == 'true')
            
            if should_generate_thumbnail and content_to_store is not None and new_size > 0:
                try:
                    from blueprints.p2.utils import generate_whiteboard_thumbnail
                    print(f"[DEBUG] Generating thumbnail for infinite whiteboard {board.id} (manual save)...")
                    thumbnail_path = generate_whiteboard_thumbnail(
                        board.content_json,
                        board.owner_id,
                        board.id
                    )
                    if thumbnail_path:
                        board.thumbnail_path = thumbnail_path
                        flag_modified(board, 'thumbnail_path')
                        print(f"[DEBUG] Thumbnail generated: {thumbnail_path}")
                    else:
                        print(f"[DEBUG] Thumbnail generation returned None")
                except Exception as thumb_error:
                    # Don't fail the save if thumbnail generation fails
                    print(f"[WARNING] Thumbnail generation failed: {thumb_error}")
            elif content_to_store is not None:
                print(f"[DEBUG] Skipping thumbnail generation (autosave)")
            
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
                notification_msg = f"Saved infinite whiteboard: {board.title} ({size_str})"
                add_notification(current_user.id, notification_msg, 'save')
                
                print(f"[DEBUG] Infinite whiteboard saved to database successfully")
            except Exception as db_error:
                print(f"[ERROR] Database error: {db_error}")
                db.session.rollback()
                return jsonify({"ok": False, "error": "Database save failed"}), 500
            
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # return the saved content so client can verify what was stored
                return jsonify({
                    "ok": True,
                    "content_saved": bool(board.content_json),
                    "content": board.content_json
                })
            else:
                # For form submissions, use telemetry notification instead of flash
                size_str = format_file_size(new_size)
                return redirect(url_for('infinite_boards.edit_infinite_board', board_id=board_id, saved='infinite_board', size=size_str))
            
        except Exception as e:
            print(f"[ERROR] General error in edit_infinite_board: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500

    # GET request - loading existing infinite whiteboard
    print(f"[DEBUG] Loading infinite whiteboard {board_id} for editing")
    print(f"[DEBUG] Board title: {board.title}")
    content = board.content_json or {}
    print(f"[DEBUG] Board content length: {len(str(content))}")
    print(f"[DEBUG] Board content preview: {str(content)[:200] if content else 'None'}...")

    return render_template('p2/infinite_whiteboard.html', board=board)


@infinite_whiteboard_bp.route('/view/<int:board_id>', methods=['GET'])
@login_required
def view_infinite_board(board_id):
    """View infinite whiteboard in read-only mode."""
    board = File.query.get_or_404(board_id)
    
    # Verify ownership
    if board.owner_id != current_user.id:
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "Access denied to infinite whiteboard.", 'error')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Verify it's an infinite whiteboard
    if board.type != 'proprietary_infinite_whiteboard':
        from blueprints.p2.utils import add_notification
        add_notification(current_user.id, "This is not an infinite whiteboard.", 'error')
        return redirect(url_for('p2_bp.dashboard'))

    print(f"[DEBUG] Viewing infinite whiteboard {board_id}")
    print(f"[DEBUG] Board title: {board.title}")
    content = board.content_json or {}
    print(f"[DEBUG] Board content length: {len(str(content))}")

    return render_template('p2/infinite_whiteboard.html', board=board, read_only=True)


@infinite_whiteboard_bp.route('/api/generate_thumbnail/<int:board_id>', methods=['POST'])
@login_required
def generate_thumbnail_api(board_id):
    """Generate thumbnail for infinite whiteboard on-demand (AJAX endpoint)."""
    from blueprints.p2.models import File
    from blueprints.p2.utils import generate_whiteboard_thumbnail
    from sqlalchemy.orm.attributes import flag_modified
    
    board = File.query.get_or_404(board_id)
    
    # Verify ownership
    if board.owner_id != current_user.id:
        return jsonify({"success": False, "error": "Access denied"}), 403
    
    # Verify it's an infinite whiteboard
    if board.type != 'proprietary_infinite_whiteboard':
        return jsonify({"success": False, "error": "Not an infinite whiteboard"}), 400
    
    try:
        print(f"[API] Generating thumbnail for board {board_id}...")
        thumbnail_path = generate_whiteboard_thumbnail(
            board.content_json,
            board.owner_id,
            board.id
        )
        
        if thumbnail_path:
            board.thumbnail_path = thumbnail_path
            flag_modified(board, 'thumbnail_path')
            db.session.commit()
            
            print(f"[API] Thumbnail generated: {thumbnail_path}")
            return jsonify({
                "success": True,
                "thumbnail_url": thumbnail_path
            })
        else:
            return jsonify({
                "success": False,
                "error": "Thumbnail generation returned None (empty board?)"
            }), 400
            
    except Exception as e:
        print(f"[API] Thumbnail generation failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
