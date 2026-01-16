"""
API endpoints for Chrome Extension integration.

Provides secure endpoints for:
- Generating API tokens for extension authentication
- Fetching user's folder tree
- Creating MioNote files from external content (images, text, URLs)
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import secrets
import base64
import os
import hashlib
import json

from blueprints.p2.models import File, Folder, User
from blueprints.p2.utils import save_data_uri_images_for_user, get_image_hash, get_existing_image_by_hash, convert_to_webp
from extensions import db
from utilities_main import update_user_data_size, check_guest_limit
from values_main import UPLOAD_FOLDER, MAX_IMAGE_SIZE

extension_api_bp = Blueprint('extension_api', __name__, url_prefix='/api/extension')


# ========================
# Helper Functions
# ========================

def normalize_url(url: str) -> str:
    """
    Normalize URL for grouping by stripping query params and fragments.
    
    Examples:
        https://example.com?utm_source=twitter  →  https://example.com
        https://example.com/page#section        →  https://example.com/page
        https://example.com/                    →  https://example.com
    """
    if not url:
        return ''
    
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url.strip())
        # Keep scheme, netloc, path only (drop query, fragment)
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/'),  # Remove trailing slash
            '', '', ''  # No params, query, or fragment
        ))
        return normalized
    except Exception:
        # Fallback: return original if parsing fails
        return url.strip()


def verify_api_token(token):
    """Verify API token and return associated user."""
    if not token:
        return None
    
    # Find user with matching token that hasn't expired
    user = User.query.filter(
        User.api_token == token,
        User.api_token_expires > datetime.utcnow()
    ).first()
    
    return user


def build_folder_tree(folder, include_children=True):
    """Recursively build folder tree structure for extension UI."""
    folder_data = {
        'id': folder.id,
        'name': folder.name,
        'parent_id': folder.parent_id,
        'is_root': folder.is_root,
        'children': []
    }
    
    if include_children:
        child_folders = Folder.query.filter_by(
            user_id=folder.user_id,
            parent_id=folder.id
        ).order_by(Folder.name).all()
        
        folder_data['children'] = [
            build_folder_tree(child, include_children=True)
            for child in child_folders
        ]
    
    return folder_data


def get_or_create_web_clippings_folder(user):
    """
    Get or create the "Web Clippings" folder for extension saves.
    
    The folder is created under the user's root folder if it doesn't exist.
    
    Args:
        user: User object
        
    Returns:
        Folder object for "Web Clippings"
    """
    # Get user's root folder
    root_folder = Folder.query.filter_by(
        user_id=user.id,
        is_root=True
    ).first()
    
    if not root_folder:
        # Create root folder if missing
        root_folder = Folder(
            name='root',
            user_id=user.id,
            parent_id=None,
            is_root=True
        )
        db.session.add(root_folder)
        db.session.flush()
    
    # Look for existing "Web Clippings" folder
    web_clippings = Folder.query.filter_by(
        user_id=user.id,
        name='Web Clippings',
        parent_id=root_folder.id
    ).first()
    
    if not web_clippings:
        # Create "Web Clippings" folder
        web_clippings = Folder(
            name='Web Clippings',
            description='Content saved from Chrome extension',
            user_id=user.id,
            parent_id=root_folder.id,
            is_root=False
        )
        db.session.add(web_clippings)
        db.session.flush()
    
    return web_clippings


def calculate_data_uri_bytes(data_uri: str) -> int:
    """Return decoded byte length for a data URI image string."""
    try:
        _, b64data = data_uri.split(',', 1)
        return len(base64.b64decode(b64data))
    except Exception:
        return 0


def build_extension_description(source_url: str, page_title: str, page_description: str) -> dict:
    """Construct rich multi-description metadata for extension-created notes."""
    fields = {
        'Source': 'Saved from Chrome extension',
        'Page URL': (source_url or '').strip(),
        'Page Title': (page_title or '').strip(),
        'Page Description': (page_description or '').strip(),
    }
    # Drop empty values while preserving keys order semantics (dict preserves insertion)
    return {k: v for k, v in fields.items() if v}


def normalize_description_entries(raw_value):
    """Normalize saved descriptions (string/dict/list) into an ordered list of strings."""
    if not raw_value:
        return []

    parsed = raw_value
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except Exception:
            return [stripped]

    if isinstance(parsed, dict):
        def _sort_key(key):
            try:
                return (0, int(key))
            except Exception:
                return (1, str(key))

        ordered = []
        for _, value in sorted(parsed.items(), key=lambda item: _sort_key(item[0])):
            if value is None:
                continue
            text = str(value).strip()
            if text:
                ordered.append(text)
        return ordered

    if isinstance(parsed, list):
        return [str(v).strip() for v in parsed if str(v).strip()]

    return [str(parsed).strip()]


def build_extension_description_entries(source_url: str, save_source: str = 'extension') -> list:
    """Return the default description entries for Chrome extension saves."""
    if save_source == 'web':
        entries = ['Saved from web']
    else:
        entries = ['Saved from Chrome extension']
    url_text = (source_url or '').strip()
    if url_text:
        entries.append(url_text)
    return entries


def merge_description_entries(existing_entries, extension_entries):
    """Merge extension descriptions ahead of existing ones without duplicates."""
    merged = []
    for entry in extension_entries + existing_entries:
        cleaned = (entry or '').strip()
        if not cleaned:
            continue
        if cleaned not in merged:
            merged.append(cleaned)
    return {str(idx + 1): val for idx, val in enumerate(merged)}


def find_or_create_extension_file(user, folder, normalized_url, page_title):
    """
    Find existing file for this URL or create a new one.
    
    Returns: (file, is_new)
    """
    existing_file = None
    
    if normalized_url:
        # Try to find existing file by normalized source URL
        existing_file = File.query.filter_by(
            owner_id=user.id,
            folder_id=folder.id,
            source_url=normalized_url,
            type='proprietary_note'
        ).first()
    
    if existing_file:
        return existing_file, False
    
    # Create new file
    title = page_title or f"Web Clips - {datetime.now().strftime('%Y-%m-%d')}"
    
    new_file = File(
        owner_id=user.id,
        folder_id=folder.id,
        type='proprietary_note',
        title=title,
        content_html='',  # Will be populated by caller
        source_url=normalized_url or None,
        is_public=False,
        metadata_json={
            'created_by': 'chrome_extension',
            'clip_count': 0
        }
    )
    
    return new_file, True


def append_to_html_content(existing_html: str, new_content: str) -> str:
    """
    Append new content to existing HTML with visual separator.
    
    Format:
        existing content
        <hr style="...">
        new content
    """
    separator = (
        '<hr style="border: none; border-top: 2px dashed #888; '
        'margin: 30px 0; opacity: 0.5;" />'
    )
    
    if not existing_html or existing_html.strip() == '':
        return new_content
    
    return f"{existing_html}\n{separator}\n{new_content}"


# ========================
# Authentication Endpoints
# ========================

@extension_api_bp.route('/generate-token', methods=['POST'])
@login_required
def generate_token():
    """
    Generate or regenerate API token for Chrome extension.
    
    Token expires after 365 days. User can regenerate if needed.
    
    POST /api/extension/generate-token
    Returns: {"token": "xxx", "expires": "2026-01-06 12:00:00"}
    """
    try:
        # Generate secure random token
        token = secrets.token_urlsafe(32)
        
        # Set expiration to 1 year from now
        expiration = datetime.utcnow() + timedelta(days=365)
        
        # Store hashed version in database
        current_user.api_token = token
        current_user.api_token_expires = expiration
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'token': token,
            'expires': expiration.strftime('%Y-%m-%d %H:%M:%S'),
            'user': {
                'username': current_user.username,
                'user_type': current_user.user_type
            }
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500


@extension_api_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """
    Verify if API token is valid.
    
    POST /api/extension/verify-token
    Headers: Authorization: Bearer <token>
    Returns: {"valid": true, "user": {...}}
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'valid': False, 'error': 'Missing or invalid Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user = verify_api_token(token)
    
    if not user:
        return jsonify({'valid': False, 'error': 'Invalid or expired token'}), 401
    
    return jsonify({
        'valid': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'user_type': user.user_type,
            'total_data_size': user.total_data_size
        }
    })


