from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, Response
from flask_login import login_required, current_user

import requests
import uuid
from PIL import Image
import os, re, requests, json, zipfile, tempfile, shutil, base64, io
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table as RLTable, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from bs4 import BeautifulSoup
import markdown


from .models import File, User, Folder, GraphWorkspace, GraphNode, GraphEdge, GraphNodeAttachment
from extensions import db, login_manager
#from utils import build_folder_breadcrumb, now
from .utils import get_existing_image_by_hash, get_image_hash, allowed_file, convert_to_webp, collect_images_from_content, copy_images_to_user
from utilities_main import  *
from values_main import  *
from . import notes_bp



## ---------------------------------------------------------------------------------------------------
# noteleeper related
# product p2

# view option in note menu # deprecate for raw text with unique link
@notes_bp.route('/note/<int:note_id>')
@login_required
def view_note(note_id):
    return render_template('p2/view_note.html', note="", md_content="")



@notes_bp.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = File.query.filter_by(id=note_id, owner_id=current_user.id, type='proprietary_note').first()
    if note:
        size_to_subtract = calculate_content_size(note.content_html)
        user_id = current_user.id
        db.session.delete(note)
        db.session.commit()
        # Session asset cleanup removed - handled by dedicated cleanup function
        update_user_data_size(current_user, -size_to_subtract)
        
        # Clean up orphaned images
        from .utils import cleanup_orphaned_images_for_user
        try:
            deleted_count, freed_bytes = cleanup_orphaned_images_for_user(user_id)
            if deleted_count > 0:
                print(f"[DELETE NOTE] Cleaned up {deleted_count} orphaned images, freed {freed_bytes} bytes")
        except Exception as e:
            print(f"[DELETE NOTE] Image cleanup failed: {e}")
        
        flash("Note deleted successfully.")
    else:
        flash("Note not found or unauthorized.")
    target_folder_id = session.get('current_folder_id')
    print(f"[DELETE NOTE] Target folder id: {target_folder_id}")
    return redirect(url_for("folders.view_folder", folder_id=target_folder_id))


@notes_bp.route('/new_note', methods=['GET', 'POST'])
@login_required
def new_note():
    # Allow explicit folder targeting (e.g., Graph Workspace).
    folder_override_id = (
        request.args.get('folder_id', type=int)
        or request.form.get('folder_id', type=int)
    )

    if folder_override_id:
        override_folder = Folder.query.filter_by(id=folder_override_id, user_id=current_user.id).first()
        if override_folder:
            session['current_folder_id'] = folder_override_id

    current_folder_id = session.get('current_folder_id')

    if not current_folder_id:
        current_folder = Folder.query.filter_by(user_id=current_user.id, parent_id=None).first()
        current_folder_id = current_folder.id

    if request.method == 'POST':
        print(f"\n========== DEBUG: NEW NOTE POST ==========")
        # Accept missing form keys gracefully
        title = (request.form.get('title') or '').strip()
        description = request.form.get('description', '')
        content = request.form.get('content', '')
        
        print(f"DEBUG: Received form data:")
        print(f"  - Title: {title[:50]}..." if len(title) > 50 else f"  - Title: {title}")
        print(f"  - Description length: {len(description)}")
        print(f"  - Content length: {len(content)}")

        # Process images in content
        print(f"DEBUG: Processing images in content...")
        content = extract_and_save_images(content, current_user.id)
        print(f"DEBUG: After image processing, content length: {len(content)}")

        # If no title provided, generate a default title
        if not title:
            title = "Default Title " + now
            flash('Title is required! Saved with the title: ' + title)
            print(f"DEBUG: No title provided, using default: {title}")

        # Create the note regardless of whether the title is present or not
        content_size = calculate_content_size(content)
        print(f"DEBUG: Content size: {content_size}")
        
        if not check_guest_limit(current_user, content_size):
            print(f"DEBUG: Guest limit check FAILED for user {current_user.id}")
            return redirect(url_for('folders.view_folder', folder_id=current_folder_id))

        print(f"DEBUG: Creating new File object...")
        print(f"  - owner_id: {current_user.id}")
        print(f"  - folder_id: {current_folder_id}")
        print(f"  - type: 'note'")
        print(f"  - title: {title}")
        metadata_preview = {'description': description} if description else {}
        print(f"  - metadata_json: {metadata_preview}")
        
        note = File(
            owner_id=current_user.id,
            folder_id=current_folder_id,
            type='proprietary_note',
            title=title,
            content_html=content,
            metadata_json={'description': description} if description else {}
        )
        print(f"DEBUG: Adding note to session...")
        db.session.add(note)
        print(f"DEBUG: Committing to database...")
        db.session.commit()
        print(f"DEBUG: Note created with ID: {note.id}")
        
        # Session asset cleanup removed - handled by dedicated cleanup function
        update_user_data_size(current_user, content_size)
        
        # Add notification for note creation
        from blueprints.p2.utils import add_notification
        def format_file_size(size_bytes):
            if size_bytes < 1024:
                return f"{size_bytes}B"
            elif size_bytes < 1024 * 1024:
                return f"{(size_bytes / 1024):.1f}KB"
            else:
                return f"{(size_bytes / (1024 * 1024)):.1f}MB"
        size_str = format_file_size(content_size)
        notif_msg = f"Created note '{title}' ({size_str})"
        add_notification(current_user.id, notif_msg, 'save')
        
        flash('Note created successfully!')
        print(f"DEBUG: Redirecting to edit_note for note_id={note.id}")
        return redirect(url_for('notes.edit_note', note_id=note.id))

    elif request.method == 'GET':
        folder = Folder.query.get(current_folder_id)
        breadcrumb = build_folder_breadcrumb(folder) if folder else []
        return render_template('p2/file_edit_proprietary_note.html', file=None, folder_breadcrumb=breadcrumb)

@notes_bp.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = File.query.get_or_404(note_id)
    if note.owner_id != current_user.id:
        flash("Access denied.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        print(f"\n========== DEBUG: EDIT NOTE {note_id} POST ==========")
        title = request.form['title']
        description = request.form.get('description', '')
        content = request.form['content']
        
        print(f"DEBUG: Received form data:")
        print(f"  - Title: {title[:50]}..." if len(title) > 50 else f"  - Title: {title}")
        print(f"  - Description length: {len(description)}")
        print(f"  - Content length: {len(content)}")

        if not title:
            flash('Title is required!')
            return redirect(url_for('notes.edit_note', note_id=note_id))

        # Process images in content
        print(f"DEBUG: Processing images in content...")
        content = extract_and_save_images(content, current_user.id)
        print(f"DEBUG: After image processing, content length: {len(content)}")

        # Debug: Validate description JSON (if present)
        try:
            if description:
                import json as _json
                _json.loads(description)
                print(f"DEBUG: Edit note {note_id} - description is valid JSON (len={len(description)})")
        except Exception as e:
            preview = (description or '')[:200]
            print(f"DEBUG: Edit note {note_id} - description is NOT valid JSON (preview={preview!r})")

        old_size = calculate_content_size(note.content_html)
        new_size = calculate_content_size(content)
        delta = new_size - old_size
        print(f"DEBUG: Content size - old: {old_size}, new: {new_size}, delta: {delta}")
        
        if not check_guest_limit(current_user, delta):
            print(f"DEBUG: Guest limit check FAILED for user {current_user.id}")
            return redirect(url_for('folders.view_folder', folder_id=note.folder_id))
        
        print(f"DEBUG: Updating note fields...")
        print(f"  - Old title: {note.title}")
        print(f"  - New title: {title}")
        print(f"  - Old metadata_json: {note.metadata_json}")
        
        note.title = title
        
        # Update description in metadata_json
        if not note.metadata_json:
            note.metadata_json = {}
        note.metadata_json['description'] = description
        
        print(f"  - New metadata_json: {note.metadata_json}")
        print(f"DEBUG: Calling flag_modified for metadata_json...")
        flag_modified(note, 'metadata_json')
        
        note.content_html = content
        note.last_modified = datetime.utcnow()
        
        print(f"DEBUG: Committing to database...")
        db.session.commit()
        print(f"DEBUG: Commit successful!")
        
        # Add notification for successful save
        from blueprints.p2.utils import add_notification
        size_str = f"{new_size / 1024:.1f} KB" if new_size < 1024 * 1024 else f"{new_size / (1024 * 1024):.1f} MB"
        notification_msg = f"Saved note: {note.title} ({size_str})"
        add_notification(current_user.id, notification_msg, 'save')
        
        # Session asset cleanup removed - handled by dedicated cleanup function
        update_user_data_size(current_user, delta)
        
        # No flash message - notification shown in telemetry panel
        # Redirect to folder view instead of staying on edit page
        return redirect(url_for('folders.view_folder', folder_id=note.folder_id))

    breadcrumb = build_folder_breadcrumb(note.folder) if note.folder else []
    return render_template('p2/file_edit_proprietary_note.html', file=note, folder_breadcrumb=breadcrumb)

def extract_and_save_images(content, user_id):
    """
    Extract external images from HTML content and convert to WebP with deduplication, replace with file paths
    """
    

    # Pattern to match external image URLs (http/https)
    external_pattern = r'<img[^>]*src="(https?://[^"]+)"[^>]*>'

    def replace_external_image(match):
        full_match = match.group(0)
        image_url = match.group(1)

        try:
            # Download the image
            response = requests.get(image_url, timeout=10, stream=True)
            response.raise_for_status()

            # Check file size
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > MAX_IMAGE_SIZE:
                return full_match  # Keep original if too large

            # Read image data
            image_data = response.content
            if len(image_data) > MAX_IMAGE_SIZE:
                return full_match  # Keep original if too large

            # Save temporary file to calculate hash
            temp_original = f"temp_original_{uuid.uuid4().hex}"
            temp_original_path = os.path.join(UPLOAD_FOLDER, temp_original)

            with open(temp_original_path, 'wb') as f:
                f.write(image_data)

            # Calculate hash
            image_hash = get_image_hash(temp_original_path)

            # Check if this image already exists for this user
            existing_url = get_existing_image_by_hash(user_id, image_hash)
            if existing_url:
                # Clean up temp file and use existing image
                os.remove(temp_original_path)
                print(f"DEBUG: Using existing external image for hash {image_hash}: {existing_url}")
                return re.sub(r'src="[^"]*"', f'src="{existing_url}"', full_match)

            # Generate hash-based filename
            filename = f"{user_id}_{image_hash}.webp"
            final_filepath = os.path.join(UPLOAD_FOLDER, filename)

            # Convert to WebP
            convert_to_webp(temp_original_path, final_filepath)

            # Clean up temp file
            os.remove(temp_original_path)

            # Get final file size and update user data size
            if os.path.exists(final_filepath):
                final_file_size = os.path.getsize(final_filepath)

                if not check_guest_limit(current_user, final_file_size):
                    # Remove the file if it would exceed the limit
                    os.remove(final_filepath)
                    return full_match  # Keep original

                update_user_data_size(current_user, final_file_size)

                # Return updated img tag
                relative_path = f"/static/uploads/images/{filename}"
                print(f"DEBUG: Created new external image with hash {image_hash}: {relative_path}")
                return re.sub(r'src="[^"]*"', f'src="{relative_path}"', full_match)

        except Exception as e:
            print(f"Error processing external image {image_url}: {e}")
            return full_match  # Keep original on error

    # Replace all external images
    updated_content = re.sub(external_pattern, replace_external_image, content)

    # Now also handle inline data:image/...;base64,... images and save them to UPLOAD_FOLDER
    from bs4 import BeautifulSoup
    import base64, mimetypes, uuid, shutil
    soup = BeautifulSoup(updated_content, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if isinstance(src, str) and src.startswith('data:image/'):
            try:
                header, b64 = src.split(',', 1)
                mime = header.split(';')[0].split(':')[1]
                ext = mimetypes.guess_extension(mime) or '.png'
                tmp = f"tmp_{uuid.uuid4().hex}{ext}"
                tmp_path = os.path.join(UPLOAD_FOLDER, tmp)
                with open(tmp_path, 'wb') as f:
                    f.write(base64.b64decode(b64))
                image_hash = get_image_hash(tmp_path)
                existing_url = get_existing_image_by_hash(user_id, image_hash)
                if existing_url:
                    print(f"DEBUG: extract_and_save_images - inline already exists for user {user_id}: {existing_url}")
                    img['src'] = existing_url
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue
                dest_filename = f"{user_id}_{image_hash}.webp"
                dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)
                try:
                    converted = convert_to_webp(tmp_path, dest_path)
                    if os.path.exists(converted):
                        img['src'] = f"/static/uploads/images/{os.path.basename(converted)}"
                        print(f"DEBUG: extract_and_save_images - inline converted and saved for user {user_id} -> {converted}")
                        # update user data size
                        try:
                            update_user_data_size(current_user, os.path.getsize(converted))
                        except Exception:
                            pass
                except Exception:
                    try:
                        shutil.copy2(tmp_path, dest_path)
                        if os.path.exists(dest_path):
                            img['src'] = f"/static/uploads/images/{os.path.basename(dest_path)}"
                            try:
                                update_user_data_size(current_user, os.path.getsize(dest_path))
                            except Exception:
                                pass
                    except Exception as e:
                        print(f"Error processing inline data URI: {e}")
                        # keep the original data URI if processing failed
                    continue
                finally:
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
            finally:
                pass



    updated_content = str(soup)
    return updated_content





# ========================================================================================
# export import
# core

import os
import io
import zipfile
import json
import re
import base64
from datetime import datetime
from flask import current_app
from bs4 import BeautifulSoup
from werkzeug.utils import secure_filename


COMBINED_BLOCK_TYPES = {"note", "board", "board-iframe"}


def parse_combined_blocks(raw_content):
    if not raw_content:
        return []

    try:
        data = json.loads(raw_content)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, list):
        return [block for block in data if isinstance(block, dict)]

    return []


