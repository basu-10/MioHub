from . import p2_blueprint
from flask import render_template, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask import Flask, json, render_template, request, jsonify, session, redirect, url_for, request, flash, Response, send_file, abort, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import urlparse

from blueprints.p2.models import  User, Folder, File, VALID_FILE_TYPES, CREATABLE_FILE_TYPES, UPLOADABLE_FILE_TYPES
from extensions import db, login_manager
from sqlalchemy.exc import OperationalError
import time
from datetime import datetime
import bleach
from bs4 import BeautifulSoup
import traceback
import os
import io
import zipfile
from values_main import UPLOAD_FOLDER, MAX_IMAGE_SIZE, ALLOWED_EXTENSIONS
from utilities_main import update_user_data_size, check_guest_limit
from .utils import (
    get_existing_image_by_hash,
    get_image_hash,
    allowed_file,
    convert_to_webp,
    parse_description_field,
)

import config

# Central list of user types supported by the application. Keep in sync with templates.
ALLOWED_USER_TYPES = [
    'guest', 'user', 'personal', 'level_1', 'level_2', 'level_3', 'level_4', 'level_5', 'mod1', 'moderator', 'dev1', 'dev2', 'admin'
]

def db_retry(func, max_retries=3, delay=1):
    """Retry database operations with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except OperationalError as e:
            if "MySQL Connection not available" in str(e) and attempt < max_retries - 1:
                print(f"Database connection failed, retrying in {delay} seconds... (attempt {attempt + 1})")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                # Try to close and recreate the session
                try:
                    db.session.close()
                    db.session.remove()
                except:
                    pass
                continue
            else:
                raise e
    return None

@p2_blueprint.route('/p2_index')
def p2_index():
    return render_template('p2/index.html')


@p2_blueprint.route('/extension-settings')
@login_required
def extension_settings():
    """Chrome Extension settings page for API token management."""
    from datetime import datetime
    response = make_response(render_template('p2/extension_settings.html', now=datetime.utcnow()))
    # Prevent cached HTML from leaking a previous user's token after account switches
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@p2_blueprint.route('/download-chrome-extension')
@login_required
def download_chrome_extension():
    """Generate and download Chrome extension as ZIP file."""
    try:
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()
        
        # Path to chrome_extension folder
        extension_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'chrome_extension')
        
        # Create ZIP with all extension files
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add manifest.json
            manifest_path = os.path.join(extension_dir, 'manifest.json')
            if os.path.exists(manifest_path):
                zipf.write(manifest_path, 'manifest.json')
            
            # Add popup files
            for popup_file in ['popup.html', 'popup.css', 'popup.js']:
                file_path = os.path.join(extension_dir, popup_file)
                if os.path.exists(file_path):
                    zipf.write(file_path, popup_file)
            
            # Add background.js
            background_path = os.path.join(extension_dir, 'background.js')
            if os.path.exists(background_path):
                zipf.write(background_path, 'background.js')
            
            # Add icons folder
            icons_dir = os.path.join(extension_dir, 'icons')
            if os.path.exists(icons_dir):
                for icon_file in os.listdir(icons_dir):
                    icon_path = os.path.join(icons_dir, icon_file)
                    if os.path.isfile(icon_path):
                        zipf.write(icon_path, os.path.join('icons', icon_file))
        
        # Prepare ZIP for download
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='miohub-chrome-extension.zip'
        )
        
    except Exception as e:
        print(f"Error generating extension ZIP: {e}")
        flash('Failed to download extension. Please try again.', 'error')
        return redirect(url_for('p2_bp.extension_settings'))



@p2_blueprint.route('/dashboard')
@login_required
def dashboard():
    user_files = File.query.filter_by(owner_id=current_user.id).all()
    
    # Check if user has a root/home folder; create one if missing
    root_folder = Folder.query.filter_by(user_id=current_user.id, is_root=True).first()
    if not root_folder:
        root_folder = Folder(name='root', user_id=current_user.id, parent_id=None, is_root=True)
        db.session.add(root_folder)
        db.session.commit()
    folder_id = root_folder.id
    
    return redirect(url_for('folders.view_folder', folder_id=folder_id))


@p2_blueprint.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Get admin dashboard data
    total_users = User.query.count()
    total_files = File.query.count()
    total_folders = Folder.query.count()
    
    # Get recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    
    return render_template('p2/p2_admin_dashboard.html', 
                         total_users=total_users,
                         total_notes=total_files,  # Keep template variable name for compatibility
                         total_folders=total_folders,
                         recent_users=recent_users)


@p2_blueprint.route('/admin/users')
@login_required
def admin_view_users():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of users per page
    
    # Get search parameter
    search = request.args.get('search', '', type=str)
    
    # Build query
    query = User.query
    if search:
        query = query.filter(
            User.username.contains(search) | 
            User.email.contains(search)
        )
    
    # Paginate results
    users = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    return render_template('p2/p2_admin_users.html', 
                         users=users, 
                         search=search,
                         allowed_types=ALLOWED_USER_TYPES)


@p2_blueprint.route('/admin/users/<int:user_id>/toggle_type', methods=['POST'])
@login_required
def admin_toggle_user_type(user_id):
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from demoting themselves
    if user.id == current_user.id:
        flash('You cannot change your own user type.')
        return redirect(url_for('p2_bp.admin_view_users'))
    
    # Toggle user type
    if user.user_type == 'admin':
        user.user_type = 'user'
        flash(f'User {user.username} demoted to regular user.')
    else:
        user.user_type = 'admin'
        flash(f'User {user.username} promoted to admin.')
    
    db.session.commit()
    return redirect(url_for('p2_bp.admin_view_users'))


@p2_blueprint.route('/admin/users/<int:user_id>/set_type', methods=['POST'])
@login_required
def admin_set_user_type(user_id):
    """Set an arbitrary supported user_type for a user via AJAX or form POST.
    Expects JSON { user_type: 'admin' } or form-encoded 'user_type'. Returns JSON on success/failure.
    """
    # Check if user is admin
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access denied. Admin privileges required.'}), 403

    user = User.query.get_or_404(user_id)

    # Prevent admin from changing their own type
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'You cannot change your own user type.'}), 400

    # Read supplied user_type from JSON or form data
    new_type = None
    if request.is_json:
        data = request.get_json(silent=True) or {}
        new_type = data.get('user_type')
    else:
        new_type = request.form.get('user_type')

    if not new_type:
        return jsonify({'success': False, 'message': 'No user type supplied.'}), 400

    allowed_types = ALLOWED_USER_TYPES
    if new_type not in allowed_types:
        return jsonify({'success': False, 'message': 'Invalid user type.'}), 400

    # If no change, return success
    if user.user_type == new_type:
        return jsonify({'success': True, 'message': f'User already set to {new_type}.', 'user_type': new_type})

    old_type = user.user_type
    user.user_type = new_type
    db.session.commit()

    return jsonify({'success': True, 'message': f'User {user.username} changed from {old_type} to {new_type}.', 'user_type': new_type})


@p2_blueprint.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash('You cannot delete your own account.')
        return redirect(url_for('p2_bp.admin_view_users'))
    
    username = user.username
    
    # Delete shared note entries where this user is the recipient
    shared_entries = []  # SharedNote removed
    for entry in shared_entries:
        db.session.delete(entry)
    
    # The model relationships now have cascade='all, delete-orphan' 
    # so deleting the user will automatically delete all related data
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} and all their data has been deleted.')
    return redirect(url_for('p2_bp.admin_view_users'))


@p2_blueprint.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
def admin_create_user():
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form.get('email', '').strip()
        password = request.form['password']
        user_type = request.form['user_type']
        
        # Validation
        if not username:
            flash('Username is required.')
            return redirect(url_for('p2_bp.admin_create_user'))
        
        if not password:
            flash('Password is required.')
            return redirect(url_for('p2_bp.admin_create_user'))
        
        if user_type not in ALLOWED_USER_TYPES:
            flash('Invalid user type.')
            return redirect(url_for('p2_bp.admin_create_user'))
        
        # Check username uniqueness
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('p2_bp.admin_create_user'))
        
        # Create user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            user_type=user_type
        )
        db.session.add(new_user)
        db.session.flush()
        
        # Create root folder for the user
        root_folder = Folder(name='root', user_id=new_user.id, parent_id=None, is_root=True)
        db.session.add(root_folder)
        db.session.commit()
        
        flash(f'User {username} created successfully with type {user_type}.')
        return redirect(url_for('p2_bp.admin_view_users'))
    
    return render_template('p2/admin_create_user.html', allowed_types=ALLOWED_USER_TYPES)


@p2_blueprint.route('/admin/users/<int:user_id>/details')
@login_required
def admin_user_details(user_id):
    # Check if user is admin
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('p2_bp.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    # Get user statistics
    notes_count = File.query.filter_by(owner_id=user_id, type='note').count()
    folders_count = Folder.query.filter_by(user_id=user_id).count()
    boards_count = File.query.filter_by(owner_id=user_id, type='whiteboard').count()
    
    # Calculate approximate storage usage
    notes = File.query.filter_by(owner_id=user_id, type='note').all()
    boards = File.query.filter_by(owner_id=user_id, type='whiteboard').all()
    
    total_notes_size = sum(len(note.content_html or '') for note in notes)
    total_boards_size = sum(len(str(board.content_json or '')) for board in boards)
    total_storage_bytes = total_notes_size + total_boards_size
    
    # Convert to readable format
    def format_bytes(bytes_size):
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    
    total_storage = format_bytes(total_storage_bytes)
    avg_note_size = format_bytes(total_notes_size / max(notes_count, 1))
    avg_board_size = format_bytes(total_boards_size / max(boards_count, 1))
    
    # Get recent activity (last 10 notes and boards by creation/update time)
    recent_notes = File.query.filter_by(owner_id=user_id, type='note').order_by(File.id.desc()).limit(10).all()
    recent_boards = File.query.filter_by(owner_id=user_id, type='whiteboard').order_by(File.id.desc()).limit(10).all()
    
    # Get folder structure
    root_folder = Folder.query.filter_by(user_id=user_id, name='root').first()
    folder_tree = []
    if root_folder:
        def build_folder_tree(folder, depth=0):
            tree_item = {
                'folder': folder,
                'depth': depth,
                'notes_count': File.query.filter_by(folder_id=folder.id, type='note').count(),
                'boards_count': File.query.filter_by(folder_id=folder.id, type='whiteboard').count()
            }
            folder_tree.append(tree_item)
            
            for child in folder.children:
                build_folder_tree(child, depth + 1)
        
        build_folder_tree(root_folder)
    
    return render_template('p2/admin_user_details.html',
                         user=user,
                         stats={
                             'notes_count': notes_count,
                             'folders_count': folders_count,
                             'boards_count': boards_count,
                             'total_storage': total_storage,
                             'avg_note_size': avg_note_size,
                             'avg_board_size': avg_board_size,
                             'total_storage_bytes': total_storage_bytes
                         },
                         recent_notes=recent_notes,
                         recent_boards=recent_boards,
                         folder_tree=folder_tree,
                         allowed_types=ALLOWED_USER_TYPES,
                         max=max)


@p2_blueprint.route('/profile')
@login_required
def profile():
    """Render the current user's profile page with basic stats."""
    user = current_user

    notes_count = File.query.filter_by(owner_id=user.id, type='note').count()
    folders_count = Folder.query.filter_by(user_id=user.id).count()
    boards_count = File.query.filter_by(owner_id=user.id, type='whiteboard').count()

    # Storage calculations
    used_bytes = user.total_data_size or 0
    used_mb = used_bytes / (1024 * 1024)
    total_mb = 50 if user.user_type == 'guest' else None
    percent = None
    if total_mb:
        try:
            percent = min(100, (used_mb / total_mb) * 100)
        except Exception:
            percent = 0

    # Recently used files: combine recent notes and boards, sorted by last_modified
    try:
        recent_notes = File.query.filter_by(owner_id=user.id, type='note').order_by(File.last_modified.desc()).limit(8).all()
    except Exception:
        recent_notes = []

    try:
        recent_boards = File.query.filter_by(owner_id=user.id, type='whiteboard').order_by(File.last_modified.desc()).limit(8).all()
    except Exception:
        recent_boards = []

    recent_candidates = []
    for n in recent_notes:
        lm = n.last_modified or n.created_at
        # sanitize preview content
        def sanitize_preview(raw_html):
            if not raw_html:
                return ''
            allowed_tags = [
                'p', 'br', 'b', 'strong', 'i', 'em', 'u', 'a', 'ul', 'ol', 'li',
                'img', 'h1', 'h2', 'h3', 'h4', 'pre', 'code', 'blockquote', 'span', 'div'
            ]
            allowed_attrs = {
                'a': ['href', 'title'],
                'img': ['src', 'alt', 'title'],
            }
            cleaned = bleach.clean(raw_html, tags=allowed_tags, attributes=allowed_attrs, protocols=['http', 'https', 'data'], strip=True)
            # remove external images (allow only local upload paths and data URIs)
            try:
                soup = BeautifulSoup(cleaned, 'html.parser')
                for img in soup.find_all('img'):
                    src = str(img.get('src') or '')
                    if not (src.startswith('/static/uploads/images/') or src.startswith('static/uploads/images/') or src.startswith('/uploads/images/') or src.startswith('uploads/images/') or src.startswith('data:image/')):
                        img.decompose()
                return str(soup)
            except Exception:
                return cleaned

        recent_candidates.append({
            'type': 'note',
            'id': n.id,
            'title': n.title or 'Untitled',
            'last_modified': lm,
            'url': url_for('notes.edit_note', note_id=n.id),
            'preview': sanitize_preview(n.content_html or '')
        })

    for b in recent_boards:
        lm = b.last_modified or b.created_at
        recent_candidates.append({
            'type': 'board',
            'id': b.id,
            'title': b.title or 'Untitled',
            'last_modified': lm,
            'url': url_for('boards.edit_board', board_id=b.id),
            'preview': sanitize_preview(b.description or '')
        })

    # sort by last_modified desc and take top 8
    recent_candidates.sort(key=lambda x: x['last_modified'] or datetime.utcnow(), reverse=True)
    recent_files = recent_candidates[:8]

    # derive display preferences from user's prefs (fallbacks like folder view expects)
    display_prefs = {}
    try:
        prefs = user.user_prefs or {}
        display_prefs = prefs.get('display', {}) if isinstance(prefs, dict) else {}
        # ensure keys exist with sensible defaults
        display_prefs.setdefault('show_previews', True)
        display_prefs.setdefault('columns', 3)
        display_prefs.setdefault('view_mode', 'grid')
        display_prefs.setdefault('card_size', 'normal')
    except Exception:
        display_prefs = {'show_previews': True, 'columns': 3, 'view_mode': 'grid', 'card_size': 'normal'}

    # Get pinned users from preferences (list of user ids)
    pinned_users = []
    try:
        prefs = user.user_prefs or {}
        pinned_ids = prefs.get('pinned_users', []) if isinstance(prefs, dict) else []
        if pinned_ids:
            # Preserve order of pinned_ids
            pinned_users = [User.query.get(int(uid)) for uid in pinned_ids if User.query.get(int(uid))]
    except Exception:
        pinned_users = []

    return render_template('p2/profile.html',
                           user=user,
                           notes_count=notes_count,
                           folders_count=folders_count,
                           boards_count=boards_count,
                           used_mb=used_mb,
                           total_mb=total_mb,
                           percent=percent,
                           recent_files=recent_files,
                           display_prefs=display_prefs,
                           pinned_users=pinned_users)