@extension_api_bp.route('/revoke-token', methods=['POST'])
@login_required
def revoke_token():
    """
    Revoke current API token.
    
    POST /api/extension/revoke-token
    """
    try:
        current_user.api_token = None
        current_user.api_token_expires = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Token revoked successfully'})
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ========================
# Folder Management
# ========================

@extension_api_bp.route('/folders', methods=['GET'])
def get_folders():
    """
    Get user's folder tree for dropdown selection.
    
    GET /api/extension/folders
    Headers: Authorization: Bearer <token>
    Returns: {"folders": [...], "default_folder_id": 123}
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user = verify_api_token(token)
    
    if not user:
        return jsonify({'error': 'Invalid or expired token'}), 401
    
    try:
        # Get root folder
        root_folder = Folder.query.filter_by(
            user_id=user.id,
            is_root=True
        ).first()
        
        if not root_folder:
            # Create root folder if missing
            root_folder = Folder(
                name='root',
                user_id=user.id,
                parent_id=None,
                is_root=True
            )
            db.session.add(root_folder)
            db.session.commit()
        
        # Build complete folder tree
        folder_tree = build_folder_tree(root_folder)
        
        # Get user's preferred default folder (or use root)
        default_folder_id = user.user_prefs.get('extension_default_folder', root_folder.id) if user.user_prefs else root_folder.id
        
        return jsonify({
            'success': True,
            'folders': [folder_tree],  # Return as array for consistency
            'default_folder_id': default_folder_id,
            'root_folder_id': root_folder.id
        })
        
    except SQLAlchemyError as e:
        return jsonify({'success': False, 'error': 'Database error'}), 500


@extension_api_bp.route('/set-default-folder', methods=['POST'])
def set_default_folder():
    """
    Set user's default folder for extension saves.
    
    POST /api/extension/set-default-folder
    Headers: Authorization: Bearer <token>
    Body: {"folder_id": 123}
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user = verify_api_token(token)
    
    if not user:
        return jsonify({'error': 'Invalid or expired token'}), 401
    
    data = request.get_json()
    folder_id = data.get('folder_id')
    
    if not folder_id:
        return jsonify({'success': False, 'error': 'Missing folder_id'}), 400
    
    # Verify folder belongs to user
    folder = Folder.query.filter_by(id=folder_id, user_id=user.id).first()
    if not folder:
        return jsonify({'success': False, 'error': 'Invalid folder'}), 400
    
    try:
        # Update user preferences
        if not user.user_prefs:
            user.user_prefs = {}
        
        user.user_prefs['extension_default_folder'] = folder_id
        flag_modified(user, 'user_prefs')
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Default folder set to "{folder.name}"',
            'folder_id': folder_id
        })
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Database error'}), 500