def is_combined_document(raw_content):
    blocks = parse_combined_blocks(raw_content)
    return any(block.get("type") in COMBINED_BLOCK_TYPES for block in blocks)


# util function collect_images_from_content has moved to utils.py. Use imported function.


def export_folder_to_jsonl(folder, image_set, lines, path_prefix=""):
    """
    Convert a folder and all its contents to JSONL format (one JSON object per line).
    Recursively includes subfolders and preserves directory structure.
    
    Each line in the JSONL output represents either:
    - A folder record
    - A file record (any type: note, whiteboard, markdown, todo, diagram, etc.)
    
    Args:
        folder: Folder object to export
        image_set: Set to collect image filenames
        lines: List to append JSONL lines to
        path_prefix: String representing the current path in the hierarchy
    """
    # Build current path
    current_path = f"{path_prefix}/{folder.name}" if path_prefix else folder.name
    
    # Export folder metadata as JSONL line
    folder_record = {
        "record_type": "folder",
        "id": folder.id,
        "name": folder.name,
        "path": current_path,
        "parent_id": folder.parent_id,
        "description": folder.description,
        "is_public": folder.is_public if hasattr(folder, 'is_public') else False,
        "is_root": folder.is_root if hasattr(folder, 'is_root') else False,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "last_modified": folder.last_modified.isoformat() if hasattr(folder, 'last_modified') and folder.last_modified else None
    }
    lines.append(json.dumps(folder_record, ensure_ascii=False))
    
    # Export all files in this folder (supports all file types)
    for file in folder.files:
        file_record = {
            "record_type": "file",
            "id": file.id,
            "type": file.type,
            "title": file.title,
            "folder_path": current_path,
            "folder_id": file.folder_id,
            "is_public": file.is_public if hasattr(file, 'is_public') else False,
            "is_pinned": file.is_pinned if hasattr(file, 'is_pinned') else False,
            "created_at": file.created_at.isoformat() if file.created_at else None,
            "last_modified": file.last_modified.isoformat() if hasattr(file, 'last_modified') and file.last_modified else None,
            "metadata_json": file.metadata_json,
        }
        
        # Add appropriate content based on file type
        # Text-based content types (markdown, code, notes)
        if file.type in ('markdown', 'code', 'proprietary_note', 'note'):
            if file.content_text:
                file_record["content_text"] = file.content_text
                # Collect images from text content (markdown images)
                collect_images_from_content(file.content_text, image_set)
            if file.content_html:
                file_record["content_html"] = file.content_html
                # Collect images from HTML content
                collect_images_from_content(file.content_html, image_set)
        
        # JSON-based content types (whiteboards, diagrams, todos, tables, blocks, graphs)
        elif file.type in ('proprietary_whiteboard', 'whiteboard', 'diagram', 'todo', 'table', 
                          'blocks', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph'):
            if file.content_json:
                file_record["content_json"] = file.content_json
                # Collect images from JSON content (whiteboard, diagram, graph)
                try:
                    json_str = json.dumps(file.content_json) if isinstance(file.content_json, dict) else str(file.content_json)
                    collect_images_from_content(json_str, image_set)
                except Exception as e:
                    print(f"[EXPORT] Warning: Could not scan JSON content for images in {file.type}: {e}")
        
        # Binary content types (PDFs, uploaded files)
        elif file.type in ('pdf',):
            if file.content_blob:
                # Encode binary content as base64 for JSONL
                file_record["content_blob_base64"] = base64.b64encode(file.content_blob).decode('utf-8')
        
        # Unknown file type - export whatever content is available
        else:
            print(f"[EXPORT] Warning: Unknown file type '{file.type}' for file '{file.title}'")
            if file.content_text:
                file_record["content_text"] = file.content_text
            if file.content_html:
                file_record["content_html"] = file.content_html
            if file.content_json:
                file_record["content_json"] = file.content_json
            if file.content_blob:
                file_record["content_blob_base64"] = base64.b64encode(file.content_blob).decode('utf-8')
        
        lines.append(json.dumps(file_record, ensure_ascii=False))
        
        # Export graph workspace metadata if this is a proprietary_graph file
        if file.type == 'proprietary_graph' and hasattr(file, 'graph_workspace') and file.graph_workspace:
            workspace = file.graph_workspace
            
            # Export workspace metadata
            workspace_record = {
                "record_type": "graph_workspace",
                "file_id": file.id,
                "settings_json": workspace.settings_json,
                "metadata_json": workspace.metadata_json,
                "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
                "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
            }
            lines.append(json.dumps(workspace_record, ensure_ascii=False))
            
            # Export all nodes
            for node in workspace.nodes:
                node_record = {
                    "record_type": "graph_node",
                    "graph_file_id": file.id,
                    "node_id": node.id,
                    "title": node.title,
                    "summary": node.summary,
                    "position_json": node.position_json,
                    "size_json": node.size_json,
                    "style_json": node.style_json,
                    "metadata_json": node.metadata_json,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                    "updated_at": node.updated_at.isoformat() if node.updated_at else None
                }
                lines.append(json.dumps(node_record, ensure_ascii=False))
            
            # Export all edges
            for edge in workspace.edges:
                edge_record = {
                    "record_type": "graph_edge",
                    "graph_file_id": file.id,
                    "edge_id": edge.id,
                    "source_node_id": edge.source_node_id,
                    "target_node_id": edge.target_node_id,
                    "label": edge.label,
                    "edge_type": edge.edge_type,
                    "metadata_json": edge.metadata_json,
                    "created_at": edge.created_at.isoformat() if edge.created_at else None,
                    "updated_at": edge.updated_at.isoformat() if edge.updated_at else None
                }
                lines.append(json.dumps(edge_record, ensure_ascii=False))
            
            # Export all node attachments
            for node in workspace.nodes:
                for attachment in node.attachments:
                    attachment_record = {
                        "record_type": "graph_node_attachment",
                        "graph_file_id": file.id,
                        "node_id": node.id,
                        "attachment_id": attachment.id,
                        "attachment_type": attachment.attachment_type,
                        "file_id": attachment.file_id,
                        "folder_id": attachment.folder_id,
                        "url": attachment.url,
                        "metadata_json": attachment.metadata_json,
                        "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
                        "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None
                    }
                    lines.append(json.dumps(attachment_record, ensure_ascii=False))
    
    # Recursively export subfolders
    for subfolder in folder.children:
        export_folder_to_jsonl(subfolder, image_set, lines, current_path)



@notes_bp.route('/export_notes', methods=['GET'])
@login_required
def export_notes():
    """
    Export folder hierarchy with individual JSONL files per content file.
    
    NEW Architecture (v5.0):
    - Creates a ZIP containing:
      - manifest.json: Export metadata and summary
      - folders.jsonl: Folder hierarchy (one folder per line)
      - files/: Directory containing individual JSONL files (one per content file)
        - {sanitized_filename}.jsonl: File metadata + content + graph data
      - images/: All referenced WebP images (no re-compression)
    
    Benefits:
    - Each content file is independent and portable
    - Easy to inspect individual files
    - Simpler import logic (one file at a time)
    - Better for version control and diffs
    """
    from blueprints.p2.utils import add_notification
    
    current_folder_id = session.get("current_folder_id")
    user_id = current_user.id
    username = current_user.username

    print("[EXPORT] current_folder_id: ", current_folder_id)
    print("[EXPORT] current_user_id: ", user_id)
    print("[EXPORT] username: ", username)

    if current_folder_id:
        start_folder = Folder.query.filter_by(
            id=current_folder_id,
            user_id=user_id
        ).first()
    else:
        # fallback to root if nothing stored
        start_folder = Folder.query.filter_by(user_id=user_id, parent_id=None).first()

    if not start_folder:
        print("[EXPORT] Folder not found")
        add_notification(current_user.id, "Export failed: Folder not found", "error")
        return redirect(url_for("folders.view_folder",
                                folder_id=session.get("current_folder_id", 0)))

    try:
        # Collect all folders, files, and images
        image_set = set()
        folder_records = []
        file_records = []  # List of (filename, jsonl_content) tuples
        
        def collect_folder_data(folder, path_prefix=""):
            current_path = f"{path_prefix}/{folder.name}" if path_prefix else folder.name
            
            # Collect folder metadata
            folder_records.append({
                "record_type": "folder",
                "id": folder.id,
                "name": folder.name,
                "path": current_path,
                "parent_id": folder.parent_id,
                "description": folder.description,
                "is_public": folder.is_public if hasattr(folder, 'is_public') else False,
                "is_root": folder.is_root if hasattr(folder, 'is_root') else False,
                "created_at": folder.created_at.isoformat() if folder.created_at else None,
                "last_modified": folder.last_modified.isoformat() if hasattr(folder, 'last_modified') and folder.last_modified else None
            })
            
            # Collect each file as individual JSONL
            for file in folder.files:
                file_data = {
                    "record_type": "file",
                    "id": file.id,
                    "type": file.type,
                    "title": file.title,
                    "folder_path": current_path,
                    "folder_id": file.folder_id,
                    "is_public": file.is_public if hasattr(file, 'is_public') else False,
                    "metadata_json": file.metadata_json,
                    "created_at": file.created_at.isoformat() if file.created_at else None,
                    "last_modified": file.last_modified.isoformat() if hasattr(file, 'last_modified') and file.last_modified else None,
                }
                
                # Add content based on file type
                if file.type in ('markdown', 'code', 'proprietary_note', 'note'):
                    if file.content_text:
                        file_data["content_text"] = file.content_text
                        collect_images_from_content(file.content_text, image_set)
                    if file.content_html:
                        file_data["content_html"] = file.content_html
                        collect_images_from_content(file.content_html, image_set)
                
                elif file.type in ('proprietary_whiteboard', 'whiteboard', 'diagram', 'todo', 'table', 
                                  'blocks', 'proprietary_blocks', 'proprietary_infinite_whiteboard', 'proprietary_graph'):
                    if file.content_json:
                        file_data["content_json"] = file.content_json
                        try:
                            json_str = json.dumps(file.content_json) if isinstance(file.content_json, dict) else str(file.content_json)
                            collect_images_from_content(json_str, image_set)
                        except Exception as e:
                            print(f"[EXPORT] Warning: Could not scan JSON content for images in {file.type}: {e}")
                
                elif file.type in ('pdf',):
                    if file.content_blob:
                        file_data["content_blob_base64"] = base64.b64encode(file.content_blob).decode('utf-8')
                
                else:
                    print(f"[EXPORT] Warning: Unknown file type '{file.type}' for file '{file.title}'")
                    if file.content_text:
                        file_data["content_text"] = file.content_text
                    if file.content_html:
                        file_data["content_html"] = file.content_html
                    if file.content_json:
                        file_data["content_json"] = file.content_json
                    if file.content_blob:
                        file_data["content_blob_base64"] = base64.b64encode(file.content_blob).decode('utf-8')
                
                # Add graph workspace data if applicable
                if file.type == 'proprietary_graph' and hasattr(file, 'graph_workspace') and file.graph_workspace:
                    workspace = file.graph_workspace
                    file_data["graph_workspace"] = {
                        "settings_json": workspace.settings_json,
                        "metadata_json": workspace.metadata_json,
                        "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
                        "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
                        "nodes": [],
                        "edges": [],
                        "attachments": []
                    }
                    
                    # Add nodes
                    for node in workspace.nodes:
                        node_data = {
                            "node_id": node.id,
                            "title": node.title,
                            "summary": node.summary,
                            "position_json": node.position_json,
                            "size_json": node.size_json,
                            "style_json": node.style_json,
                            "metadata_json": node.metadata_json,
                            "created_at": node.created_at.isoformat() if node.created_at else None,
                            "updated_at": node.updated_at.isoformat() if node.updated_at else None
                        }
                        file_data["graph_workspace"]["nodes"].append(node_data)
                    
                    # Add edges
                    for edge in workspace.edges:
                        edge_data = {
                            "edge_id": edge.id,
                            "source_node_id": edge.source_node_id,
                            "target_node_id": edge.target_node_id,
                            "label": edge.label,
                            "edge_type": edge.edge_type,
                            "metadata_json": edge.metadata_json,
                            "created_at": edge.created_at.isoformat() if edge.created_at else None,
                            "updated_at": edge.updated_at.isoformat() if edge.updated_at else None
                        }
                        file_data["graph_workspace"]["edges"].append(edge_data)
                    
                    # Add attachments
                    for node in workspace.nodes:
                        for attachment in node.attachments:
                            attachment_data = {
                                "node_id": node.id,
                                "attachment_id": attachment.id,
                                "attachment_type": attachment.attachment_type,
                                "file_id": attachment.file_id,
                                "folder_id": attachment.folder_id,
                                "url": attachment.url,
                                "metadata_json": attachment.metadata_json,
                                "created_at": attachment.created_at.isoformat() if attachment.created_at else None,
                                "updated_at": attachment.updated_at.isoformat() if attachment.updated_at else None
                            }
                            file_data["graph_workspace"]["attachments"].append(attachment_data)
                
                # Generate safe filename for JSONL
                safe_filename = sanitize_filename(file.title) or f"file_{file.id}"
                jsonl_filename = f"{safe_filename}.jsonl"
                jsonl_content = json.dumps(file_data, ensure_ascii=False, indent=2)
                file_records.append((jsonl_filename, jsonl_content))
            
            # Recursively process subfolders
            for subfolder in folder.children:
                collect_folder_data(subfolder, current_path)
        
        # Start collection
        collect_folder_data(start_folder)
        
        # Count files by type
        file_type_counts = {}
        for _, jsonl_content in file_records:
            file_data = json.loads(jsonl_content)
            file_type = file_data.get("type", "unknown")
            file_type_counts[file_type] = file_type_counts.get(file_type, 0) + 1
        
        # Create manifest
        manifest = {
            "export_version": "5.0",
            "export_format": "individual_jsonl",
            "export_date": datetime.now().isoformat(),
            "exporter_username": username,
            "exporter_user_id": user_id,
            "start_folder_name": start_folder.name,
            "start_folder_id": start_folder.id,
            "summary": {
                "total_folders": len(folder_records),
                "total_files": len(file_records),
                "files_by_type": file_type_counts,
                "total_images": len(image_set)
            },
            "notes": "Import this backup using the 'Import ZIP Backup' feature in MioWord"
        }
        
        # Create ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Write manifest.json
            zipf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            
            # Write folders.jsonl
            folders_jsonl = "\n".join(json.dumps(f, ensure_ascii=False) for f in folder_records)
            zipf.writestr("folders.jsonl", folders_jsonl)
            
            # Write individual file JSONL files
            for filename, content in file_records:
                zipf.writestr(f"files/{filename}", content)
            
            # Copy images to ZIP
            images_added = 0
            for image_filename in image_set:
                possible_paths = [
                    os.path.normpath(os.path.join('static', 'uploads', 'images', image_filename)),
                    os.path.normpath(os.path.join(UPLOAD_FOLDER, image_filename))
                ]
                
                for image_path in possible_paths:
                    if os.path.exists(image_path) and os.path.isfile(image_path):
                        zip_image_path = f"images/{image_filename}"
                        zipf.write(image_path, zip_image_path)
                        images_added += 1
                        print(f"[EXPORT] Added image: {image_filename}")
                        break
                else:
                    print(f"[EXPORT] Warning: Image not found: {image_filename}")
            
            print(f"[EXPORT] Created {len(file_records)} individual JSONL files")
            print(f"[EXPORT] Added {images_added} images to ZIP")
        
        zip_buffer.seek(0)
        zip_filename = f"{username}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        # Add notification instead of flash
        add_notification(
            current_user.id, 
            f"Exported {len(folder_records)} folders, {len(file_records)} files, {len(image_set)} images", 
            "info"
        )
        
        return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=zip_filename)
    
    except Exception as e:
        print(f"[EXPORT] Error: {e}")
        import traceback
        traceback.print_exc()
        add_notification(current_user.id, f"Export failed: {str(e)}", "error")
        return redirect(url_for("folders.view_folder", folder_id=current_folder_id))