@p2_blueprint.route('/storage_status')
@login_required
def storage_status():
    """Return JSON with used_bytes and total_bytes for current user.

    Used by client-side polling in the navbar to show Used/Remaining.
    """
    try:
        used_bytes = int(current_user.total_data_size or 0)
    except Exception:
        used_bytes = 0

    total_bytes = None
    if getattr(current_user, 'user_type', None) == 'guest':
        total_bytes = 50 * 1024 * 1024

    remaining_bytes = None
    if total_bytes is not None:
        remaining_bytes = max(total_bytes - used_bytes, 0)

    return jsonify({
        'used_bytes': used_bytes,
        'total_bytes': total_bytes,
        'remaining_bytes': remaining_bytes,
    })


@p2_blueprint.route('/api/telemetry_data')
@login_required
def telemetry_data():
    """Return telemetry data for TelemetryPanel display.
    
    Provides system metrics including:
    - User type and storage info
    - Total image count
    - Last sender (if available from recent transfers)
    - Last transfer timestamp
    - Recent notifications (last 50)
    """
    try:
        # Import Notification model
        from blueprints.p2.models import Notification
        
        # Basic user info
        user_type = getattr(current_user, 'user_type', 'guest')
        used_bytes = int(current_user.total_data_size or 0)
        
        # Storage limits
        total_bytes = None
        remaining_bytes = None
        if user_type == 'guest':
            total_bytes = 50 * 1024 * 1024  # 50MB for guests
            remaining_bytes = max(0, total_bytes - used_bytes)
        
        # Count total images by checking upload folder
        total_images = 0
        try:
            if os.path.exists(UPLOAD_FOLDER):
                user_prefix = f"{current_user.id}_"
                allowed_exts = {'.webp'}
                allowed_exts |= {f".{ext.lower().lstrip('.')}" for ext in ALLOWED_EXTENSIONS}
                total_images = sum(
                    1 for filename in os.listdir(UPLOAD_FOLDER)
                    if filename.startswith(user_prefix)
                    and os.path.splitext(filename)[1].lower() in allowed_exts
                )
        except Exception as e:
            print(f"Error counting images: {e}")
        
        # Find most recent item (note/board) to determine last transfer activity
        last_sender = None
        last_transfer_time = None
        
        try:
            # Get most recent note and board
            recent_note = File.query.filter_by(owner_id=current_user.id, type='note').order_by(File.created_at.desc()).first()
            recent_board = File.query.filter_by(owner_id=current_user.id, type='whiteboard').order_by(File.created_at.desc()).first()
            
            # Determine which is more recent
            most_recent = None
            if recent_note and recent_board:
                most_recent = recent_note if recent_note.created_at > recent_board.created_at else recent_board
            elif recent_note:
                most_recent = recent_note
            elif recent_board:
                most_recent = recent_board
            
            if most_recent:
                last_transfer_time = most_recent.created_at.isoformat()
                # For now, we don't track sender info, but could be added later
                # by adding a 'sent_by_user_id' field to Note/Board models
                last_sender = "System"  # Placeholder
        except Exception as e:
            print(f"Error fetching last transfer: {e}")
        
        # Fetch user's notifications (last 50, most recent first)
        notifications = []
        try:
            user_notifications = (
                Notification.query
                .filter_by(user_id=current_user.id)
                .order_by(Notification.timestamp.desc())
                .limit(50)
                .all()
            )
            notifications = [notif.to_dict() for notif in user_notifications]
        except Exception as e:
            print(f"Error fetching notifications: {e}")
        
        return jsonify({
            'user_type': user_type,
            'storage_used': used_bytes,
            'storage_total': total_bytes,
            'storage_remaining': remaining_bytes,
            'total_images': total_images,
            'last_sender': last_sender,
            'last_transfer_time': last_transfer_time,
            'notifications': notifications
        })
        
    except Exception as e:
        print(f"Error in telemetry_data endpoint: {e}")
        traceback.print_exc()
        return jsonify({
            'user_type': 'guest',
            'storage_used': 0,
            'storage_total': None,
            'storage_remaining': None,
            'total_images': 0,
            'last_sender': None,
            'last_transfer_time': None,
            'notifications': []
        }), 500