# ========================
# Content Saving Endpoints
# ========================

@extension_api_bp.route('/save-content', methods=['POST'])
def save_content():
    """
    Save content from Chrome extension as MioNote file.
    
    SMART GROUPING: Content from the same URL is appended to existing file instead of creating new files.
    
    POST /api/extension/save-content
    Headers: Authorization: Bearer <token>
    Body: {
        "type": "text|image|url|clean-page",
        "content": "...",
        "title": "Optional title",
        "folder_id": 123,  # Optional, uses default if not specified
        "url": "https://...",  # For context when saving images/text
        "page_title": "Page Title"  # From tab
    }
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing Authorization header'}), 401
    
    token = auth_header.replace('Bearer ', '')
    user = verify_api_token(token)
    
    if not user:
        return jsonify({'error': 'Invalid or expired token'}), 401
    
    data = request.get_json()
    content_type = data.get('type')
    content = data.get('content')
    title = data.get('title', '').strip()
    folder_id = data.get('folder_id')
    source_url = data.get('url', '')
    page_title = data.get('page_title', '')
    page_description = data.get('page_description', '')
    
    if not content_type or not content:
        return jsonify({'success': False, 'error': 'Missing type or content'}), 400
    
    try:
        # Normalize URL for grouping
        normalized_url = normalize_url(source_url) if source_url else None
        
        # Get folder
        folder = get_or_create_web_clippings_folder(user)
        
        # Build the new HTML content
        new_html_content = ''
        bytes_added_from_images = 0
        
        # Add timestamp header for this clip
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_html_content += f'<p style="color: #999; font-size: 0.85em; margin-bottom: 10px;">📌 Saved: {timestamp}</p>'

        if content_type == 'text':
            escaped_content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            formatted_content = escaped_content.replace('\n', '<br>')
            new_html_content += f'<div>{formatted_content}</div>'

        elif content_type == 'image':
            if not content.startswith('data:image'):
                return jsonify({'success': False, 'error': 'Invalid image data'}), 400

            estimated_size = calculate_data_uri_bytes(content)
            if estimated_size <= 0:
                return jsonify({'success': False, 'error': 'Invalid image data'}), 400

            if user.user_type == 'guest' and not check_guest_limit(user, estimated_size):
                return jsonify({'success': False, 'error': 'Storage quota exceeded'}), 403

            normalized_content = f'<img src="{content}" />'
            updated_content, bytes_added_from_images = save_data_uri_images_for_user(normalized_content, user.id)

            img_src = None
            if updated_content:
                try:
                    soup = BeautifulSoup(updated_content, 'html.parser')
                    img_tag = soup.find('img')
                    img_src = img_tag.get('src') if img_tag else None
                except Exception:
                    img_src = None

            if not img_src:
                return jsonify({'success': False, 'error': 'Failed to save image'}), 500

            new_html_content += f'<div><img src="{img_src}" style="max-width: 100%; height: auto;" /></div>'

        elif content_type == 'url':
            new_html_content += f'<h3><a href="{content}" target="_blank">{title or page_title}</a></h3>'
            if page_title and page_title != title:
                new_html_content += f'<p>{page_title}</p>'
            new_html_content += f'<p style="color: #666; font-size: 0.9em;">{content}</p>'

        elif content_type == 'clean-page':
            # Convert markdown-formatted clean page content to HTML
            # First, extract and process images with data URIs
            import re
            
            # Find all markdown images: ![alt](data:image/...)
            image_pattern = r'!\[([^\]]*)\]\((data:image[^)]+)\)'
            images_found = re.findall(image_pattern, content)
            
            # Process images through deduplication system
            for alt_text, data_uri in images_found:
                # Calculate size for quota check
                estimated_size = calculate_data_uri_bytes(data_uri)
                
                if estimated_size > 0:
                    if user.user_type == 'guest' and not check_guest_limit(user, estimated_size):
                        # Skip this image if quota exceeded
                        content = content.replace(f'![{alt_text}]({data_uri})', f'[Image removed: quota exceeded]')
                        continue
                    
                    # Convert data URI to saved image path
                    temp_html = f'<img src="{data_uri}" alt="{alt_text}" />'
                    processed_html, img_bytes = save_data_uri_images_for_user(temp_html, user.id)
                    
                    if processed_html and img_bytes > 0:
                        bytes_added_from_images += img_bytes
                        
                        # Extract new image path from processed HTML
                        img_match = re.search(r'src="([^"]+)"', processed_html)
                        if img_match:
                            new_img_path = img_match.group(1)
                            # Replace data URI with saved image path in markdown
                            content = content.replace(data_uri, new_img_path)
            
            # Now convert markdown to HTML
            try:
                import markdown
                # Convert markdown to HTML with extensions for better formatting
                html_content = markdown.markdown(
                    content,
                    extensions=['fenced_code', 'tables', 'nl2br']
                )
                new_html_content += f'<div class="clean-page-content" style="max-width: 800px;">{html_content}</div>'
            except ImportError:
                # Fallback: basic markdown-like formatting without markdown library
                escaped_content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                # Handle markdown images manually
                escaped_content = re.sub(
                    r'!\[([^\]]*)\]\(([^)]+)\)',
                    r'<img src="\2" alt="\1" style="max-width: 100%; height: auto;" />',
                    escaped_content
                )
                # Convert markdown headings to HTML
                lines = escaped_content.split('\n')
                formatted_lines = []
                for line in lines:
                    if line.startswith('# '):
                        formatted_lines.append(f'<h1>{line[2:]}</h1>')
                    elif line.startswith('## '):
                        formatted_lines.append(f'<h2>{line[3:]}</h2>')
                    elif line.startswith('### '):
                        formatted_lines.append(f'<h3>{line[4:]}</h3>')
                    elif line.startswith('> '):
                        formatted_lines.append(f'<blockquote>{line[2:]}</blockquote>')
                    elif line.strip() == '':
                        formatted_lines.append('<br>')
                    else:
                        formatted_lines.append(f'<p>{line}</p>')
                new_html_content += '<div class="clean-page-content" style="max-width: 800px;">' + '\n'.join(formatted_lines) + '</div>'

        else:
            return jsonify({'success': False, 'error': f'Unsupported content type: {content_type}'}), 400

        # Find or create file for this URL
        target_file, is_new_file = find_or_create_extension_file(user, folder, normalized_url, page_title)
        
        # Calculate old size for delta tracking
        old_content_size = 0
        if not is_new_file and target_file.content_html:
            old_content_size = len(target_file.content_html.encode('utf-8'))
        
        # Append or set content
        if is_new_file:
            target_file.content_html = new_html_content
        else:
            target_file.content_html = append_to_html_content(target_file.content_html, new_html_content)
            target_file.last_modified = datetime.utcnow()
            
            # Update clip count
            if not target_file.metadata_json:
                target_file.metadata_json = {}
            clip_count = target_file.metadata_json.get('clip_count', 0) + 1
            target_file.metadata_json['clip_count'] = clip_count
            target_file.metadata_json['last_clip_at'] = datetime.utcnow().isoformat()

        if not target_file.metadata_json:
            target_file.metadata_json = {}

        existing_entries = normalize_description_entries(target_file.metadata_json.get('description'))
        extension_entries = build_extension_description_entries(normalized_url)
        target_file.metadata_json['description'] = merge_description_entries(existing_entries, extension_entries)
        
        # CRITICAL: Flag modified for LONGTEXT column (content_html)
        flag_modified(target_file, 'content_html')
        flag_modified(target_file, 'metadata_json')
        
        # Calculate new size for delta
        new_content_size = len(target_file.content_html.encode('utf-8'))
        content_size_delta = new_content_size - old_content_size
        
        # Add to session
        if is_new_file:
            db.session.add(target_file)
        
        folder.last_modified = datetime.utcnow()
        
        # Commit database changes
        db.session.commit()
        
        # Update quota with delta (content + images)
        total_delta = content_size_delta + bytes_added_from_images
        if total_delta > 0:
            # Final quota check for non-image content
            if user.user_type == 'guest' and content_type != 'image':
                if not check_guest_limit(user, total_delta):
                    db.session.rollback()
                    return jsonify({'success': False, 'error': 'Storage quota exceeded'}), 403
            
            update_user_data_size(user, total_delta)

        action_verb = 'created' if is_new_file else 'updated'
        clip_info = f" (clip #{target_file.metadata_json.get('clip_count', 1)})" if not is_new_file else ''
        
        return jsonify({
            'success': True,
            'message': f'Content {action_verb} in "{folder.name}"{clip_info}',
            'file': {
                'id': target_file.id,
                'title': target_file.title,
                'type': target_file.type,
                'folder_name': folder.name,
                'is_new': is_new_file,
                'clip_count': target_file.metadata_json.get('clip_count', 1),
                'created_at': target_file.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'last_modified': target_file.last_modified.strftime('%Y-%m-%d %H:%M:%S')
            }
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Extension API save error: {str(e)}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Extension API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