def sanitize_filename(filename):
    """
    Clean filename for safe file system usage
    """
    if not filename:
        return "Untitled"

    # Replace problematic characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]

    return sanitized or "Untitled"





from docx.text.run import Run as _DocxRun

def _get_paragraph_indent_px(para, p_elem=None, ns=None):
    """
    Return left-indent in pixels for a paragraph.
    Prefer python-docx Paragraph.paragraph_format.left_indent when available.
    If missing, read the raw w:ind/@w:left (twips) from the XML element (if provided).
    Conversion: twips -> points (twips/20) -> px (~1.33 * points).
    """
    try:
        left = para.paragraph_format.left_indent
        if left:
            return int(left.pt * 1.33)
    except Exception:
        pass

    # Fallback: read w:ind/@w:left from paragraph XML (twips)
    if p_elem is not None and ns is not None:
        try:
            vals = p_elem.xpath('.//w:ind/@w:left', namespaces=ns)
            if vals:
                twips = int(vals[0])
                points = twips / 20.0
                return int(points * 1.33)
        except Exception:
            pass

    return 0



def _extract_textbox_with_newlines(txbx_element, ns, doc):
    """
    Given an XML element that represents a textbox container (txbxContent or sdt),
    return HTML with paragraphs preserved. Uses python-docx Paragraph wrapper
    for accurate text extraction.
    """
    parts = []
    # find all w:p descendants (paragraphs) inside the textbox element
    for p_elem in txbx_element.xpath('.//w:p', namespaces=ns):
        p = _DocxParagraph(p_elem, doc)
        html_text = _runs_to_html(p).strip()
        if html_text:
            px = _get_paragraph_indent_px(p, p_elem, ns)
            indent_attr = f" style='margin-left:{px}px;'" if px else ""
            parts.append(f"<p{indent_attr}>{html_text}</p>")



    return "".join(parts)