@p2_blueprint.route('/api/export_item_jsonl')
@login_required
def export_item_jsonl():
    """Export an item (note, board, folder, file) as JSONL (JSON Lines) format.
    
    JSONL format: one JSON object per line, making it easy to process line-by-line.
    Each line contains complete metadata and content for the item.
    """
    item_type = request.args.get('type', '')
    item_id = request.args.get('id', type=int)
    
    if not item_type or not item_id:
        return jsonify({'error': 'Missing type or id parameter'}), 400
    
    try:
        import json
        from io import BytesIO
        
        jsonl_lines = []
        
        if item_type == 'folder':
            folder = Folder.query.filter_by(id=item_id, owner_id=current_user.id).first()
            if not folder:
                return jsonify({'error': 'Folder not found'}), 404
            
            # Export folder metadata
            folder_data = {
                'type': 'folder',
                'id': folder.id,
                'name': folder.name,
                'description': folder.description or '',
                'created_at': folder.created_at.isoformat() if folder.created_at else None,
                'last_modified': folder.last_modified.isoformat() if folder.last_modified else None,
                'is_public': folder.is_public,
                'parent_id': folder.parent_id
            }
            jsonl_lines.append(json.dumps(folder_data))
            
            # Export all items in folder (recursive)
            def export_folder_contents(folder_id, depth=0):
                # Get all child items
                child_folders = Folder.query.filter_by(parent_id=folder_id, owner_id=current_user.id).all()
                child_files = File.query.filter_by(folder_id=folder_id, owner_id=current_user.id).all()
                
                for child_folder in child_folders:
                    folder_data = {
                        'type': 'folder',
                        'id': child_folder.id,
                        'name': child_folder.name,
                        'description': child_folder.description or '',
                        'created_at': child_folder.created_at.isoformat() if child_folder.created_at else None,
                        'last_modified': child_folder.last_modified.isoformat() if child_folder.last_modified else None,
                        'is_public': child_folder.is_public,
                        'parent_id': child_folder.parent_id,
                        'depth': depth + 1
                    }
                    jsonl_lines.append(json.dumps(folder_data))
                    export_folder_contents(child_folder.id, depth + 1)
                
                for file_item in child_files:
                    file_data = {
                        'type': file_item.type,
                        'id': file_item.id,
                        'title': file_item.title,
                        'folder_id': file_item.folder_id,
                        'created_at': file_item.created_at.isoformat() if file_item.created_at else None,
                        'last_modified': file_item.last_modified.isoformat() if file_item.last_modified else None,
                        'is_public': file_item.is_public,
                        'content_text': file_item.content_text,
                        'content_html': file_item.content_html,
                        'content_json': file_item.content_json,
                        'metadata_json': file_item.metadata_json,
                        'depth': depth + 1
                    }
                    jsonl_lines.append(json.dumps(file_data))
            
            export_folder_contents(folder.id)
            
        elif item_type in VALID_FILE_TYPES or item_type == 'file':
            # Export single file (supports all valid file types defined in models.VALID_FILE_TYPES)
            file_item = File.query.filter_by(id=item_id, owner_id=current_user.id).first()
            if not file_item:
                return jsonify({'error': 'Item not found'}), 404
            
            file_data = {
                'type': file_item.type,
                'id': file_item.id,
                'title': file_item.title,
                'folder_id': file_item.folder_id,
                'created_at': file_item.created_at.isoformat() if file_item.created_at else None,
                'last_modified': file_item.last_modified.isoformat() if file_item.last_modified else None,
                'is_public': file_item.is_public,
                'content_text': file_item.content_text,
                'content_html': file_item.content_html,
                'content_json': file_item.content_json,
                'metadata_json': file_item.metadata_json
            }
            jsonl_lines.append(json.dumps(file_data))
        else:
            return jsonify({'error': f'Unsupported item type: {item_type}'}), 400
        
        # Create JSONL file in memory
        jsonl_content = '\n'.join(jsonl_lines)
        buffer = BytesIO(jsonl_content.encode('utf-8'))
        buffer.seek(0)
        
        # Get item name for filename
        if item_type == 'folder':
            item_name = folder.name
        else:
            item_name = file_item.title
        
        safe_name = ''.join(c if c.isalnum() or c in ('_', '-') else '_' for c in item_name)
        filename = f"{safe_name}.jsonl"
        
        return send_file(
            buffer,
            mimetype='application/jsonl',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"Error exporting as JSONL: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Failed to export item'}), 500


@p2_blueprint.route('/user_search')
@login_required
def user_search():
    q = request.args.get('q', '').strip()
    users = []
    if q:
        # Basic case-insensitive search by username or email
        users = User.query.filter(
            (User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        ).limit(50).all()

    return render_template('p2/profile_search_results.html', q=q, users=users)


@p2_blueprint.route('/users/api/search')
@login_required
def users_api_search():
    """Return JSON list of users matching a search query.

    The response is: { success: True, users: [{ id, username, email, pinned}] }
    """
    q = request.args.get('q', '').strip()
    users = []
    try:
        if q:
            users = User.query.filter(
                (User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
            ).limit(50).all()

        # compute pinned state for current user
        prefs = current_user.user_prefs or {}
        pinned = prefs.get('pinned_users', []) or []
        normalized = []
        for x in pinned:
            try:
                normalized.append(int(x))
            except Exception:
                continue
        pinned_set = set(normalized)

        users_out = []
        for u in users:
            users_out.append({
                'id': u.id,
                'username': u.username,
                'email': u.email or '',
                'pinned': u.id in pinned_set
            })

        return jsonify({'success': True, 'users': users_out})
    except Exception as e:
        print(f"[error] users_api_search exception: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'users': [], 'message': 'Failed to search users'}), 500


def _search_json_for_url(obj, url_path):
    """
    Recursively search JSON structure for a URL string.
    Returns True if found, False otherwise.
    """
    if obj is None:
        return False
    if isinstance(obj, str):
        return url_path in obj
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _search_json_for_url(value, url_path):
                return True
    if isinstance(obj, list):
        for item in obj:
            if _search_json_for_url(item, url_path):
                return True
    return False


@p2_blueprint.route('/assets')
@login_required
def assets():
    """Show a gallery of user-uploaded images (images stored in static/uploads/images)."""
    user_id = current_user.id
    images = []
    try:
        for fname in os.listdir(UPLOAD_FOLDER):
            if not fname.startswith(f"{user_id}_"):
                continue
            file_path = os.path.join(UPLOAD_FOLDER, fname)
            if not os.path.isfile(file_path):
                continue
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)

            used_in = []
            try:
                url_path = f"/static/uploads/images/{fname}"
                # Find notes that reference this image
                note_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'note',
                    File.content_html.contains(url_path)
                ).all()
                for n in note_matches:
                    used_in.append({
                        'type': 'note',
                        'id': n.id,
                        'title': n.title or f'Note {n.id}',
                        'url': url_for('notes.edit_note', note_id=n.id)
                    })
                # Find boards that reference this image (in content_json or description)
                board_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'whiteboard'
                ).all()
                for b in board_matches:
                    # Check content_json (properly traverse JSON structure)
                    if _search_json_for_url(b.content_json, url_path):
                        used_in.append({
                            'type': 'board',
                            'id': b.id,
                            'title': b.title or f'Board {b.id}',
                            'url': url_for('boards.edit_board', board_id=b.id)
                        })
                    # Check metadata_json description
                    elif b.metadata_json and _search_json_for_url(b.metadata_json.get('description', ''), url_path):
                        used_in.append({
                            'type': 'board',
                            'id': b.id,
                            'title': b.title or f'Board {b.id}',
                            'url': url_for('boards.edit_board', board_id=b.id)
                        })
                
                # Find infinite whiteboards that reference this image
                infinite_board_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'proprietary_infinite_whiteboard'
                ).all()
                for ib in infinite_board_matches:
                    # Check content_json (image objects have src property in the objects array)
                    if _search_json_for_url(ib.content_json, url_path):
                        used_in.append({
                            'type': 'infinite_whiteboard',
                            'id': ib.id,
                            'title': ib.title or f'Infinite Whiteboard {ib.id}',
                            'url': url_for('infinite_boards.edit_infinite_board', board_id=ib.id)
                        })
                    # Check metadata_json description
                    elif ib.metadata_json and _search_json_for_url(ib.metadata_json.get('description', ''), url_path):
                        used_in.append({
                            'type': 'infinite_whiteboard',
                            'id': ib.id,
                            'title': ib.title or f'Infinite Whiteboard {ib.id}',
                            'url': url_for('infinite_boards.edit_infinite_board', board_id=ib.id)
                        })
            except Exception:
                used_in = []

            images.append({
                'filename': fname,
                'url': f"/static/uploads/images/{fname}",
                'size': size,
                'mtime': datetime.utcfromtimestamp(mtime),
                'used_in': used_in,
            })
    except Exception as e:
        print(f"Error reading upload folder: {e}")
    print(f"DEBUG: assets() - found {len(images)} images for user {user_id}: {[i['filename'] for i in images]}")

    images.sort(key=lambda x: x['mtime'], reverse=True)
    total_size = sum(i['size'] for i in images)
    # Split assets into 'in_use' and 'reserve' on server-side to avoid template tests
    in_use = [i for i in images if i.get('used_in')]
    reserve = [i for i in images if not i.get('used_in')]
    return render_template('p2/assets.html', images=images, total_size=total_size, in_use=in_use, reserve=reserve)


@p2_blueprint.route('/assets/list')
@login_required
def assets_list():
    """Return JSON list of user-uploaded images for a gallery.

    Returns JSON: { images: [{ filename, url, size, mtime, used_in: [] }, ...] }
    """
    user_id = current_user.id
    images = []
    limit = int(request.args.get('limit', 200))
    try:
        for fname in os.listdir(UPLOAD_FOLDER):
            if not fname.startswith(f"{user_id}_"):
                continue
            file_path = os.path.join(UPLOAD_FOLDER, fname)
            if not os.path.isfile(file_path):
                continue
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            url_path = f"/static/uploads/images/{fname}"
            used_in = []
            try:
                # Check if this URL appears in any Note or Board for this user
                note_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'note',
                    File.content_html.contains(url_path)
                ).all()
                for n in note_matches:
                    used_in.append({'type': 'note', 'id': n.id, 'title': n.title or f'Note {n.id}', 'url': url_for('notes.edit_note', note_id=n.id)})
                # For boards, check content_json and metadata_json description
                board_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'whiteboard'
                ).all()
                for b in board_matches:
                    # Check content_json (properly traverse JSON structure)
                    if _search_json_for_url(b.content_json, url_path):
                        used_in.append({'type': 'board', 'id': b.id, 'title': b.title or f'Board {b.id}', 'url': url_for('boards.edit_board', board_id=b.id)})
                    # Check metadata_json description
                    elif b.metadata_json and _search_json_for_url(b.metadata_json.get('description', ''), url_path):
                        used_in.append({'type': 'board', 'id': b.id, 'title': b.title or f'Board {b.id}', 'url': url_for('boards.edit_board', board_id=b.id)})
                # For infinite whiteboards, check content_json and metadata_json description
                infinite_board_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'proprietary_infinite_whiteboard'
                ).all()
                for ib in infinite_board_matches:
                    # Check content_json (image objects have src property in the objects array)
                    if _search_json_for_url(ib.content_json, url_path):
                        used_in.append({'type': 'infinite_whiteboard', 'id': ib.id, 'title': ib.title or f'Infinite Whiteboard {ib.id}', 'url': url_for('infinite_boards.edit_infinite_board', board_id=ib.id)})
                    # Check metadata_json description
                    elif ib.metadata_json and _search_json_for_url(ib.metadata_json.get('description', ''), url_path):
                        used_in.append({'type': 'infinite_whiteboard', 'id': ib.id, 'title': ib.title or f'Infinite Whiteboard {ib.id}', 'url': url_for('infinite_boards.edit_infinite_board', board_id=ib.id)})
            except Exception:
                used_in = []
            images.append({
                'filename': fname,
                'url': url_path,
                'size': size,
                'mtime': mtime,
                'mtime_iso': datetime.utcfromtimestamp(mtime).isoformat() + 'Z',
                'used_in': used_in
            })
    except Exception as e:
        print(f"Error listing upload folder: {e}")
    print(f"DEBUG: assets_list() - found {len(images)} images for user {user_id}: {[i['filename'] for i in images]}")
    images.sort(key=lambda x: x['mtime'], reverse=True)
    if limit and len(images) > limit:
        images = images[:limit]
    # Convert mtime to isoformat string for JSON response
    for img in images:
        img['mtime'] = img.get('mtime_iso')
        if 'mtime_iso' in img: del img['mtime_iso']
    # Consider session-marked-as-used assets not yet saved by the user
    try:
        marked = session.get('assets_marked_used') or []
        if marked:
            for img in images:
                if img['filename'] in marked:
                    if not img.get('used_in'):
                        img['used_in'] = []
                    img['used_in'].append({'type': 'session', 'id': None, 'title': 'Inserted (unsaved)', 'url': None})
    except Exception:
        pass
    return jsonify({'images': images})