def _runs_to_html(paragraph):
    """Convert a python-docx Paragraph into HTML with <b>, <i>, <u> where needed."""
    parts = []
    for run in paragraph.runs:
        text = run.text.replace("<", "&lt;").replace(">", "&gt;")
        if not text:
            continue
        if run.bold:
            text = f"<b>{text}</b>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.underline:
            text = f"<u>{text}</u>"
        parts.append(text)
    return "".join(parts)



import docx
import openpyxl
from docx.table import Table as _DocxTable
from docx.text.paragraph import Paragraph as _DocxParagraph
from docx.text.run import Run as _DocxRun



# w excel word support
@notes_bp.route('/import_files', methods=['POST'])
@login_required
def import_files():
    target_folder_id = request.form.get("target_folder_id")
    print(f"[IMPORT_FILES] Target folder id: {target_folder_id}")

    uploaded_files = request.files.getlist("import_files")
    if not uploaded_files or uploaded_files == [None]:
        flash("No files provided.", "danger")
        return redirect(url_for("folders.view_folder", folder_id=target_folder_id))

    imported_notes = 0
    imported_jsonl = 0
    target_folder = Folder.query.get(target_folder_id)

    for uploaded_file in uploaded_files:
        filename = secure_filename(uploaded_file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in (".html", ".txt", ".docx", ".xlsx", ".jsonl"):
            flash(f"Skipped {filename}: only .html, .txt, .docx, .xlsx, .jsonl allowed.", "warning")
            continue

        try:
            content = ""
            
            # Handle JSONL format (app-generated exports)
            if ext == ".jsonl":
                raw_data = uploaded_file.read().decode("utf-8", errors="ignore")
                file_data = json.loads(raw_data)
                
                # Validate it's a file record
                if file_data.get("record_type") != "file":
                    flash(f"Skipped {filename}: Invalid JSONL format (expected file record)", "warning")
                    continue
                
                # Prepare metadata with is_pinned
                metadata_json = file_data.get("metadata_json", {})
                if "is_pinned" not in metadata_json and file_data.get("is_pinned"):
                    metadata_json["is_pinned"] = file_data.get("is_pinned", False)
                
                # Create file
                new_file = File(
                    title=file_data.get("title", filename),
                    type=file_data.get("type", "proprietary_note"),
                    folder_id=target_folder.id,
                    owner_id=current_user.id,
                    is_public=file_data.get("is_public", False),
                    metadata_json=metadata_json
                )
                
                # Restore content
                if "content_text" in file_data:
                    new_file.content_text = file_data["content_text"]
                if "content_html" in file_data:
                    new_file.content_html = file_data["content_html"]
                if "content_json" in file_data:
                    new_file.content_json = file_data["content_json"]
                if "content_blob_base64" in file_data:
                    new_file.content_blob = base64.b64decode(file_data["content_blob_base64"])
                
                # Restore timestamps
                if file_data.get("created_at"):
                    try:
                        new_file.created_at = datetime.fromisoformat(file_data["created_at"])
                    except:
                        pass
                if file_data.get("last_modified"):
                    try:
                        new_file.last_modified = datetime.fromisoformat(file_data["last_modified"])
                    except:
                        pass
                
                db.session.add(new_file)
                db.session.flush()
                imported_jsonl += 1
                
                # Import graph workspace if present
                if "graph_workspace" in file_data and file_data["type"] == "proprietary_graph":
                    ws_data = file_data["graph_workspace"]
                    
                    # Create workspace
                    workspace = GraphWorkspace(
                        file_id=new_file.id,
                        owner_id=current_user.id,
                        folder_id=new_file.folder_id,
                        settings_json=ws_data.get("settings_json", {}),
                        metadata_json=ws_data.get("metadata_json", {})
                    )
                    db.session.add(workspace)
                    db.session.flush()
                    
                    # Create nodes with ID mapping
                    node_id_map = {}
                    for node_data in ws_data.get("nodes", []):
                        node = GraphNode(
                            graph_id=workspace.id,
                            title=node_data["title"],
                            summary=node_data.get("summary"),
                            position_json=node_data.get("position_json", {}),
                            size_json=node_data.get("size_json", {}),
                            style_json=node_data.get("style_json", {}),
                            metadata_json=node_data.get("metadata_json", {})
                        )
                        db.session.add(node)
                        db.session.flush()
                        node_id_map[node_data["node_id"]] = node.id
                    
                    # Create edges
                    for edge_data in ws_data.get("edges", []):
                        source_id = node_id_map.get(edge_data["source_node_id"])
                        target_id = node_id_map.get(edge_data["target_node_id"])
                        if source_id and target_id:
                            edge = GraphEdge(
                                graph_id=workspace.id,
                                source_node_id=source_id,
                                target_node_id=target_id,
                                label=edge_data.get("label"),
                                edge_type=edge_data.get("edge_type", "directed"),
                                metadata_json=edge_data.get("metadata_json", {})
                            )
                            db.session.add(edge)
                    
                    # Create attachments
                    for attach_data in ws_data.get("attachments", []):
                        node_id = node_id_map.get(attach_data["node_id"])
                        if node_id:
                            attachment = GraphNodeAttachment(
                                node_id=node_id,
                                attachment_type=attach_data["attachment_type"],
                                file_id=attach_data.get("file_id"),
                                folder_id=attach_data.get("folder_id"),
                                url=attach_data.get("url"),
                                metadata_json=attach_data.get("metadata_json", {})
                            )
                            db.session.add(attachment)
                
                print(f"[IMPORT_FILES] Imported JSONL: {filename} (type: {new_file.type})")
                continue  # Skip to next file
            
            # Handle legacy formats (HTML, TXT, etc.)
            if ext == ".html":
                raw_data = uploaded_file.read().decode("utf-8", errors="ignore")
                content = extract_and_save_images(raw_data, current_user.id)

            elif ext == ".txt":
                raw_data = uploaded_file.read().decode("utf-8", errors="ignore")
                content = f"<pre>{raw_data}</pre>"

            elif ext == ".docx":
                doc = docx.Document(uploaded_file)
                parts = []
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

                # iterate children of body to preserve original order (paras, tables, textboxes)
                for element in doc.element.body:
                    tag_local = element.tag.split('}')[-1]

                    if tag_local == 'tbl':
                        # create a Table wrapper from the XML element and render to HTML
                        tbl = _DocxTable(element, doc)
                        rows = []
                        for r in tbl.rows:
                            cells = []
                            for c in r.cells:
                                # join cell paragraphs (preserve runs/styles) with <br/> to preserve line breaks inside a cell
                                para_texts = [_runs_to_html(p).strip() for p in c.paragraphs]
                                cell_text = "<br/>".join(t for t in para_texts if t)
                                cells.append(f"<td>{cell_text}</td>")
                            rows.append(f"<tr>{''.join(cells)}</tr>")
                        parts.append("<table border='1' style='border-collapse:collapse;'>")
                        parts.extend(rows)
                        parts.append("</table>")

                    elif tag_local == 'p':
                        para = _DocxParagraph(element, doc)
                        html_text = _runs_to_html(para).strip()
                        if html_text:
                            px = _get_paragraph_indent_px(para, element, ns)
                            indent_attr = f" style='margin-left:{px}px;'" if px else ""
                            parts.append(f"<p{indent_attr}>{html_text}</p>")



                    elif tag_local in ('sdt', 'txbxContent'):
                        textbox_text = _extract_textbox_with_newlines(element, ns, doc)
                        if textbox_text:
                            parts.append(f"<div class='textbox'>{textbox_text}</div>")

                content = "".join(parts)





            elif ext == ".xlsx":
                wb = openpyxl.load_workbook(uploaded_file, data_only=True)
                sheet_tables = []

                for sheet in wb.worksheets:
                    # Start table
                    html = [f"<h4>{sheet.title}</h4>", "<table border='1' style='border-collapse:collapse;'>"]

                    for row in sheet.iter_rows(values_only=True):
                        html.append("<tr>")
                        for cell in row:
                            val = "" if cell is None else str(cell)
                            html.append(f"<td>{val}</td>")
                        html.append("</tr>")

                    html.append("</table>")
                    sheet_tables.append("".join(html))

                content = "<hr>".join(sheet_tables)


            title = os.path.splitext(filename)[0] or "Untitled"
            note = File(
                folder_id=target_folder.id,
                owner_id=current_user.id,
                type='proprietary_note',
                title=title,
                content_html=content
            )
            db.session.add(note)
            imported_notes += 1

        except Exception as e:
            current_app.logger.exception(f"Failed to import {filename}")
            flash(f"Error importing {filename}: {e}", "danger")

    db.session.commit()
    
    # Build success message
    success_parts = []
    if imported_notes > 0:
        success_parts.append(f"{imported_notes} legacy files")
    if imported_jsonl > 0:
        success_parts.append(f"{imported_jsonl} JSONL files")
    
    if success_parts:
        flash(f"Imported {' and '.join(success_parts)}.", "success")
    else:
        flash("No files were imported.", "info")

    return redirect(url_for("folders.view_folder", folder_id=target_folder_id))







def dict_to_folder(folder_dict, parent_folder, user_id, id_mapping, imported_images):
    """
    Recursively create folder structure from dictionary
    Returns the created folder and updates id_mapping
    """
    # Create folder
    new_folder = Folder(
        name=folder_dict["name"],
        user_id=user_id,
        parent_id=parent_folder.id if parent_folder else None
    )
    db.session.add(new_folder)
    db.session.flush()  # Get the ID
    
    # Map old ID to new ID
    old_id = folder_dict["id"]
    id_mapping[f"folder_{old_id}"] = new_folder.id
    
    # Create notes
    for note_dict in folder_dict.get("notes", []):
        # Content stays as-is, images are already copied to disk
        note = File(
            title=note_dict["title"],
            content_html=note_dict["content"],
            folder_id=new_folder.id,
            owner_id=user_id,
            type='proprietary_note'
        )
        db.session.add(note)
    
    # Create boards
    for board_dict in folder_dict.get("boards", []):
        board = File(
            title=board_dict["title"],
            content_json=board_dict["content"],
            folder_id=new_folder.id,
            owner_id=user_id,
            type='whiteboard'
        )
        db.session.add(board)
    
    # Recursively create children
    for child_dict in folder_dict.get("children", []):
        dict_to_folder(child_dict, new_folder, user_id, id_mapping, imported_images)
    
    return new_folder


def import_jsonl_to_folder(jsonl_lines, target_folder, user_id):
    """
    Import JSONL format backup to restore folders and files.
    
    Args:
        jsonl_lines: List of JSON strings (one per line from data.jsonl)
        target_folder: Target Folder object to import into
        user_id: Current user's ID
    
    Returns:
        Dict with counts: {"folders": int, "files": int, "images": int, "errors": list, "graph_items": int}
    """
    # Track IDs mapping (old ID -> new ID) to maintain relationships
    folder_id_map = {}
    path_to_folder = {}  # path -> Folder object
    file_id_map = {}  # old file ID -> new File object
    node_id_map = {}  # old node ID -> new GraphNode object
    
    stats = {
        "folders": 0,
        "files": 0,
        "images": 0,
        "graph_items": 0,
        "errors": []
    }
    
    # First pass: Create all folders
    for line in jsonl_lines:
        try:
            record = json.loads(line)
            
            if record["record_type"] == "folder":
                path = record["path"]
                old_id = record["id"]
                
                # Determine parent folder
                parent_path = "/".join(path.split("/")[:-1]) if "/" in path else ""
                parent_folder = path_to_folder.get(parent_path, target_folder)
                
                # Create folder
                new_folder = Folder(
                    name=record["name"],
                    user_id=user_id,
                    parent_id=parent_folder.id if parent_folder else None,
                    description=record.get("description"),
                    is_public=record.get("is_public", False),
                    is_root=False  # Never import as root
                )
                
                # Restore timestamps if available
                if record.get("created_at"):
                    try:
                        new_folder.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                db.session.add(new_folder)
                db.session.flush()  # Get the ID
                
                # Track mapping
                folder_id_map[old_id] = new_folder.id
                path_to_folder[path] = new_folder
                stats["folders"] += 1
                
                print(f"[IMPORT] Created folder: {path} (ID: {new_folder.id})")
        
        except Exception as e:
            stats["errors"].append(f"Folder import error: {str(e)}")
            print(f"[IMPORT] Error creating folder: {e}")
    
    # Second pass: Create all files
    for line in jsonl_lines:
        try:
            record = json.loads(line)
            
            if record["record_type"] == "file":
                folder_path = record["folder_path"]
                folder = path_to_folder.get(folder_path, target_folder)
                
                # Prepare metadata_json with is_pinned
                metadata_json = record.get("metadata_json", {})
                if "is_pinned" not in metadata_json and record.get("is_pinned"):
                    metadata_json["is_pinned"] = record.get("is_pinned", False)
                
                # Create file with appropriate content
                new_file = File(
                    title=record["title"],
                    type=record["type"],
                    folder_id=folder.id,
                    owner_id=user_id,
                    is_public=record.get("is_public", False),
                    metadata_json=metadata_json
                )
                
                # Restore content based on type
                if "content_text" in record:
                    new_file.content_text = record["content_text"]
                
                if "content_html" in record:
                    new_file.content_html = record["content_html"]
                
                if "content_json" in record:
                    new_file.content_json = record["content_json"]
                
                if "content_blob_base64" in record:
                    new_file.content_blob = base64.b64decode(record["content_blob_base64"])
                
                # Restore timestamps
                if record.get("created_at"):
                    try:
                        new_file.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                if record.get("last_modified"):
                    try:
                        new_file.last_modified = datetime.fromisoformat(record["last_modified"])
                    except:
                        pass
                
                db.session.add(new_file)
                db.session.flush()  # Get the ID for graph workspace mapping
                
                # Track file mapping for graph workspace references
                old_file_id = record.get("id")
                if old_file_id:
                    file_id_map[old_file_id] = new_file
                
                stats["files"] += 1
                
                print(f"[IMPORT] Created file: {record['title']} (type: {record['type']})")
        
        except Exception as e:
            stats["errors"].append(f"File import error ({record.get('title', 'unknown')}): {str(e)}")
            print(f"[IMPORT] Error creating file: {e}")
    
    # Third pass: Create graph workspaces, nodes, edges, and attachments
    for line in jsonl_lines:
        try:
            record = json.loads(line)
            
            if record["record_type"] == "graph_workspace":
                old_file_id = record["file_id"]
                new_file = file_id_map.get(old_file_id)
                
                if not new_file:
                    stats["errors"].append(f"Graph workspace references missing file ID: {old_file_id}")
                    continue
                
                # Create graph workspace
                workspace = GraphWorkspace(
                    file_id=new_file.id,
                    owner_id=user_id,
                    folder_id=new_file.folder_id,
                    settings_json=record.get("settings_json", {}),
                    metadata_json=record.get("metadata_json", {})
                )
                
                # Restore timestamps
                if record.get("created_at"):
                    try:
                        workspace.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                if record.get("updated_at"):
                    try:
                        workspace.updated_at = datetime.fromisoformat(record["updated_at"])
                    except:
                        pass
                
                db.session.add(workspace)
                db.session.flush()  # Get the ID
                stats["graph_items"] += 1
                print(f"[IMPORT] Created graph workspace for file ID: {new_file.id}")
            
            elif record["record_type"] == "graph_node":
                old_file_id = record["graph_file_id"]
                new_file = file_id_map.get(old_file_id)
                
                if not new_file or not hasattr(new_file, 'graph_workspace') or not new_file.graph_workspace:
                    stats["errors"].append(f"Graph node references missing workspace for file ID: {old_file_id}")
                    continue
                
                workspace = new_file.graph_workspace
                old_node_id = record["node_id"]
                
                # Create graph node
                node = GraphNode(
                    graph_id=workspace.id,
                    title=record["title"],
                    summary=record.get("summary"),
                    position_json=record.get("position_json", {}),
                    size_json=record.get("size_json", {}),
                    style_json=record.get("style_json", {}),
                    metadata_json=record.get("metadata_json", {})
                )
                
                # Restore timestamps
                if record.get("created_at"):
                    try:
                        node.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                if record.get("updated_at"):
                    try:
                        node.updated_at = datetime.fromisoformat(record["updated_at"])
                    except:
                        pass
                
                db.session.add(node)
                db.session.flush()  # Get the ID
                
                # Track node ID mapping for edges
                node_id_map[old_node_id] = node
                stats["graph_items"] += 1
                print(f"[IMPORT] Created graph node: {node.title} (ID: {node.id})")
        
        except Exception as e:
            stats["errors"].append(f"Graph workspace/node import error: {str(e)}")
            print(f"[IMPORT] Error creating graph workspace/node: {e}")
    
    # Fourth pass: Create graph edges (requires nodes to exist)
    for line in jsonl_lines:
        try:
            record = json.loads(line)
            
            if record["record_type"] == "graph_edge":
                old_file_id = record["graph_file_id"]
                new_file = file_id_map.get(old_file_id)
                
                if not new_file or not hasattr(new_file, 'graph_workspace') or not new_file.graph_workspace:
                    stats["errors"].append(f"Graph edge references missing workspace for file ID: {old_file_id}")
                    continue
                
                workspace = new_file.graph_workspace
                old_source_id = record["source_node_id"]
                old_target_id = record["target_node_id"]
                
                source_node = node_id_map.get(old_source_id)
                target_node = node_id_map.get(old_target_id)
                
                if not source_node or not target_node:
                    stats["errors"].append(f"Graph edge references missing nodes: {old_source_id} -> {old_target_id}")
                    continue
                
                # Create graph edge
                edge = GraphEdge(
                    graph_id=workspace.id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    label=record.get("label"),
                    edge_type=record.get("edge_type", "directed"),
                    metadata_json=record.get("metadata_json", {})
                )
                
                # Restore timestamps
                if record.get("created_at"):
                    try:
                        edge.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                if record.get("updated_at"):
                    try:
                        edge.updated_at = datetime.fromisoformat(record["updated_at"])
                    except:
                        pass
                
                db.session.add(edge)
                stats["graph_items"] += 1
                print(f"[IMPORT] Created graph edge: {source_node.title} -> {target_node.title}")
            
            elif record["record_type"] == "graph_node_attachment":
                old_file_id = record["graph_file_id"]
                old_node_id = record["node_id"]
                
                node = node_id_map.get(old_node_id)
                
                if not node:
                    stats["errors"].append(f"Graph attachment references missing node ID: {old_node_id}")
                    continue
                
                # Create node attachment
                attachment = GraphNodeAttachment(
                    node_id=node.id,
                    attachment_type=record["attachment_type"],
                    file_id=record.get("file_id"),
                    folder_id=record.get("folder_id"),
                    url=record.get("url"),
                    metadata_json=record.get("metadata_json", {})
                )
                
                # Restore timestamps
                if record.get("created_at"):
                    try:
                        attachment.created_at = datetime.fromisoformat(record["created_at"])
                    except:
                        pass
                
                if record.get("updated_at"):
                    try:
                        attachment.updated_at = datetime.fromisoformat(record["updated_at"])
                    except:
                        pass
                
                db.session.add(attachment)
                stats["graph_items"] += 1
                print(f"[IMPORT] Created graph node attachment for node: {node.title}")
        
        except Exception as e:
            stats["errors"].append(f"Graph edge/attachment import error: {str(e)}")
            print(f"[IMPORT] Error creating graph edge/attachment: {e}")
    
    return stats


@notes_bp.route('/import_notes', methods=['POST'])
@login_required
def import_notes():
    """
    Import ZIP backup with individual JSONL files and images.
    
    Supports:
    - v5.0: Individual JSONL format (folders.jsonl + files/*.jsonl + images/)
    - v4.0: Legacy JSONL format (data.jsonl + images/) - for backward compatibility
    - v3.0: Legacy JSON format (export_data.json + images/) - for backward compatibility
    
    Images are copied from ZIP to static/uploads/images/ directory.
    """
    from blueprints.p2.utils import add_notification
    
    target_folder_id = request.form.get("target_folder_id", type=int)
    print(f"[IMPORT] Target folder id: {target_folder_id}")

    uploaded_file = request.files.get("import_zip")
    if uploaded_file is None:
        add_notification(current_user.id, "Import failed: No file provided", "error")
        return redirect(url_for("folders.view_folder", folder_id=target_folder_id))

    filename = uploaded_file.filename or ""
    if not filename.lower().endswith(".zip"):
        add_notification(current_user.id, "Import failed: Please upload a ZIP file", "error")
        return redirect(url_for("folders.view_folder", folder_id=target_folder_id))

    print(f"[IMPORT] Uploaded filename: {filename}")
    
    zip_bytes = uploaded_file.read()
    print(f"[IMPORT] File size: {len(zip_bytes)} bytes")

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            file_list = zf.namelist()
            
            # Check format version
            has_folders_jsonl = "folders.jsonl" in file_list
            has_files_dir = any(f.startswith("files/") for f in file_list)
            has_data_jsonl = "data.jsonl" in file_list
            has_manifest = "manifest.json" in file_list
            has_legacy_json = "export_data.json" in file_list
            
            # Get target folder
            target_folder = None
            if target_folder_id:
                target_folder = Folder.query.get(target_folder_id)
            if not target_folder:
                target_folder = Folder.query.filter_by(
                    user_id=current_user.id, 
                    parent_id=None
                ).first()
            
            if not target_folder:
                add_notification(current_user.id, "Import failed: No target folder found", "error")
                return redirect(url_for("folders.view_folder", folder_id=target_folder_id))
            
            # v5.0: Individual JSONL files
            if has_folders_jsonl and has_files_dir:
                print("[IMPORT] Detected individual JSONL format (v5.0)")
                
                # Read manifest if available
                if has_manifest:
                    with zf.open("manifest.json") as f:
                        manifest = json.load(f)
                        print(f"[IMPORT] Manifest: {manifest.get('summary', {})}")
                
                # Step 1: Copy all images from ZIP to static/uploads/images/
                images_imported = 0
                image_files = [f for f in file_list if f.startswith("images/") and not f.endswith("/")]
                print(f"[IMPORT] Found {len(image_files)} images in ZIP")
                
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                for image_path in image_files:
                    image_filename = os.path.basename(image_path)
                    target_path = os.path.join(UPLOAD_FOLDER, image_filename)
                    
                    # Copy image from ZIP to disk
                    with zf.open(image_path) as img_src:
                        image_data = img_src.read()
                        
                        # Only copy if it doesn't exist (avoid overwriting)
                        if not os.path.exists(target_path):
                            with open(target_path, 'wb') as img_dst:
                                img_dst.write(image_data)
                            
                            # Update user data size
                            file_size = len(image_data)
                            update_user_data_size(current_user, file_size)
                            images_imported += 1
                            print(f"[IMPORT] Copied image: {image_filename} ({file_size} bytes)")
                        else:
                            print(f"[IMPORT] Image already exists: {image_filename}")
                
                # Step 2: Import folder hierarchy
                folder_id_map = {}
                path_to_folder = {}
                folders_created = 0
                
                with zf.open("folders.jsonl") as f:
                    folders_content = f.read().decode('utf-8')
                    folder_lines = folders_content.strip().split('\n')
                    
                    for line in folder_lines:
                        folder_record = json.loads(line)
                        path = folder_record["path"]
                        old_id = folder_record["id"]
                        
                        # Determine parent folder
                        parent_path = "/".join(path.split("/")[:-1]) if "/" in path else ""
                        parent_folder = path_to_folder.get(parent_path, target_folder)
                        
                        # Create folder
                        new_folder = Folder(
                            name=folder_record["name"],
                            user_id=current_user.id,
                            parent_id=parent_folder.id if parent_folder else None,
                            description=folder_record.get("description"),
                            is_public=folder_record.get("is_public", False),
                            is_root=False  # Never import as root
                        )
                        
                        # Restore timestamps
                        if folder_record.get("created_at"):
                            try:
                                new_folder.created_at = datetime.fromisoformat(folder_record["created_at"])
                            except:
                                pass
                        
                        db.session.add(new_folder)
                        db.session.flush()
                        
                        folder_id_map[old_id] = new_folder.id
                        path_to_folder[path] = new_folder
                        folders_created += 1
                        print(f"[IMPORT] Created folder: {path} (ID: {new_folder.id})")
                
                # Step 3: Import individual file JSONL files
                files_created = 0
                graph_items_created = 0
                errors = []
                
                file_jsonl_list = [f for f in file_list if f.startswith("files/") and f.endswith(".jsonl")]
                print(f"[IMPORT] Found {len(file_jsonl_list)} file JSONL files")
                
                for file_jsonl_path in file_jsonl_list:
                    try:
                        with zf.open(file_jsonl_path) as f:
                            file_data = json.load(f)
                        
                        folder_path = file_data["folder_path"]
                        folder = path_to_folder.get(folder_path, target_folder)
                        
                        # Prepare metadata with is_pinned
                        metadata_json = file_data.get("metadata_json", {})
                        if "is_pinned" not in metadata_json and file_data.get("is_pinned"):
                            metadata_json["is_pinned"] = file_data.get("is_pinned", False)
                        
                        # Create file
                        new_file = File(
                            title=file_data["title"],
                            type=file_data["type"],
                            folder_id=folder.id,
                            owner_id=current_user.id,
                            is_public=file_data.get("is_public", False),
                            metadata_json=metadata_json
                        )
                        
                        # Restore content
                        if "content_text" in file_data:
                            new_file.content_text = file_data["content_text"]
                        if "content_html" in file_data:
                            new_file.content_html = file_data["content_html"]
                        if "content_json" in file_data:
                            new_file.content_json = file_data["content_json"]
                        if "content_blob_base64" in file_data:
                            new_file.content_blob = base64.b64decode(file_data["content_blob_base64"])
                        
                        # Restore timestamps
                        if file_data.get("created_at"):
                            try:
                                new_file.created_at = datetime.fromisoformat(file_data["created_at"])
                            except:
                                pass
                        if file_data.get("last_modified"):
                            try:
                                new_file.last_modified = datetime.fromisoformat(file_data["last_modified"])
                            except:
                                pass
                        
                        db.session.add(new_file)
                        db.session.flush()
                        files_created += 1
                        print(f"[IMPORT] Created file: {file_data['title']} (type: {file_data['type']})")
                        
                        # Import graph workspace if present
                        if "graph_workspace" in file_data and file_data["type"] == "proprietary_graph":
                            ws_data = file_data["graph_workspace"]
                            
                            # Create workspace
                            workspace = GraphWorkspace(
                                file_id=new_file.id,
                                owner_id=current_user.id,
                                folder_id=new_file.folder_id,
                                settings_json=ws_data.get("settings_json", {}),
                                metadata_json=ws_data.get("metadata_json", {})
                            )
                            db.session.add(workspace)
                            db.session.flush()
                            graph_items_created += 1
                            
                            # Create nodes with ID mapping
                            node_id_map = {}
                            for node_data in ws_data.get("nodes", []):
                                node = GraphNode(
                                    graph_id=workspace.id,
                                    title=node_data["title"],
                                    summary=node_data.get("summary"),
                                    position_json=node_data.get("position_json", {}),
                                    size_json=node_data.get("size_json", {}),
                                    style_json=node_data.get("style_json", {}),
                                    metadata_json=node_data.get("metadata_json", {})
                                )
                                db.session.add(node)
                                db.session.flush()
                                node_id_map[node_data["node_id"]] = node.id
                                graph_items_created += 1
                            
                            # Create edges
                            for edge_data in ws_data.get("edges", []):
                                source_id = node_id_map.get(edge_data["source_node_id"])
                                target_id = node_id_map.get(edge_data["target_node_id"])
                                if source_id and target_id:
                                    edge = GraphEdge(
                                        graph_id=workspace.id,
                                        source_node_id=source_id,
                                        target_node_id=target_id,
                                        label=edge_data.get("label"),
                                        edge_type=edge_data.get("edge_type", "directed"),
                                        metadata_json=edge_data.get("metadata_json", {})
                                    )
                                    db.session.add(edge)
                                    graph_items_created += 1
                            
                            # Create attachments
                            for attach_data in ws_data.get("attachments", []):
                                node_id = node_id_map.get(attach_data["node_id"])
                                if node_id:
                                    attachment = GraphNodeAttachment(
                                        node_id=node_id,
                                        attachment_type=attach_data["attachment_type"],
                                        file_id=attach_data.get("file_id"),
                                        folder_id=attach_data.get("folder_id"),
                                        url=attach_data.get("url"),
                                        metadata_json=attach_data.get("metadata_json", {})
                                    )
                                    db.session.add(attachment)
                                    graph_items_created += 1
                    
                    except Exception as e:
                        error_msg = f"Failed to import {os.path.basename(file_jsonl_path)}: {str(e)}"
                        errors.append(error_msg)
                        print(f"[IMPORT] {error_msg}")
                
                db.session.commit()
                
                # Build success message
                summary_parts = []
                if folders_created:
                    summary_parts.append(f"{folders_created} folders")
                if files_created:
                    summary_parts.append(f"{files_created} files")
                if graph_items_created:
                    summary_parts.append(f"{graph_items_created} graph items")
                if images_imported:
                    summary_parts.append(f"{images_imported} images")
                
                if summary_parts:
                    add_notification(current_user.id, f"Imported {', '.join(summary_parts)}", "info")
                else:
                    add_notification(current_user.id, "No content imported from archive", "info")
                
                if errors:
                    for error in errors[:3]:  # Show first 3 errors
                        add_notification(current_user.id, f"Warning: {error}", "error")
                
                print(f"[IMPORT] Successfully imported v5.0 format")
            
            # v4.0: Legacy single JSONL format
            elif has_data_jsonl and has_manifest:
                print("[IMPORT] Detected legacy JSONL format (v4.0)")
                add_notification(current_user.id, "Legacy v4.0 format detected - consider re-exporting", "info")
                
                # Use old import function
                with zf.open("data.jsonl") as f:
                    jsonl_content = f.read().decode('utf-8')
                    jsonl_lines = jsonl_content.strip().split('\n')
                
                stats = import_jsonl_to_folder(jsonl_lines, target_folder, current_user.id)
                db.session.commit()
                
                add_notification(
                    current_user.id, 
                    f"Imported {stats['folders']} folders, {stats['files']} files (legacy format)", 
                    "info"
                )
            
            # v3.0: Legacy JSON format
            elif has_legacy_json:
                print("[IMPORT] Detected legacy JSON format (v3.0)")
                add_notification(current_user.id, "Legacy v3.0 format - please re-export for better compatibility", "info")
                
                with zf.open("export_data.json") as f:
                    export_data = json.load(f)
                
                folder_data = export_data.get("folder", {})
                id_mapping = {}
                dict_to_folder(folder_data, target_folder, current_user.id, id_mapping, 0)
                
                db.session.commit()
                add_notification(current_user.id, "Imported legacy v3.0 backup", "info")
            
            else:
                add_notification(current_user.id, "Unsupported backup format", "error")
                print("[IMPORT] Unsupported format")

    except zipfile.BadZipFile:
        add_notification(current_user.id, "Invalid ZIP file", "error")
        print("[IMPORT] Invalid ZIP file")
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Import failed")
        add_notification(current_user.id, f"Import error: {str(e)}", "error")
        print(f"[IMPORT] Error: {e}")
        import traceback
        traceback.print_exc()

    return redirect(url_for("folders.view_folder", folder_id=target_folder_id))





# Add new route for handling image uploads from Summernote
@notes_bp.route('/upload_image', methods=['POST'])
@login_required
def upload_image():
    """
    Handle direct image uploads from Summernote - convert all to WebP with deduplication
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        # Ensure upload directory exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_IMAGE_SIZE:
            return jsonify({'error': 'File too large'}), 400

        # Save temporary file first to calculate hash
        temp_original = f"temp_original_{uuid.uuid4().hex}"
        temp_original_path = os.path.join(UPLOAD_FOLDER, temp_original)
        file.save(temp_original_path)

        # Calculate hash of original file
        image_hash = get_image_hash(temp_original_path)

        # Check if this image already exists for this user
        existing_url = get_existing_image_by_hash(current_user.id, image_hash)
        if existing_url:
            # Clean up temp file and return existing image URL
            os.remove(temp_original_path)
            print(f"DEBUG: Using existing image for hash {image_hash}: {existing_url}")
            return jsonify({'url': existing_url})

        # Generate hash-based filename - always WebP
        filename = f"{current_user.id}_{image_hash}.webp"
        final_filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Convert to WebP
        actual_filepath = convert_to_webp(temp_original_path, final_filepath)

        # Clean up temp file
        os.remove(temp_original_path)

        # Get final file size and update user data size
        if os.path.exists(actual_filepath):
            final_file_size = os.path.getsize(actual_filepath)

            if not check_guest_limit(current_user, final_file_size):
                # Remove the file if it would exceed the limit
                os.remove(actual_filepath)
                return jsonify({'error': 'Storage limit exceeded'}), 400

            update_user_data_size(current_user, final_file_size)

        # Return URL for Summernote
        filename = os.path.basename(actual_filepath)
        url = f"/static/uploads/images/{filename}"
        print(f"DEBUG: Created new image with hash {image_hash}: {url}")
        return jsonify({'url': url})

    except Exception as e:
        print(f"Error uploading image: {e}")
        return jsonify({'error': 'Upload failed'}), 500




# Update autosave functions
@notes_bp.post("/autosave")
@login_required
def autosave():
    note_id = request.form.get("note_id", type=int)
    title = (request.form.get("title") or "").strip()
    content = request.form.get("content") or ""
    description = request.form.get("description") or ''

    if not (note_id or content or title):
        return Response(status=204)

    try:
        if note_id:
            note = File.query.filter_by(id=note_id, type='proprietary_note').first_or_404()
            if note.owner_id != current_user.id:
                return Response("Forbidden", status=403)

            # Process images in content
            content = extract_and_save_images(content, current_user.id)

            # Update title if provided
            if title:
                note.title = title

            # Compute size delta for content and update
            old_size = calculate_content_size(note.content_html)
            new_size = calculate_content_size(content)
            delta = new_size - old_size
            if not check_guest_limit(current_user, delta):
                return Response("Data limit exceeded", status=400)
            
            print(f"DEBUG: Autosave - updating note {note_id}")
            print(f"  - Title: {title[:50] if title else 'NO TITLE'}")
            print(f"  - Content length: {len(content)}")
            print(f"  - Content preview: {content[:100] if content else 'EMPTY'}")
            print(f"  - Description length: {len(description) if description else 0}")
            print(f"  - Old content_html length: {len(note.content_html or '')}")
            
            note.content_html = content
            note.last_modified = datetime.utcnow()
            
            print(f"  - New content_html length: {len(note.content_html or '')}")
            print(f"  - Content_html updated: {note.content_html is not None}")
            
            # Flag content_html as modified for SQLAlchemy
            flag_modified(note, 'content_html')

            # Update description in metadata_json
            if description is not None and description != '':
                if not note.metadata_json:
                    note.metadata_json = {}
                note.metadata_json['description'] = description
                print(f"DEBUG: Autosave - Setting metadata_json: {note.metadata_json}")
                flag_modified(note, 'metadata_json')

            db.session.commit()
            print(f"DEBUG: Autosave - committed successfully")
            
            # Verify the save by re-querying
            db.session.refresh(note)
            print(f"DEBUG: Autosave - POST-COMMIT verification:")
            print(f"  - Database content_html length: {len(note.content_html or '')}")
            print(f"  - Database content_html preview: {(note.content_html or '')[:100]}")
            print(f"  - Database metadata_json: {note.metadata_json}")
            
            update_user_data_size(current_user, delta)
            # Update description if present and valid JSON
            if description:
                try:
                    import json as _json
                    parsed = _json.loads(description)
                    if isinstance(parsed, (dict, list)):
                        note.description = description
                        db.session.commit()
                    else:
                        print(f"DEBUG: autosave - description for note {note_id} not dict/list; ignoring")
                except Exception:
                    print(f"DEBUG: autosave - failed to parse description JSON for note {note_id}; ignoring")
    except SQLAlchemyError:
        db.session.rollback()
        return Response(status=204)

    return Response(status=204)

@notes_bp.post("/autosave_draft")
@login_required
def autosave_draft():
    title = (request.form.get("title") or "").strip()
    content = request.form.get("content") or ""
    description = request.form.get("description") or ''

    current_folder_id = session.get('current_folder_id')
    if not current_folder_id:
        root_folder = Folder.query.filter_by(user_id=current_user.id, parent_id=None).first()
        if root_folder:
            current_folder_id = root_folder.id
        else:
            # Create root folder if it doesn't exist
            root_folder = Folder(name="Root", user_id=current_user.id)
            db.session.add(root_folder)
            db.session.commit()
            current_folder_id = root_folder.id

    try:
        # Process images in content
        content = extract_and_save_images(content, current_user.id)

        # If there's any meaningful data (title or content), create a draft note
        if title or content or description:
            # If title empty, generate a default title
            if not title:
                title = f"Untitled on {now}"
            content_size = calculate_content_size(content)
            if not check_guest_limit(current_user, content_size):
                return jsonify({"ok": False, "error": "Data limit exceeded"}), 400
            note = File(
                folder_id=current_folder_id,
                title=title,
                content_html=content,
                owner_id=current_user.id,
                type='proprietary_note',
                metadata_json={'description': description} if description else {}
            )
            db.session.add(note)
            db.session.commit()
            update_user_data_size(current_user, content_size)
            return jsonify({"ok": True, "note_id": note.id, "edit_url": url_for('notes.edit_note', note_id=note.id)}), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": "autosave_draft_failed"}), 500


@notes_bp.route('/export_folder_as_pdf')
@login_required
def export_folder_as_pdf():
    """
    Export all MioNotes, MioDraws, and MioBooks from the current folder as individual PDFs in a ZIP file.
    Maintains folder structure and converts each item to a separate PDF.
    """
    current_folder_id = session.get("current_folder_id")
    user_id = current_user.id
    username = current_user.username

    if current_folder_id:
        start_folder = Folder.query.filter_by(
            id=current_folder_id,
            user_id=user_id
        ).first()
    else:
        start_folder = Folder.query.filter_by(user_id=user_id, parent_id=None).first()

    if not start_folder:
        flash("Folder not found.", "danger")
        return redirect(url_for("folders.view_folder",
                                folder_id=session.get("current_folder_id", 0)))

    # Create a temporary directory to hold the PDF files
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Define PDF styles once (reused for all PDFs)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#1a365d'),
            spaceAfter=20,
            alignment=TA_LEFT,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c5282'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=6
        )
        
        code_style = ParagraphStyle(
            'CodeStyle',
            parent=styles['Normal'],
            fontName='Courier',
            fontSize=9,
            leading=11,
            leftIndent=20,
            backgroundColor=colors.HexColor('#f5f5f5'),
            spaceAfter=6
        )
        
        # Helper function to sanitize filename
        def sanitize_filename(filename):
            """Remove or replace invalid filename characters"""
            # Replace invalid characters with underscore
            invalid_chars = '<>:"/\\|?*'
            for char in invalid_chars:
                filename = filename.replace(char, '_')
            # Limit length
            return filename[:200]
        
        # Helper function to create a PDF for a single note
        def create_note_pdf(note, folder_path):
            """Create a PDF for a single MioNote note"""
            try:
                pdf_filename = sanitize_filename(f"{note.title}.pdf")
                pdf_path = os.path.join(folder_path, pdf_filename)
                
                # Create PDF
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter,
                                       rightMargin=72, leftMargin=72,
                                       topMargin=72, bottomMargin=72)
                
                elements = []
                
                # Add title
                elements.append(Paragraph(note.title, title_style))
                elements.append(Spacer(1, 0.2*inch))
                
                # Add metadata
                meta_text = f"Type: MioNote | Created: {note.created_at.strftime('%Y-%m-%d %H:%M')}"
                elements.append(Paragraph(meta_text, ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
                elements.append(Spacer(1, 0.3*inch))
                
                # Convert HTML content to formatted PDF content
                if note.content_html:
                    soup = BeautifulSoup(note.content_html, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    
                    # Process top-level elements only (not descendants) to avoid duplication
                    def process_element(elem, level=0):
                        """Recursively process elements and convert to PDF content"""
                        if not hasattr(elem, 'name') or elem.name is None:
                            # This is a text node
                            return
                        
                        tag = elem.name.lower()
                        
                        # Headings
                        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                            text = elem.get_text().strip()
                            if text:
                                # Escape special characters
                                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                try:
                                    elements.append(Paragraph(text, heading_style))
                                    elements.append(Spacer(1, 0.1*inch))
                                except Exception as e:
                                    print(f"[PDF] Error with heading: {e}")
                        
                        # Paragraphs
                        elif tag == 'p':
                            # Check if paragraph contains images
                            imgs = elem.find_all('img', recursive=False)
                            if imgs:
                                # Process images in paragraph
                                for img in imgs:
                                    process_element(img, level)
                            
                            # Process text content
                            text = elem.get_text().strip()
                            if text:
                                # Escape special characters
                                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                try:
                                    elements.append(Paragraph(text, normal_style))
                                    elements.append(Spacer(1, 0.08*inch))
                                except Exception as e:
                                    print(f"[PDF] Error with paragraph: {e}")
                        
                        # Preformatted text / code blocks
                        elif tag in ['pre', 'code']:
                            text = elem.get_text().strip()
                            if text:
                                # Escape special characters
                                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                try:
                                    elements.append(Paragraph(text, code_style))
                                    elements.append(Spacer(1, 0.08*inch))
                                except Exception as e:
                                    print(f"[PDF] Error with code: {e}")
                        
                        # Lists
                        elif tag in ['ul', 'ol']:
                            for li in elem.find_all('li', recursive=False):
                                text = li.get_text().strip()
                                if text:
                                    # Escape special characters
                                    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                    bullet = '•' if tag == 'ul' else f"{elem.find_all('li', recursive=False).index(li) + 1}."
                                    try:
                                        elements.append(Paragraph(f"{bullet} {text}", normal_style))
                                        elements.append(Spacer(1, 0.05*inch))
                                    except Exception as e:
                                        print(f"[PDF] Error with list item: {e}")
                        
                        # Tables
                        elif tag == 'table':
                            try:
                                table_data = []
                                for row in elem.find_all('tr'):
                                    row_data = []
                                    for cell in row.find_all(['td', 'th']):
                                        cell_text = cell.get_text().strip().replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                        row_data.append(cell_text)
                                    if row_data:
                                        table_data.append(row_data)
                                
                                if table_data:
                                    t = RLTable(table_data)
                                    t.setStyle([
                                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                                        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                                        ('PADDING', (0, 0), (-1, -1), 6),
                                    ])
                                    elements.append(t)
                                    elements.append(Spacer(1, 0.1*inch))
                            except Exception as e:
                                print(f"[PDF] Error with table: {e}")
                        
                        # Images
                        elif tag == 'img':
                            try:
                                img_src = elem.get('src', '')
                                if img_src:
                                    img_path = None
                                    
                                    # Handle various local image path formats
                                    if any(prefix in img_src for prefix in ['/static/uploads/images/', 'static/uploads/images/', '/uploads/images/', 'uploads/images/']):
                                        # Extract filename
                                        filename = img_src.split('/')[-1]
                                        
                                        # Try multiple possible paths
                                        possible_paths = [
                                            os.path.join(UPLOAD_FOLDER, filename),
                                            os.path.normpath(os.path.join('static', 'uploads', 'images', filename)),
                                            os.path.normpath(os.path.join(os.getcwd(), 'static', 'uploads', 'images', filename))
                                        ]
                                        
                                        for path in possible_paths:
                                            if os.path.exists(path) and os.path.isfile(path):
                                                img_path = path
                                                break
                                        
                                        if img_path:
                                            try:
                                                # Get image dimensions to calculate proper size
                                                from PIL import Image as PILImage
                                                with PILImage.open(img_path) as pil_img:
                                                    img_width, img_height = pil_img.size
                                                    aspect_ratio = img_height / img_width
                                                    
                                                    # Set max width to 5 inches
                                                    max_width = 5 * inch
                                                    pdf_width = min(max_width, img_width)
                                                    pdf_height = pdf_width * aspect_ratio
                                                    
                                                    # Add image to PDF
                                                    img = RLImage(img_path, width=pdf_width, height=pdf_height)
                                                    elements.append(img)
                                                    elements.append(Spacer(1, 0.15*inch))
                                                    print(f"[PDF] Added image: {filename} ({img_width}x{img_height})")
                                            except Exception as img_error:
                                                print(f"[PDF] Error processing image {filename}: {img_error}")
                                                # Add placeholder text
                                                elements.append(Paragraph(f"[Image: {filename}]", normal_style))
                                                elements.append(Spacer(1, 0.05*inch))
                                        else:
                                            print(f"[PDF] Image not found: {filename}")
                                            elements.append(Paragraph(f"[Image not found: {filename}]", normal_style))
                                            elements.append(Spacer(1, 0.05*inch))
                                    
                                    # Handle external images (note them)
                                    elif img_src.startswith('http'):
                                        elements.append(Paragraph(f"[External image: {img_src[:60]}...]", normal_style))
                                        elements.append(Spacer(1, 0.05*inch))
                                    
                                    # Handle base64 images
                                    elif img_src.startswith('data:image'):
                                        elements.append(Paragraph("[Embedded base64 image]", normal_style))
                                        elements.append(Spacer(1, 0.05*inch))
                                        
                            except Exception as e:
                                print(f"[PDF] Error with image element: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Dividers
                        elif tag == 'hr':
                            elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
                            elements.append(Spacer(1, 0.1*inch))
                        
                        # Block quotes
                        elif tag == 'blockquote':
                            text = elem.get_text().strip()
                            if text:
                                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                quote_style = ParagraphStyle(
                                    'Quote',
                                    parent=normal_style,
                                    leftIndent=30,
                                    rightIndent=30,
                                    textColor=colors.HexColor('#555555'),
                                    fontName='Helvetica-Oblique'
                                )
                                try:
                                    elements.append(Paragraph(f'"{text}"', quote_style))
                                    elements.append(Spacer(1, 0.1*inch))
                                except Exception as e:
                                    print(f"[PDF] Error with blockquote: {e}")
                        
                        # Divs - process children (including images)
                        elif tag in ['div', 'section', 'article', 'main', 'body']:
                            for child in elem.children:
                                process_element(child, level + 1)
                        
                        # Spans and other inline elements - check for images
                        elif tag in ['span', 'a', 'strong', 'em', 'b', 'i', 'u']:
                            # Check for nested images
                            imgs = elem.find_all('img')
                            if imgs:
                                for img in imgs:
                                    process_element(img, level)
                            # Process text if no images
                            elif elem.get_text().strip():
                                text = elem.get_text().strip()
                                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                                try:
                                    elements.append(Paragraph(text, normal_style))
                                    elements.append(Spacer(1, 0.05*inch))
                                except Exception as e:
                                    print(f"[PDF] Error with inline element: {e}")
                        
                        # Line breaks
                        elif tag == 'br':
                            elements.append(Spacer(1, 0.05*inch))
                    
                    # First, handle any standalone images in the content
                    all_images = soup.find_all('img')
                    processed_images = set()
                    
                    # Process body content
                    body = soup.find('body')
                    if body:
                        for child in body.children:
                            process_element(child)
                    else:
                        # No body tag, process all top-level elements
                        for child in soup.children:
                            process_element(child)
                    
                    # Fallback: if no structured content was found, get all text
                    if len(elements) <= 3:  # Only title and metadata
                        text = soup.get_text()
                        if text.strip():
                            # Escape special characters
                            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                            paragraphs = text.split('\n')
                            for para in paragraphs:
                                para = para.strip()
                                if para:
                                    try:
                                        elements.append(Paragraph(para, normal_style))
                                        elements.append(Spacer(1, 0.05*inch))
                                    except Exception as e:
                                        print(f"[PDF] Error with fallback paragraph: {e}")
                else:
                    elements.append(Paragraph("(Empty note)", normal_style))
                
                # Build PDF
                doc.build(elements)
                buffer.seek(0)
                
                # Write to file
                with open(pdf_path, 'wb') as f:
                    f.write(buffer.read())
                
                return True
                
            except Exception as e:
                print(f"[PDF EXPORT] Error creating PDF for note {note.id}: {e}")
                return False
        
        # Helper function to create a PDF for a board
        def create_board_pdf(board, folder_path):
            """Create a PDF for a MioDraw (whiteboard)"""
            try:
                pdf_filename = sanitize_filename(f"{board.title}_MioDraw.pdf")
                pdf_path = os.path.join(folder_path, pdf_filename)
                
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter,
                                       rightMargin=72, leftMargin=72,
                                       topMargin=72, bottomMargin=72)
                
                elements = []
                
                # Add title
                elements.append(Paragraph(board.title, title_style))
                elements.append(Spacer(1, 0.2*inch))
                
                # Add metadata
                meta_text = f"Type: MioDraw (Whiteboard) | Created: {board.created_at.strftime('%Y-%m-%d %H:%M')}"
                elements.append(Paragraph(meta_text, ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, textColor=colors.grey)))
                elements.append(Spacer(1, 0.3*inch))
                
                # Try to extract information from board content (JSON)
                if board.content:
                    try:
                        board_data = json.loads(board.content)
                        
                        # Display board info
                        elements.append(Paragraph("MioDraw Content Summary:", heading_style))
                        elements.append(Spacer(1, 0.1*inch))
                        
                        # Extract text elements if available
                        if isinstance(board_data, dict):
                            # Check for common whiteboard data structures
                            if 'objects' in board_data:
                                objects = board_data['objects']
                                elements.append(Paragraph(f"Total elements: {len(objects)}", normal_style))
                                
                                # Extract text from objects
                                text_items = []
                                for obj in objects:
                                    if isinstance(obj, dict):
                                        if obj.get('type') == 'text' or 'text' in obj:
                                            text_content = obj.get('text', obj.get('content', ''))
                                            if text_content:
                                                text_items.append(text_content)
                                
                                if text_items:
                                    elements.append(Spacer(1, 0.2*inch))
                                    elements.append(Paragraph("Text Content:", heading_style))
                                    for text in text_items:
                                        elements.append(Paragraph(f"• {text}", normal_style))
                                        elements.append(Spacer(1, 0.05*inch))
                                else:
                                    elements.append(Paragraph("This MioDraw contains visual elements (shapes, drawings, etc.) that cannot be fully represented in PDF format.", normal_style))
                            else:
                                elements.append(Paragraph("This MioDraw contains visual whiteboard content that cannot be fully represented in PDF format.", normal_style))
                        else:
                            elements.append(Paragraph("This MioDraw contains visual whiteboard content.", normal_style))
                        
                    except json.JSONDecodeError:
                        elements.append(Paragraph("This MioDraw contains visual whiteboard content.", normal_style))
                else:
                    elements.append(Paragraph("(Empty MioDraw)", normal_style))
                
                # Build PDF
                doc.build(elements)
                buffer.seek(0)
                
                # Write to file
                with open(pdf_path, 'wb') as f:
                    f.write(buffer.read())
                
                return True
                
            except Exception as e:
                print(f"[PDF EXPORT] Error creating PDF for board {board.id}: {e}")
                return False
        
        # Recursive function to process folders and create PDFs
        def process_folder(folder, parent_path):
            """Recursively process folder and create PDFs for all content"""
            # Create folder directory
            folder_name = sanitize_filename(folder.name)
            folder_path = os.path.join(parent_path, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            
            # Process all notes in this folder
            notes = Note.query.filter_by(folder_id=folder.id, user_id=user_id).all()
            for note in notes:
                create_note_pdf(note, folder_path)
            
            # Process all boards in this folder
            boards = Board.query.filter_by(folder_id=folder.id, user_id=user_id).all()
            for board in boards:
                create_board_pdf(board, folder_path)
            
            # Process subfolders recursively
            subfolders = Folder.query.filter_by(parent_id=folder.id, user_id=user_id).all()
            for subfolder in subfolders:
                process_folder(subfolder, folder_path)
        
        # Start processing from the root folder
        root_path = os.path.join(temp_dir, sanitize_filename(start_folder.name))
        os.makedirs(root_path, exist_ok=True)
        process_folder(start_folder, temp_dir)
        
        # Create ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Walk through the temp directory and add all files
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Calculate the archive name (relative path)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        # Clean up temp directory
        shutil.rmtree(temp_dir)
        
        # Generate filename
        zip_filename = f"{username}_{start_folder.name}_PDFs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        flash(f"PDF export complete! Downloaded as ZIP with folder structure maintained.", "success")
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=zip_filename
        )
    
    except Exception as e:
        print(f"[PDF EXPORT] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up temp directory in case of error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        
        flash(f"Error creating PDF export: {str(e)}", "danger")
        return redirect(url_for("folders.view_folder", folder_id=current_folder_id))