@p2_blueprint.route('/assets/debug/<int:uid>')
@login_required
def assets_debug(uid):
    """Debug endpoint: list all file names in upload folder for a user and show which notes/boards reference them.
    Access allowed only if current_user.is_admin or current_user.id == uid."""
    from flask import abort
    if not (getattr(current_user, 'is_admin', False) or current_user.id == int(uid)):
        abort(403)
    files = []
    try:
        for fname in os.listdir(UPLOAD_FOLDER):
            if not fname.startswith(f"{uid}_"):
                continue
            file_path = os.path.join(UPLOAD_FOLDER, fname)
            if not os.path.isfile(file_path):
                continue
            size = os.path.getsize(file_path)
            mtime = os.path.getmtime(file_path)
            files.append({'filename': fname, 'url': f"/static/uploads/images/{fname}", 'size': size, 'mtime': mtime})
    except Exception as e:
        print(f"DEBUG assets_debug - reading upload folder for user {uid} failed: {e}")
        return jsonify({'error': 'failed to read uploads', 'exception': str(e)}), 500
    # Also check DB references
    try:
        for f in files:
            used_in = []
            url_path = f"/static/uploads/images/{f['filename']}"
            note_matches = File.query.filter(
                File.owner_id == uid,
                File.type == 'note',
                File.content_html.contains(url_path)
            ).all()
            for n in note_matches:
                used_in.append({'type': 'note', 'id': n.id, 'title': n.title or f'Note {n.id}'})
            # For boards, check content_json and metadata_json description
            board_matches = File.query.filter(
                File.owner_id == uid,
                File.type == 'whiteboard'
            ).all()
            for b in board_matches:
                # Check content_json (properly traverse JSON structure)
                if _search_json_for_url(b.content_json, url_path):
                    used_in.append({'type': 'board', 'id': b.id, 'title': b.title or f'Board {b.id}'})
                # Check metadata_json description
                elif b.metadata_json and _search_json_for_url(b.metadata_json.get('description', ''), url_path):
                    used_in.append({'type': 'board', 'id': b.id, 'title': b.title or f'Board {b.id}'})
            # For infinite whiteboards, check content_json and metadata_json description
            infinite_board_matches = File.query.filter(
                File.owner_id == uid,
                File.type == 'proprietary_infinite_whiteboard'
            ).all()
            for ib in infinite_board_matches:
                # Check content_json (image objects have src property in the objects array)
                if _search_json_for_url(ib.content_json, url_path):
                    used_in.append({'type': 'infinite_whiteboard', 'id': ib.id, 'title': ib.title or f'Infinite Whiteboard {ib.id}'})
                # Check metadata_json description
                elif ib.metadata_json and _search_json_for_url(ib.metadata_json.get('description', ''), url_path):
                    used_in.append({'type': 'infinite_whiteboard', 'id': ib.id, 'title': ib.title or f'Infinite Whiteboard {ib.id}'})
            f['used_in'] = used_in
    except Exception as e:
        print(f"DEBUG assets_debug - DB lookup failed: {e}")
    return jsonify({'files': files})


@p2_blueprint.route('/assets/mark_used', methods=['POST'])
@login_required
def assets_mark_used():
    """Mark an asset as used in the current session (unsaved note). This helps the UI reflect changed usage status before the note is saved."""
    if request.is_json:
        data = request.get_json(force=True) or {}
        filename = (data.get('filename') or '').strip()
    else:
        filename = (request.form.get('filename') or '').strip()
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    # Basic safety check
    if not filename.startswith(f"{current_user.id}_"):
        return jsonify({'error': 'Unauthorized'}), 403
    marked = session.get('assets_marked_used', [])
    if filename not in marked:
        marked.append(filename)
        session['assets_marked_used'] = marked
    return jsonify({'success': True, 'filename': filename})


@p2_blueprint.route('/assets/unmark_used', methods=['POST'])
@login_required
def assets_unmark_used():
    if request.is_json:
        data = request.get_json(force=True) or {}
        filename = (data.get('filename') or '').strip()
    else:
        filename = (request.form.get('filename') or '').strip()
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    # Basic safety: only allow manipulating your own session-marked filenames
    if not filename.startswith(f"{current_user.id}_"):
        return jsonify({'error': 'Unauthorized'}), 403
    marked = session.get('assets_marked_used', [])
    if filename in marked:
        try:
            marked.remove(filename)
        except Exception:
            pass
        session['assets_marked_used'] = marked
    return jsonify({'success': True})


@p2_blueprint.route('/assets/delete', methods=['POST'])
@login_required
def assets_delete():
    """Delete an uploaded picture belonging to this user.
    Accepts form field 'filename'. """
    if request.is_json:
        data = request.get_json(force=True)
        filename = data.get('filename')
    else:
        filename = request.form.get('filename')
    if not filename:
        return jsonify(error='No filename provided'), 400
    if not filename.startswith(f"{current_user.id}_"):
        return jsonify(error='Unauthorized'), 403
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify(error='Not found'), 404
    try:
        file_size = os.path.getsize(file_path)
        os.remove(file_path)
        try:
            update_user_data_size(current_user, -file_size)
        except Exception as e:
            print(f"Warning: failed to update user data size: {e}")
        # Ensure filename is not left marked in session (e.g., deleted while unsaved)
        try:
            marked = session.get('assets_marked_used', []) or []
            if filename in marked:
                marked = [m for m in marked if m != filename]
                session['assets_marked_used'] = marked
                session.modified = True
        except Exception:
            pass
        return jsonify(success=True)
    except Exception as e:
        print(f"Failed to delete image {filename}: {e}")
        return jsonify(error='Delete failed'), 500


@p2_blueprint.route('/assets/unused')
@login_required
def assets_unused():
    """Return JSON list of unused images for the current user."""
    user_id = current_user.id
    unused = []
    try:
        for fname in os.listdir(UPLOAD_FOLDER):
            if not fname.startswith(f"{user_id}_"):
                continue
            file_path = os.path.join(UPLOAD_FOLDER, fname)
            if not os.path.isfile(file_path):
                continue
            url_path = f"/static/uploads/images/{fname}"
            used_in = []
            try:
                note_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'note',
                    File.content_html.contains(url_path)
                ).all()
                for n in note_matches:
                    used_in.append({'type': 'note', 'id': n.id, 'title': n.title or f'Note {n.id}', 'url': url_for('notes.edit_note', note_id=n.id)})
                # For boards, check content_json and metadata_json description
                board_matches = File.query.filter(
                    File.owner_id == user_id,
                    File.type == 'whiteboard'
                ).all()
                for b in board_matches:
                    content_str = str(b.content_json) if b.content_json else ''
                    desc_str = b.metadata_json.get('description', '') if b.metadata_json else ''
                    if url_path in content_str or url_path in desc_str:
                        used_in.append({'type': 'board', 'id': b.id, 'title': b.title or f'Board {b.id}', 'url': url_for('boards.edit_board', board_id=b.id)})
            except Exception:
                used_in = []
            if not used_in:
                size = os.path.getsize(file_path)
                mtime = os.path.getmtime(file_path)
                unused.append({'filename': fname, 'url': url_path, 'size': size, 'mtime': datetime.utcfromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')})
    except Exception as e:
        print(f"Error scanning for unused images: {e}")
    return jsonify(images=unused)


@p2_blueprint.route('/assets/cleanup', methods=['POST'])
@login_required
def assets_cleanup():
    """Delete unused images belonging to the current user and return a JSON report.
    Request body (JSON): { filenames: ["<user>_<hash>.webp", ...] } - If omitted, delete all unused images.
    """
    if request.is_json:
        data = request.get_json(force=True)
    else:
        data = {}
    filenames = data.get('filenames')

    # If filenames were provided, verify they're owned and unused; otherwise compute unused.
    to_delete = []
    try:
        if filenames and isinstance(filenames, list):
            for fn in filenames:
                if not fn.startswith(f"{current_user.id}_"):
                    continue
                file_path = os.path.join(UPLOAD_FOLDER, fn)
                if os.path.exists(file_path):
                    # verify unused
                    url_path = f"/static/uploads/images/{fn}"
                    used = False
                    try:
                        # Check notes
                        if File.query.filter(
                            File.owner_id == current_user.id,
                            File.type == 'note',
                            File.content_html.contains(url_path)
                        ).first():
                            used = True
                        # Check boards (content_json and metadata_json description)
                        if not used:
                            board_matches = File.query.filter(
                                File.owner_id == current_user.id,
                                File.type == 'whiteboard'
                            ).all()
                            for b in board_matches:
                                content_str = str(b.content_json) if b.content_json else ''
                                desc_str = b.metadata_json.get('description', '') if b.metadata_json else ''
                                if url_path in content_str or url_path in desc_str:
                                    used = True
                                    break
                    except Exception:
                        used = False
                    if not used:
                        to_delete.append(fn)
        else:
            # compute all unused
            for fname in os.listdir(UPLOAD_FOLDER):
                if not fname.startswith(f"{current_user.id}_"):
                    continue
                file_path = os.path.join(UPLOAD_FOLDER, fname)
                if not os.path.isfile(file_path):
                    continue
                url_path = f"/static/uploads/images/{fname}"
                used = False
                try:
                    # Check notes
                    if File.query.filter(
                        File.owner_id == current_user.id,
                        File.type == 'note',
                        File.content_html.contains(url_path)
                    ).first():
                        used = True
                    # Check boards (content_json and metadata_json description)
                    if not used:
                        board_matches = File.query.filter(
                            File.owner_id == current_user.id,
                            File.type == 'whiteboard'
                        ).all()
                        for b in board_matches:
                            content_str = str(b.content_json) if b.content_json else ''
                            desc_str = b.metadata_json.get('description', '') if b.metadata_json else ''
                            if url_path in content_str or url_path in desc_str:
                                used = True
                                break
                except Exception:
                    used = False
                if not used:
                    to_delete.append(fname)
    except Exception as e:
        print(f"Error computing cleanup list: {e}")

    deleted = []
    failed = []
    total_freed = 0
    for fn in to_delete:
        try:
            file_path = os.path.join(UPLOAD_FOLDER, fn)
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                os.remove(file_path)
                total_freed += size
                deleted.append(fn)
        except Exception as e:
            print(f"Failed to delete {fn}: {e}")
            failed.append(fn)
    if deleted:
        try:
            update_user_data_size(current_user, -total_freed)
        except Exception as e:
            print(f"Failed to update user size post cleanup: {e}")

    return jsonify({ 'deleted': deleted, 'failed': failed, 'freed_bytes': total_freed })


@p2_blueprint.route('/assets/upload', methods=['POST'])
@login_required
def assets_upload():
    """Upload one or more images for the current user. Accepts 'files' in multipart-form.
    Returns JSON with a list of uploaded files: { uploaded: [{filename, url, success, error}], total_freed: ... }
    """
    results = []
    # Collect files: either 'files' field (multiple) or single 'file'
    files = request.files.getlist('files') or ([] if 'file' not in request.files else [request.files['file']])
    if not files:
        return jsonify(error='No files provided'), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    for file in files:
        if not file or file.filename == '':
            results.append({'filename': '', 'success': False, 'error': 'No filename provided'})
            continue
        if not allowed_file(file.filename):
            results.append({'filename': file.filename, 'success': False, 'error': 'Invalid file type'})
            continue
        # check file size
        try:
            file.stream.seek(0, os.SEEK_END)
            file_size = file.stream.tell()
            file.stream.seek(0)
        except Exception:
            # fallback to reading bytes
            data = file.read()
            file_size = len(data)
            # reset file stream
            file.stream = BytesIO(data)

        if file_size > MAX_IMAGE_SIZE:
            results.append({'filename': file.filename, 'success': False, 'error': 'File too large'})
            continue

        # Save temp file
        import uuid
        from io import BytesIO
        temp_name = f"temp_original_{uuid.uuid4().hex}"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_name)
        try:
            file.save(temp_path)
            image_hash = get_image_hash(temp_path)
            existing = get_existing_image_by_hash(current_user.id, image_hash)
            if existing:
                # clean up temp
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
                try:
                    existing_name = os.path.basename(existing)
                    existing_path = os.path.join(UPLOAD_FOLDER, existing_name)
                    existing_size = os.path.getsize(existing_path) if os.path.exists(existing_path) else None
                    existing_mtime = datetime.utcfromtimestamp(os.path.getmtime(existing_path)).strftime('%Y-%m-%d %H:%M') if os.path.exists(existing_path) else None
                except Exception:
                    existing_size = None
                    existing_mtime = None
                results.append({'filename': existing_name, 'url': existing, 'success': True, 'deduped': True, 'size': existing_size, 'mtime': existing_mtime})
                continue

            # Final filename always WebP (or fallback in convert_to_webp)
            final_name = f"{current_user.id}_{image_hash}.webp"
            final_path = os.path.join(UPLOAD_FOLDER, final_name)
            out_path = convert_to_webp(temp_path, final_path)
            # remove temp original
            try:
                os.remove(temp_path)
            except Exception:
                pass

            if os.path.exists(out_path):
                final_file_size = os.path.getsize(out_path)
                if not check_guest_limit(current_user, final_file_size):
                    # remove file and report
                    try:
                        os.remove(out_path)
                    except Exception:
                        pass
                    results.append({'filename': os.path.basename(out_path), 'success': False, 'error': 'Storage limit exceeded'})
                    continue
                try:
                    update_user_data_size(current_user, final_file_size)
                except Exception:
                    pass
                url = f"/static/uploads/images/{os.path.basename(out_path)}"
                try:
                    mtime = datetime.utcfromtimestamp(os.path.getmtime(out_path)).strftime('%Y-%m-%d %H:%M')
                except Exception:
                    mtime = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
                results.append({'filename': os.path.basename(out_path), 'url': url, 'success': True, 'size': final_file_size, 'mtime': mtime})
            else:
                results.append({'filename': file.filename, 'success': False, 'error': 'Failed to convert/save'})
        except Exception as e:
            print(f"Error uploading asset {file.filename}: {e}")
            results.append({'filename': file.filename, 'success': False, 'error': 'Upload failed'})

    # Report total uploaded bytes (only for newly saved files, exclude deduped)
    uploaded_total = sum(r.get('size', 0) for r in results if r.get('success') and not r.get('deduped'))
    try:
        user_total = int(current_user.total_data_size or 0)
    except Exception:
        user_total = None
    return jsonify(uploaded=results, uploaded_bytes=uploaded_total, user_total_bytes=user_total)


@p2_blueprint.route('/edit_image/<filename>')
@login_required
def edit_image(filename):
    """Image editor page using TOAST UI Image Editor"""
    # Verify user owns this image (filename format: {user_id}_{hash}.webp)
    prefix = f"{current_user.id}_"
    if not filename.startswith(prefix):
        abort(403)  # Forbidden - not user's image
    
    image_url = f"/static/uploads/images/{filename}"
    return render_template('p2/edit_image.html', filename=filename, image_url=image_url)


@p2_blueprint.route('/save_image/<filename>', methods=['POST'])
@login_required
def save_image(filename):
    """Save edited image from TOAST UI editor"""
    # Verify user owns this image
    prefix = f"{current_user.id}_"
    if not filename.startswith(prefix):
        return jsonify(error='Forbidden'), 403
    
    try:
        # Get base64 image data from request
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify(error='No image data provided'), 400
        
        import base64
        from io import BytesIO
        
        # Parse data URI
        image_data = data['image']
        if image_data.startswith('data:image'):
            # Strip header: data:image/png;base64,{data}
            image_data = image_data.split(',', 1)[1]
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        
        # Calculate size difference for storage quota
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        old_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Save to temporary file first
        import uuid
        temp_name = f"temp_edit_{uuid.uuid4().hex}.png"
        temp_path = os.path.join(UPLOAD_FOLDER, temp_name)
        
        with open(temp_path, 'wb') as f:
            f.write(image_bytes)
        
        # Convert to WebP and overwrite original
        final_path = convert_to_webp(temp_path, file_path)
        
        # Clean up temp file
        try:
            os.remove(temp_path)
        except Exception:
            pass
        
        # Calculate new size and update quota
        new_size = os.path.getsize(final_path)
        size_delta = new_size - old_size
        
        if size_delta > 0:
            # File got bigger - check quota
            if not check_guest_limit(current_user, size_delta):
                # Restore original if possible - for now just report error
                return jsonify(error='Storage limit exceeded'), 400
            update_user_data_size(current_user, size_delta)
        elif size_delta < 0:
            # File got smaller - credit the difference
            update_user_data_size(current_user, size_delta)
        
        return jsonify(success=True, filename=filename, size=new_size)
        
    except Exception as e:
        print(f"Error saving edited image {filename}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(error=str(e)), 500


@p2_blueprint.route('/users/<int:user_id>/toggle_pin', methods=['GET', 'POST'])
@login_required
def toggle_pin_user(user_id):
    """Toggle pin/unpin for a user in the current_user's preferences."""
    try:
        print(f"[debug] toggle_pin_user called by user_id={getattr(current_user, 'id', None)} target_user={user_id}")
        prefs = current_user.user_prefs or {}
        print(f"[debug] current_user.user_prefs (before): {prefs}")
        if not isinstance(prefs, dict):
            prefs = {}

        pinned = prefs.get('pinned_users', []) or []
        # normalize to list of ints (handle strings stored in JSON)
        normalized = []
        for x in pinned:
            try:
                normalized.append(int(x))
            except Exception:
                # ignore values that can't be converted
                continue
        pinned = normalized

        if user_id in pinned:
            pinned.remove(user_id)
            flash('User unpinned.')
            result_flag = 'unpinned'
        else:
            pinned.append(user_id)
            flash('User pinned.')
            result_flag = 'pinned'

        print(f"[debug] attempting to persist pinned list for user {current_user.id}: {pinned}")

        prefs['pinned_users'] = pinned
        current_user.user_prefs = prefs
        # Ensure SQLAlchemy detects the JSON field change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(current_user, 'user_prefs')
        db.session.add(current_user)
        try:
            db.session.commit()
            # fetch fresh copy from DB to verify persistence
            fresh = User.query.get(current_user.id)
            print(f"[debug] commit successful. fresh.user_prefs={getattr(fresh, 'user_prefs', None)}")
        except Exception as commit_exc:
            print(f"[error] commit failed: {commit_exc}")
            print(traceback.format_exc())
            raise
    except Exception as e:
        db.session.rollback()
        print(f"[error] toggle_pin_user exception: {e}")
        print(traceback.format_exc())
        flash('Unable to update pinned users.')
        result_flag = 'error'

    # redirect back to where the request came from (fallback to search)
    # accept next from either form data or query string (GET/POST friendly)
    next_url = request.values.get('next') or request.referrer or url_for('p2_bp.user_search')
    # append a short query flag so the redirected page can show immediate feedback
    try:
        sep = '&' if '?' in next_url else '?'
        next_url_with_flag = f"{next_url}{sep}pin_result={result_flag}"
    except Exception:
        next_url_with_flag = next_url
    print(f"[debug] redirecting to: {next_url_with_flag}")
    return redirect(next_url_with_flag)


@p2_blueprint.route('/users/<int:user_id>/toggle_pin_ajax', methods=['POST'])
@login_required
def toggle_pin_user_ajax(user_id):
    """AJAX-friendly JSON endpoint to toggle pin/unpin for a user.

    Returns JSON: { success: bool, pinned: bool, message: str }
    """
    try:
        prefs = current_user.user_prefs or {}
        if not isinstance(prefs, dict):
            prefs = {}

        pinned = prefs.get('pinned_users', []) or []
        # normalize to list of ints (handle strings stored in JSON)
        normalized = []
        for x in pinned:
            try:
                normalized.append(int(x))
            except Exception:
                continue
        pinned = normalized

        if user_id in pinned:
            pinned.remove(user_id)
            pinned_state = False
            message = 'User unpinned.'
        else:
            pinned.append(user_id)
            pinned_state = True
            message = 'User pinned.'

        prefs['pinned_users'] = pinned
        current_user.user_prefs = prefs
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(current_user, 'user_prefs')
        db.session.add(current_user)
        db.session.commit()
        return jsonify({'success': True, 'pinned': pinned_state, 'message': message})
    except Exception as e:
        try:
            db.session.rollback()
        except:
            pass
        print(f"[error] toggle_pin_user_ajax exception: {e}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'pinned': None, 'message': 'Unable to update pinned users.'}), 500


@p2_blueprint.route('/users/<int:user_id>')
def view_user(user_id):
    user = User.query.get_or_404(user_id)

    # Collect public items for this user
    try:
        from blueprints.p2.models import Folder, File
        # Load all public folders for the user
        all_public_folders = Folder.query.filter_by(user_id=user.id, is_public=True).all()
        public_folder_ids = {f.id for f in all_public_folders}

        # Top-level public folders are those whose parent is not a public folder
        public_folders = [f for f in all_public_folders if not (f.parent_id in public_folder_ids)]

        # Public items not already covered by a public folder tree
        base_query = File.query.filter(File.owner_id == user.id, File.is_public == True)
        if public_folder_ids:
            base_query = base_query.filter(~File.folder_id.in_(list(public_folder_ids)))

        # Get ALL public files (unified approach)
        all_public_files = base_query.all()
    except Exception as e:
        print(f"Error loading public items for user {user_id}: {e}")
        public_folders = []
        all_public_files = []

    # Group files by type for sectioned display
    files_by_type = {}
    for file_obj in all_public_files:
        file_type = file_obj.type
        if file_type not in files_by_type:
            files_by_type[file_type] = []
        files_by_type[file_type].append(file_obj)

    return render_template('p2/public_profile.html', user=user, folders=public_folders, files_by_type=files_by_type)


@p2_blueprint.route('/public/note/<int:note_id>')
def public_view_note(note_id):
    note = File.query.get_or_404(note_id)
    # allow if owner or public
    if (not (getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None) == note.owner_id)) and not getattr(note, 'is_public', False):
        abort(403)
    # sanitize note content for public rendering
    try:
        allowed_tags = [
            'p', 'br', 'b', 'strong', 'i', 'em', 'u', 'a', 'ul', 'ol', 'li',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 'blockquote', 'span', 'div'
        ]
        allowed_attrs = {
            'a': ['href', 'title', 'rel', 'target'],
            'img': ['src', 'alt', 'title']
        }
        cleaned = bleach.clean(note.content_html or '', tags=allowed_tags, attributes=allowed_attrs, protocols=['http', 'https', 'data'], strip=True)
        # remove external images that are not uploads or data URIs
        try:
            soup = BeautifulSoup(cleaned, 'html.parser')
            for img in soup.find_all('img'):
                src = str(img.get('src') or '')
                if not (src.startswith('/static/uploads/images/') or src.startswith('static/uploads/images/') or src.startswith('/uploads/images/') or src.startswith('uploads/images/') or src.startswith('data:image/')):
                    img.decompose()
            sanitized_content = str(soup)
        except Exception:
            sanitized_content = cleaned
    except Exception:
        sanitized_content = ''

    # Parse description metadata for public rendering (supports JSON or plain text)
    try:
        description_value = (note.metadata_json or {}).get('description', '') if isinstance(note.metadata_json, dict) else note.description
        descriptions, description_readable, parse_failed = parse_description_field(description_value)
        note.descriptions = descriptions
        note.description_readable = description_readable
        note.description_parse_failed = parse_failed
    except Exception:
        print(f"DEBUG: Failed to parse description for public Note {note.id}; ignoring description.")
        note.description_parse_failed = True

    return render_template('p2/public_note.html', note=note, sanitized_content=sanitized_content)


@p2_blueprint.route('/public/board/<int:board_id>')
def public_view_board(board_id):
    board = File.query.get_or_404(board_id)
    if (not (getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None) == board.owner_id)) and not getattr(board, 'is_public', False):
        abort(403)

    # Render MioDraw in read-only mode for public viewers
    return render_template(
        'p2/file_edit_proprietary_whiteboard.html',
        board=board,
        public_view=True,
        disable_editing=True,
    )


@p2_blueprint.route('/public/folder/<int:folder_id>')
def public_view_folder(folder_id):
    from blueprints.p2.models import Folder, File
    folder = Folder.query.get_or_404(folder_id)
    if (not (getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'id', None) == folder.user_id)) and not getattr(folder, 'is_public', False):
        abort(403)

    # For public folder view: show direct children that are public and direct public notes/boards/files
    public_subs = [c for c in folder.children if getattr(c, 'is_public', False)]
    public_notes = [n for n in folder.notes if getattr(n, 'is_public', False)]
    public_boards = [b for b in folder.boards if getattr(b, 'is_public', False)]
    public_files = [f for f in folder.files if getattr(f, 'is_public', False)]
    
    # Group files by type for sectioned display
    files_by_type = {}
    for file_obj in public_files:
        file_type = file_obj.type
        if file_type not in files_by_type:
            files_by_type[file_type] = []
        files_by_type[file_type].append(file_obj)
    
    return render_template('p2/public_folder.html', folder=folder, subfolders=public_subs, notes=public_notes, boards=public_boards, files=public_files, files_by_type=files_by_type)


@login_manager.user_loader
def load_user(user_id):
    def _load_user():
        return User.query.get(int(user_id))
    
    try:
        return db_retry(_load_user)
    except Exception as e:
        # Log the database connection error
        print(f"Database connection error in load_user after retries: {e}")
        # Return None to force re-authentication
        return None


@p2_blueprint.route('/login', methods=['GET', 'POST'])
def login():
    # Handle clearing remembered username
    if request.args.get('clear_username'):
        session.pop('last_username', None)
        return redirect(url_for('p2_bp.login'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember_me = 'remember' in request.form  # Check if remember checkbox is checked
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember_me)
            session['current_user_id'] = username
            session['last_username'] = username  # Store for next login

            # Get the 'next' parameter to redirect to originally requested page
            next_page = request.args.get('next')
            
            # Validate next_page to prevent open redirect vulnerability
            # Only allow relative URLs (no scheme and no netloc)
            if next_page:
                url_parts = urlparse(next_page)
                # Accept only if it's a relative URL (no scheme/netloc) or same-host
                if not url_parts.netloc and not url_parts.scheme:
                    return redirect(next_page)
            
            # Check user type and redirect accordingly
            if user.is_admin:
                return redirect(url_for('auth.admin_central'))
            else:
                return redirect(url_for('p2_bp.dashboard'))
        flash('Invalid credentials.')
    
    # Get last username from session for pre-filling
    last_username = session.get('last_username', '')
    return render_template('p2/login.html', last_username=last_username)

@p2_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form.get('email', '').strip()  # Optional email
        password = request.form['password']
        answer = request.form.get('security_answer', '').strip()

        # Validation - only username and password are required
        if not username:
            flash('Username is required.')
            return render_template('p2/register.html')
        
        if not password:
            flash('Password is required.')
            return render_template('p2/register.html')

        # Check only for username uniqueness (users can have same email or no email)
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            print('Username already exists.')
        else:
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                security_answer=answer
            )
            db.session.add(new_user)
            db.session.flush()

            root_folder = Folder(name='root', user_id=new_user.id, parent_id=None, is_root=True)
            db.session.add(root_folder)
            db.session.commit()

            flash('Account created! Please log in.')
            print('Account created! Please log in.')
            return redirect(url_for('p2_bp.login'))  # note the blueprint name

    return render_template('p2/register.html')

@p2_blueprint.route('/api/insert_table', methods=['POST'])
@login_required
def insert_table():
    """Convert plain text to HTML table format"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Empty text provided'}), 400
        
        # Split text into lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return jsonify({'error': 'No valid lines found'}), 400
        
        # Detect separator (try common separators)
        separators = ['\t', '|', ',', ';', '  ']  # tab, pipe, comma, semicolon, double space
        best_separator = None
        max_columns = 0
        
        for sep in separators:
            # Test first few lines to determine consistent column count
            column_counts = []
            for line in lines[:min(3, len(lines))]:
                cols = [col.strip() for col in line.split(sep) if col.strip()]
                if len(cols) > 1:  # Only consider if it actually splits
                    column_counts.append(len(cols))
            
            if column_counts and len(set(column_counts)) <= 1:  # Consistent column count
                avg_cols = sum(column_counts) / len(column_counts)
                if avg_cols > max_columns:
                    max_columns = avg_cols
                    best_separator = sep
        
        # Fallback: use whitespace if no good separator found
        if not best_separator:
            best_separator = '  '  # Double space
        
        # Convert to HTML table
        html_parts = ['<table class="table table-bordered table-striped">']
        
        # Process first line as header if it looks like headers
        first_line_cols = [col.strip() for col in lines[0].split(best_separator) if col.strip()]
        
        # Simple heuristic: if first line has no numbers, treat as header
        has_numbers = any(any(c.isdigit() for c in col) for col in first_line_cols)
        use_header = not has_numbers and len(lines) > 1
        
        if use_header:
            html_parts.append('<thead><tr>')
            for col in first_line_cols:
                html_parts.append(f'<th>{col}</th>')
            html_parts.append('</tr></thead>')
            data_lines = lines[1:]
        else:
            data_lines = lines
        
        # Process data rows
        html_parts.append('<tbody>')
        for line in data_lines:
            cols = [col.strip() for col in line.split(best_separator)]
            # Pad columns if needed to match expected count
            while len(cols) < len(first_line_cols):
                cols.append('')
            
            html_parts.append('<tr>')
            for col in cols:
                html_parts.append(f'<td>{col}</td>')
            html_parts.append('</tr>')
        
        html_parts.append('</tbody></table>')
        
        html_table = ''.join(html_parts)
        
        return jsonify({
            'html': html_table,
            'separator_used': best_separator,
            'rows_processed': len(data_lines),
            'has_header': use_header
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to process table: {str(e)}'}), 500

@p2_blueprint.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    """Update user settings like theme preferences"""
    print("update_settings route called")
    print(f"Request method: {request.method}")
    print(f"Form data: {request.form}")
    print(f"Current user: {current_user}")
    
    try:
        # Get the theme from the form data
        theme = request.form.get('theme', 'flatly')
        print(f"Received theme: {theme}")
        
        # Validate theme (ensure it's one of the allowed themes)
        allowed_themes = [
            'flatly', 'darkly', 'slate', 'superhero', 'solar', 
            'cyborg', 'vapor', 'lux', 'minty', 'journal'
        ]
        
        if theme not in allowed_themes:
            print(f"Invalid theme: {theme}")
            return jsonify({'success': False, 'message': 'Invalid theme selected'}), 400
        
        print(f"Current user_prefs: {current_user.user_prefs}")
        
        # Update user preferences
        current_user.user_prefs = current_user.user_prefs or {}
        current_user.user_prefs['theme'] = theme
        
        print(f"Updated user_prefs: {current_user.user_prefs}")
        
        # Flag the attribute as modified for SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(current_user, 'user_prefs')
        
        # Save to database
        db.session.commit()
        print("Database commit successful")
        
        return jsonify({
            'success': True, 
            'message': 'Settings updated successfully',
            'theme': theme,
            'reload_required': False  # Set to True if you want to reload the page to apply theme
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating user settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Failed to save settings'}), 500

@p2_blueprint.route('/debug_user_type')
@login_required
def debug_user_type():
    """Debug route to check current user type"""
    return jsonify({
        'username': current_user.username,
        'user_type': current_user.user_type,
        'user_type_repr': repr(current_user.user_type),
        'user_type_bytes': current_user.user_type.encode('utf-8') if current_user.user_type else None,
        'is_admin': current_user.is_admin,
        'total_data_size': current_user.total_data_size,
        'check_guest': current_user.user_type == 'guest',
        'check_user': current_user.user_type == 'user',
        'check_admin': current_user.user_type == 'admin'
    })

@p2_blueprint.route('/infinite_whiteboard')
@login_required
def infinite_whiteboard():
    """New infinite whiteboard using existing modules"""
    return render_template('p2/infinite_whiteboard.html')

@p2_blueprint.route('/logout')
@login_required
def logout():
    print('Logged out')
    
    # Optionally clear remembered username if requested
    if request.args.get('clear_username'):
        session.pop('last_username', None)
        
    logout_user()
    return redirect(url_for('p2_bp.login'))
