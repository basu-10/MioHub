import os
import hashlib
from PIL import Image
import json
from flask import request, jsonify,  session
import base64
import uuid
import mimetypes

from . import p2_blueprint
from calculator import Calculator
from extensions import db


from values_main import UPLOAD_FOLDER, ALLOWED_EXTENSIONS

def format_bytes(bytes_size):
    """Format byte size into human-readable string.
    
    Args:
        bytes_size: Size in bytes (int)
        
    Returns:
        Formatted string like "2.5 KB", "15.3 MB", etc.
    """
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"

def get_image_hash(filepath):
    """Generate SHA256 hash of image file content."""
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def get_existing_image_by_hash(user_id, image_hash):
    """Check if an image with this hash already exists for the user."""
    extensions = ['.webp', '.jpg', '.jpeg', '.png', '.gif']
    for ext in extensions:
        pattern = f"{user_id}_{image_hash}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, pattern)
        if os.path.exists(filepath):
            return f"/static/uploads/images/{pattern}"
    return None


def collect_images_from_content(content, image_set):
    """
    Extract image filenames from HTML or JSON content and add to image_set.
    
    Handles:
    - HTML: Scans <img> tags for src attributes
    - JSON strings: Searches for image paths in JSON structure
    - Plain text: Regex pattern matching for image paths
    
    Returns content unchanged
    """
    import re
    from bs4 import BeautifulSoup
    
    if not content:
        return content
    
    # Try to parse as HTML first
    if isinstance(content, str) and ('<img' in content or '<IMG' in content):
        try:
            soup = BeautifulSoup(content, 'html.parser')
            images = soup.find_all('img')
            for img in images:
                src = img.get('src', '')
                if src and isinstance(src, str):
                    if any(prefix in src for prefix in ['/static/uploads/images/', 'static/uploads/images/', '/uploads/images/', 'uploads/images/']):
                        filename = src.split('/')[-1]
                        if filename:
                            image_set.add(filename)
        except Exception as e:
            print(f"[COLLECT_IMAGES] HTML parsing failed: {e}")
    
    # Always do regex pattern matching for image paths (works for JSON and plain text)
    # Pattern matches: /static/uploads/images/filename.webp or similar variants
    pattern = r'(?:/?static/)?(?:/?uploads/)?images/([a-zA-Z0-9_\-]+\.(?:webp|jpg|jpeg|png|gif))'
    
    if isinstance(content, str):
        matches = re.findall(pattern, content)
        for filename in matches:
            if filename:
                image_set.add(filename)
    
    return content


def save_data_uri_images_in_json(json_obj, user_id):
    """
    Find data:image URIs in JSON objects (e.g., whiteboard content) and save them to disk.
    Returns (updated_json_obj, bytes_added)
    """
    import copy
    if not json_obj:
        return json_obj, 0
    
    # Make a deep copy to avoid modifying original
    updated_obj = copy.deepcopy(json_obj)
    total_added = 0
    
    def process_value(val):
        nonlocal total_added
        if isinstance(val, str) and val.startswith('data:image/'):
            # Process data URI
            try:
                header, b64data = val.split(',', 1)
                mime = header.split(';')[0].split(':')[1] if ';' in header else header.split(':')[1]
                ext = mimetypes.guess_extension(mime) or '.png'
                tmp_name = f"tmp_{uuid.uuid4().hex}{ext}"
                tmp_path = os.path.join(UPLOAD_FOLDER, tmp_name)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                
                # Write temp file
                with open(tmp_path, 'wb') as f:
                    f.write(base64.b64decode(b64data))
                
                # Compute hash and check for existing
                try:
                    image_hash = get_image_hash(tmp_path)
                except Exception:
                    image_hash = None
                
                if image_hash:
                    existing_url = get_existing_image_by_hash(user_id, image_hash)
                    if existing_url:
                        print(f"DEBUG: save_data_uri_images_in_json - existing image for user {user_id} -> {existing_url}")
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        return existing_url
                    dest_filename = f"{user_id}_{image_hash}.webp"
                    dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)
                else:
                    dest_filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
                    dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)
                
                # Convert to webp
                try:
                    converted = convert_to_webp(tmp_path, dest_path)
                    if os.path.exists(converted):
                        added = os.path.getsize(converted)
                        total_added += added
                        print(f"DEBUG: save_data_uri_images_in_json - saved image for user {user_id} at {converted} ({added} bytes)")
                        url = f"/static/uploads/images/{os.path.basename(converted)}"
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                        return url
                except Exception as e:
                    print(f"ERROR: save_data_uri_images_in_json - conversion failed: {e}")
                
                # Cleanup temp file on failure
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
            except Exception as e:
                print(f"ERROR: save_data_uri_images_in_json - processing failed: {e}")
        return val
    
    def traverse(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith('data:image/'):
                    obj[key] = process_value(value)
                elif isinstance(value, (dict, list)):
                    traverse(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.startswith('data:image/'):
                    obj[i] = process_value(item)
                elif isinstance(item, (dict, list)):
                    traverse(item)
    
    traverse(updated_obj)
    return updated_obj, total_added


def save_data_uri_images_for_user(content, user_id):
    """
    Find <img src="data:image/...;base64,..."> in content, decode and save them to UPLOAD_FOLDER
    using the SHA256 hash as the filename. Returns (updated_content, bytes_added).
    """
    from bs4 import BeautifulSoup
    import shutil
    if not content:
        return content, 0
    soup = BeautifulSoup(content, 'html.parser')
    total_added = 0
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if not src or not isinstance(src, str) or not src.startswith('data:image/'):
            continue
        try:
            header, b64data = src.split(',', 1)
            # Get mime type and extension
            mime = header.split(';')[0].split(':')[1] if ';' in header else header.split(':')[1]
            ext = mimetypes.guess_extension(mime) or '.png'
            tmp_name = f"tmp_{uuid.uuid4().hex}{ext}"
            tmp_path = os.path.join(UPLOAD_FOLDER, tmp_name)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            # Write temp file
            with open(tmp_path, 'wb') as f:
                f.write(base64.b64decode(b64data))

            # Compute hash and find existing image
            try:
                image_hash = get_image_hash(tmp_path)
            except Exception:
                image_hash = None

            if image_hash:
                existing_url = get_existing_image_by_hash(user_id, image_hash)
                if existing_url:
                    print(f"DEBUG: save_data_uri_images_for_user - existing image for user {user_id} hash {image_hash} -> {existing_url}")
                    # Use existing and remove temp
                    img['src'] = existing_url
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue
                dest_filename = f"{user_id}_{image_hash}.webp"
                dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)
            else:
                # No hash - fallback to write with random name
                dest_filename = f"{user_id}_{uuid.uuid4().hex}{ext}"
                dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)

            # Convert to webp and replace src
            try:
                converted = convert_to_webp(tmp_path, dest_path)
                if os.path.exists(converted):
                    added = os.path.getsize(converted)
                    total_added += added
                    print(f"DEBUG: save_data_uri_images_for_user - saved image for user {user_id} at {converted} ({added} bytes)")
                    img['src'] = f"/static/uploads/images/{os.path.basename(converted)}"
                else:
                    # If conversion failed, keep original and remove tmp
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue
            except Exception:
                try:
                    # fallback copy
                    shutil.copy2(tmp_path, dest_path)
                    if os.path.exists(dest_path):
                        added = os.path.getsize(dest_path)
                        total_added += added
                        img['src'] = f"/static/uploads/images/{os.path.basename(dest_path)}"
                        print(f"DEBUG: save_data_uri_images_for_user - fallback saved image for user {user_id} at {dest_path} ({added} bytes)")
                except Exception:
                    pass
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
        except Exception:
            # If anything went wrong processing this image, ensure tmp_path is removed and continue
            try:
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            continue
    # end for img

    return str(soup), total_added


def copy_images_to_user(image_filenames, receiver_user_id):
    """
    Copy an iterable of image filenames found in content to the receiver's upload directory.
    Returns tuple: (mapping_old_to_new_filename, total_bytes_added)
    The function respects existing images for the receiver (checks by hash via get_existing_image_by_hash).
    """
    import os, shutil
    mapping = {}
    total_added = 0
    for filename in set(image_filenames or []):
        if not filename:
            continue
        src1 = os.path.normpath(os.path.join('static', 'uploads', 'images', filename))
        src2 = os.path.join(UPLOAD_FOLDER, filename)
        src = src1 if os.path.exists(src1) else (src2 if os.path.exists(src2) else None)
        if not src:
            # File not found - skip
            continue
        print(f"DEBUG: copy_images_to_user - found source for {filename}: {src}")
        try:
            # Compute hash
            image_hash = get_image_hash(src)
        except Exception:
            print(f"DEBUG: copy_images_to_user - could not compute hash for {src}")
            # If we can't compute hash, fallback to file copy using original filename
            # but to avoid collisions, prefix with receiver id
            new_filename = f"{receiver_user_id}_{filename}"
            dest_path = os.path.join(UPLOAD_FOLDER, new_filename)
            if not os.path.exists(dest_path):
                shutil.copy2(src, dest_path)
                added = os.path.getsize(dest_path)
                mapping[filename] = new_filename
                total_added += added
            else:
                mapping[filename] = new_filename
            continue

        # Check if receiver already has this image by hash
        existing = get_existing_image_by_hash(receiver_user_id, image_hash)
        if existing:
            # Extract filename from URL and map; no new size added
            existing_filename = existing.split('/')[-1]
            print(f"DEBUG: copy_images_to_user - receiver {receiver_user_id} already has image hash {image_hash} -> {existing_filename}")
            mapping[filename] = existing_filename
            continue

        # Not found - create a receiver-specific filename and try to convert to webp if needed
        _, ext = os.path.splitext(filename)
        dest_filename = f"{receiver_user_id}_{image_hash}.webp"
        dest_path = os.path.join(UPLOAD_FOLDER, dest_filename)
        if os.path.exists(dest_path):
            mapping[filename] = dest_filename
            continue

        try:
            # Use convert_to_webp to standardize
            temp_dest = convert_to_webp(src, dest_path)
            if os.path.exists(temp_dest):
                added_size = os.path.getsize(temp_dest)
                mapping[filename] = os.path.basename(temp_dest)
                total_added += added_size
                print(f"DEBUG: copy_images_to_user - converted {src} -> {temp_dest} ({added_size} bytes)")
                continue
        except Exception:
            print(f"DEBUG: copy_images_to_user - convert_to_webp failed for {src}, trying fallback copy to {dest_path}")
            # Fallback copy
            try:
                shutil.copy2(src, dest_path)
                if os.path.exists(dest_path):
                    added_size = os.path.getsize(dest_path)
                    mapping[filename] = os.path.basename(dest_path)
                    total_added += added_size
                    print(f"DEBUG: copy_images_to_user - fallback copy {src} -> {dest_path} ({added_size} bytes)")
            except Exception:
                # Unable to copy - skip and do not add size
                print(f"DEBUG: copy_images_to_user - failed to copy {src} -> {dest_path}")
                continue

    return mapping, total_added


def calculate_copy_size_for_item(item_type, original, recipient_id):
    """
    Calculate total bytes that will be added to recipient when copying the given item.
    Returns integer total bytes (content + images to be copied) and a detailed dict.
    """
    import os
    total = 0
    images = set()
    def content_size_for_text(text):
        return len(text.encode('utf-8')) if text else 0

    if item_type == 'note':
        html = getattr(original, 'content_html', None)
        if html is None:
            html = getattr(original, 'content', None)

        total += content_size_for_text(html)
        collect_images_from_content(html or '', images)

        # Description may live on metadata_json (File) or as direct attribute
        if getattr(original, 'metadata_json', None) and isinstance(original.metadata_json, dict):
            desc = original.metadata_json.get('description', '')
            if desc:
                collect_images_from_content(desc, images)
        elif getattr(original, 'description', None):
            collect_images_from_content(original.description or '', images)
    elif item_type == 'board':
        # Boards use content_json
        total += len(str(original.content_json or '').encode('utf-8'))
        # Board content_json doesn't contain HTML/images usually
        # Description is in metadata_json
        if original.metadata_json and isinstance(original.metadata_json, dict):
            desc = original.metadata_json.get('description', '')
            if desc:
                collect_images_from_content(desc, images)
    elif item_type == 'folder':
        def rec(f):
            nonlocal total
            # Include folder description in size calculation
            if getattr(f, 'description', None):
                total += content_size_for_text(f.description)
                collect_images_from_content(f.description or '', images)
            
            # Process ALL files in folder (not just notes and boards)
            for file_obj in f.files:
                if getattr(file_obj, 'content_text', None):
                    total += content_size_for_text(file_obj.content_text)
                    collect_images_from_content(file_obj.content_text or '', images)
                if getattr(file_obj, 'content_html', None):
                    total += content_size_for_text(file_obj.content_html)
                    collect_images_from_content(file_obj.content_html or '', images)
                if getattr(file_obj, 'content_json', None):
                    try:
                        json_str = json.dumps(file_obj.content_json)
                    except Exception:
                        json_str = str(file_obj.content_json)
                    total += len(json_str.encode('utf-8'))
                    collect_images_from_content(json_str, images)
                if getattr(file_obj, 'content_blob', None):
                    total += len(file_obj.content_blob)
                if file_obj.metadata_json and isinstance(file_obj.metadata_json, dict):
                    desc = file_obj.metadata_json.get('description', '')
                    if desc:
                        total += content_size_for_text(desc)
                        collect_images_from_content(desc, images)
            
            # Recurse into subfolders
            for child in f.children:
                rec(child)
        rec(original)
    elif item_type == 'file':
        # Generic file handler (markdown, todo, diagrams, etc.)
        if getattr(original, 'content_text', None):
            total += content_size_for_text(original.content_text)
            collect_images_from_content(original.content_text or '', images)
        if getattr(original, 'content_html', None):
            total += content_size_for_text(original.content_html)
            collect_images_from_content(original.content_html or '', images)
        if getattr(original, 'content_json', None):
            try:
                json_str = json.dumps(original.content_json)
            except Exception:
                json_str = str(original.content_json)
            total += len(json_str.encode('utf-8'))
            collect_images_from_content(json_str, images)
        if getattr(original, 'content_blob', None):
            total += len(original.content_blob)
        if getattr(original, 'metadata_json', None) and isinstance(original.metadata_json, dict):
            desc = original.metadata_json.get('description', '')
            if desc:
                total += content_size_for_text(desc)
                collect_images_from_content(desc, images)
    # Calculate unique image sizes that recipient doesn't already have
    seen_hashes = set()
    image_total = 0
    for img_filename in images:
        possible_paths = [os.path.join(UPLOAD_FOLDER, img_filename), os.path.normpath(os.path.join('static', 'uploads', 'images', img_filename))]
        path = None
        for p in possible_paths:
            if os.path.exists(p):
                path = p
                break
        if not path:
            continue
        try:
            h = get_image_hash(path)
        except Exception:
            try:
                image_total += os.path.getsize(path)
            except Exception:
                pass
            continue
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        if get_existing_image_by_hash(recipient_id, h):
            continue
        try:
            image_total += os.path.getsize(path)
        except Exception:
            pass
    return total + image_total, { 'content_bytes': total, 'image_bytes': image_total, 'images_count': len(images) }

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def convert_to_webp(input_path, output_path, max_width=1200, quality=85):
    """
    Convert any image format to WebP with optimization
    """
    try:
        with Image.open(input_path) as img:
            # Convert to RGB if necessary (WebP supports RGBA but we'll standardize)
            if img.mode in ('RGBA', 'LA'):
                # Keep transparency for WebP
                pass
            elif img.mode in ('P', 'L', '1'):
                img = img.convert('RGBA')
            elif img.mode not in ('RGB', 'RGBA'):
                img = img.convert('RGB')

            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Save as WebP
            img.save(output_path, 'WebP', quality=quality, optimize=True)
            return output_path

    except Exception as e:
        print(f"Error converting to WebP: {e}")
        # If WebP conversion fails, try to save as JPEG
        try:
            with Image.open(input_path) as img:
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                # Change extension to .jpg
                jpg_path = output_path.replace('.webp', '.jpg')
                img.save(jpg_path, 'JPEG', quality=quality, optimize=True)
                return jpg_path
        except Exception as e2:
            print(f"Error converting to JPEG as fallback: {e2}")
            # If all fails, copy original with correct extension
            if input_path != output_path:
                try:
                    import shutil
                    # Get original extension
                    _, ext = os.path.splitext(input_path)
                    correct_path = output_path.replace('.webp', ext.lower())
                    shutil.copy2(input_path, correct_path)
                    return correct_path
                except Exception as e3:
                    print(f"Error copying original file: {e3}")
    return output_path


#############################
# AI INLINE HELPERS
#############################


from flask import Flask, request, jsonify
import config
import os
from providers import LLMClient

llm = LLMClient()

# All formatting decisions are here (server-side), not in JS.
DELIMITER = config.AI_DELIMITER
MAX_INPUT_CHARS = config.MAX_INPUT_CHARS

SYSTEM_BASE = "You are a helpful assistant. Be concise, correct, and actionable."

PROMPTS = {
    "explain": (
        "Explain the following selection in simple, exact terms. "
        "Use 5–8 short bullet points. If it is code, add brief inline comments.\n\n"
        "---\n{TEXT}\n---"
    ),
    "eval": (
        "If the selection is math/code, compute or evaluate the result step by step. "
        "If it isn't evaluable, say so briefly.\n\nSelection:\n{TEXT}"
    ),
}

@p2_blueprint.post("/api/ai_inline")
def ai_inline():
    data = request.get_json(force=True)
    action = (data.get("action") or "explain").lower()
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify(error="No text provided."), 400

    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]

    user_prompt = PROMPTS.get(action, PROMPTS["explain"]).replace("{TEXT}", text)
    messages = [
        {"role": "system", "content": SYSTEM_BASE},
        {"role": "user", "content": user_prompt}
    ]

    try:
        result_text = llm.chat(messages, temperature=0.2, max_tokens=512) or ""
        combined = f"{text}{DELIMITER}{result_text}"
        return jsonify(combined=combined)
    except Exception as e:
        # Server decides error string; client just pastes it if you want (or we can 500).
        return jsonify(error=f"AI error: {str(e)}"), 500



######################
# whiteboard import/export helpers
######################

def import_board_json(json_content, target_folder):
    """
    Import board from JSON content
    """
    print(f"DEBUG: import_board_json called for folder: {target_folder.name}")

    try:
        board_data = json.loads(json_content)
        print(f"DEBUG: JSON parsed successfully")
        print(f"DEBUG: Board data keys: {list(board_data.keys())}")

        title = board_data.get('title', 'Untitled Board')
        content = board_data.get('content', '')

        print(f"DEBUG: Board title: '{title}'")
        print(f"DEBUG: Board content length: {len(content)}")

        # Create board
        board = Board(
            title=title,
            content=content,
            user_id=current_user.id,
            folder_id=target_folder.id
        )

        print(f"DEBUG: Board object created")

        try:
            db.session.add(board)
            db.session.flush()
            print(f"DEBUG: Board added to session, ID: {board.id}")
        except Exception as e:
            print(f"DEBUG: ERROR adding board to session: {e}")
            raise

        return title

    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"DEBUG: ERROR in import_board_json: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return None











@p2_blueprint.route('/eval_expression', methods=['POST'])
@p2_blueprint.route("/calculate", methods=["POST"])
def calculate():
    session.permanent = True  # Ensure persistence
    data = request.get_json()
    expr = data.get("expression", "")

    if not expr.strip():
        return jsonify({"error": "No expression provided"}), 400

    original_expr = expr.strip()

    # Check if input contains multiple lines
    if '\n' in original_expr:
        # Handle multi-line expressions
        lines = [line.strip() for line in original_expr.split('\n') if line.strip()]
        results = []
        all_successful = True

        for line in lines:
            # Handle trailing "=" for each line
            if line.endswith('='):
                line_to_evaluate = line[:-1].strip()
                has_trailing_equals = True
            else:
                line_to_evaluate = line
                has_trailing_equals = False

            calc = Calculator(expression=line_to_evaluate)
            result = calc.evaluate()

            if result == "Error":
                all_successful = False
                results.append(f"{line} → Error")
            else:
                # Format each line result without HTML tags for now
                if has_trailing_equals:
                    results.append(f"{line_to_evaluate} = {result}")
                else:
                    results.append(f"{line_to_evaluate} = {result}")

        if not all_successful:
            return jsonify({"error": "One or more expressions failed to evaluate"}), 400

        # Reverse the order to maintain original line order (results were processed in forward order)
        #results.reverse()
        # Join with newlines for plain text formatting, then convert to HTML paragraphs
        formatted_result = '\n'.join(results)
        # Convert each line to a paragraph for rich text editor display
        lines = formatted_result.split('\n')
        formatted_result = ''.join([f'<p>{line}</p>' for line in lines if line.strip()])

        # Store history for multi-line (store as single entry with all results)
        history = session.get("history", [])
        history.append({"expression": original_expr, "result": formatted_result})

        # Limit history size to prevent cookie overflow
        if len(history) > 50:
            history = history[-50:]

        session["history"] = history
        return jsonify({"result": formatted_result})

    else:
        # Handle single line expression (original logic)
        if original_expr.endswith('='):
            expr_to_evaluate = original_expr[:-1].strip()  # Remove the trailing "="
            has_trailing_equals = True
        else:
            expr_to_evaluate = original_expr
            has_trailing_equals = False

        calc = Calculator(expression=expr_to_evaluate)
        result = calc.evaluate()

        # Check if evaluation failed
        if result == "Error":
            return jsonify({"error": "Invalid expression or calculation error"}), 400

        # Format the response based on whether there was already a trailing "="
        if has_trailing_equals:
            # If input was "5+6=", return just the result "11"
            # so frontend shows "5+6= = 11" -> "5+6=11"
            formatted_result =  f"{expr_to_evaluate} = {result}"
        else:
            # If input was "5+6", return "5+6 = 11" format
            formatted_result = f"{expr_to_evaluate} = {result}"

        # Store history only for successful calculations
        history = session.get("history", [])
        history.append({"expression": original_expr, "result": result})

        # Limit history size to prevent cookie overflow
        if len(history) > 50:  # Keep only last 50 calculations
            history = history[-50:]

        session["history"] = history
        return jsonify({"result": formatted_result})


def cleanup_orphaned_images_for_user(user_id, deleted_content=None):
    """
    Delete image files that are no longer referenced in any user's notes or boards.
    This should be called after deleting notes/boards to clean up unused images.
    
    Args:
        user_id: The user ID whose images to check
        deleted_content: Optional - the content that was just deleted (for optimization)
    
    Returns:
        Tuple of (deleted_count, freed_bytes)
    """
    from blueprints.p2.models import File, User
    
    # Collect all image filenames currently in use by this user
    used_filenames = set()
    
    # Check all remaining notes
    for note in File.query.filter_by(owner_id=user_id, type='note').all():
        if note.content_html:
            collect_images_from_content(note.content_html, used_filenames)
        if note.metadata_json and isinstance(note.metadata_json, dict):
            desc = note.metadata_json.get('description', '')
            if desc:
                collect_images_from_content(desc, used_filenames)
    
    # Check all remaining boards - metadata_json descriptions might have images
    for board in File.query.filter_by(owner_id=user_id, type='whiteboard').all():
        if board.metadata_json and isinstance(board.metadata_json, dict):
            desc = board.metadata_json.get('description', '')
            if desc:
                collect_images_from_content(desc, used_filenames)
    
    # Find all image files belonging to this user
    deleted_count = 0
    freed_bytes = 0
    
    try:
        for fname in os.listdir(UPLOAD_FOLDER):
            if not fname.startswith(f"{user_id}_"):
                continue
            
            # Skip if this image is still in use
            if fname in used_filenames:
                continue
            
            # Delete the orphaned image
            file_path = os.path.join(UPLOAD_FOLDER, fname)
            if os.path.exists(file_path):
                try:
                    size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deleted_count += 1
                    freed_bytes += size
                    print(f"[CLEANUP] Deleted orphaned image: {fname} ({size} bytes)")
                except Exception as e:
                    print(f"[CLEANUP] Failed to delete {fname}: {e}")
    except Exception as e:
        print(f"[CLEANUP] Error during image cleanup for user {user_id}: {e}")
    
    # Update user's total_data_size if we freed any space
    if freed_bytes > 0:
        try:
            user = User.query.get(user_id)
            if user:
                user.total_data_size = max(0, (user.total_data_size or 0) - freed_bytes)
                db.session.commit()
                print(f"[CLEANUP] Updated user {user_id} data size: freed {freed_bytes} bytes")
        except Exception as e:
            print(f"[CLEANUP] Failed to update user data size: {e}")
    
    return (deleted_count, freed_bytes)


def add_notification(user_id, message, notification_type='info'):
    """Add a notification for a user and maintain the last 50 notifications.
    
    Args:
        user_id: ID of the user to notify
        message: Notification message text (max 500 chars)
        notification_type: Type of notification ('save', 'transfer', 'delete', 'error', 'info', etc.)
    
    Returns:
        The created Notification object, or None if failed
    """
    from blueprints.p2.models import Notification
    from datetime import datetime
    
    try:
        # Create new notification
        notification = Notification(
            user_id=user_id,
            message=message[:500],  # Enforce max length
            type=notification_type,
            timestamp=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.flush()  # Get the ID without committing
        
        # Get count of notifications for this user
        notification_count = Notification.query.filter_by(user_id=user_id).count()
        
        # If more than 50, delete the oldest ones
        if notification_count > 50:
            # Get IDs of oldest notifications to delete
            notifications_to_delete = (
                Notification.query
                .filter_by(user_id=user_id)
                .order_by(Notification.timestamp.asc())
                .limit(notification_count - 50)
                .all()
            )
            
            for old_notification in notifications_to_delete:
                db.session.delete(old_notification)
        
        db.session.commit()
        return notification
        
    except Exception as e:
        db.session.rollback()
        print(f"[NOTIFICATION] Error adding notification for user {user_id}: {e}")
        return None


def notify_user(user_id, message, notification_type='info'):
    """Add notification and return JSON response for AJAX/API endpoints.
    
    This is a convenience wrapper around add_notification that provides
    consistent error handling for API endpoints.
    
    Args:
        user_id: ID of the user to notify
        message: Notification message text
        notification_type: Type ('save', 'transfer', 'delete', 'error', 'info')
    
    Returns:
        tuple: (success: bool, notification: Notification or None)
    """
    try:
        notification = add_notification(user_id, message, notification_type)
        return (True, notification)
    except Exception as e:
        print(f"[NOTIFICATION] Failed to notify user {user_id}: {e}")
        return (False, None)


def generate_whiteboard_thumbnail(content_json, user_id, board_id, width=400, height=300):
    """
    Generate a PNG thumbnail for infinite whiteboard content.
    
    Server-side rendering using PIL (headless, efficient).
    Caches result to disk and returns relative path.
    
    Args:
        content_json: Whiteboard content dict with 'objects' array
        user_id: Owner user ID (for thumbnail path)
        board_id: Board file ID (for cache key)
        width: Thumbnail width in pixels (default 400)
        height: Thumbnail height in pixels (default 300)
    
    Returns:
        str: Relative path to thumbnail (/static/uploads/thumbnails/...),
             or None if generation fails
    """
    if not content_json or not isinstance(content_json, dict):
        print(f"[THUMBNAIL] Invalid content_json for board {board_id}")
        return None
    
    objects = content_json.get('objects', [])
    if not objects:
        print(f"[THUMBNAIL] No objects in board {board_id}, skipping thumbnail")
        return None
    
    try:
        from PIL import Image, ImageDraw
        import os
        
        # Create thumbnails directory (in static/uploads/thumbnails, not images folder)
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'static')
        thumbnail_dir = os.path.join(static_dir, 'uploads', 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        # Thumbnail filename: {user_id}_board_{board_id}.png
        thumbnail_filename = f"{user_id}_board_{board_id}.png"
        thumbnail_path_abs = os.path.join(thumbnail_dir, thumbnail_filename)
        
        # Calculate bounding box of all objects
        minX = float('inf')
        minY = float('inf')
        maxX = float('-inf')
        maxY = float('-inf')
        
        for obj in objects:
            obj_type = obj.get('type')
            
            if obj_type == 'stroke' and obj.get('path'):
                for pt in obj['path']:
                    if pt and 'x' in pt and 'y' in pt:
                        size = obj.get('size', 2) / 2
                        minX = min(minX, pt['x'] - size)
                        minY = min(minY, pt['y'] - size)
                        maxX = max(maxX, pt['x'] + size)
                        maxY = max(maxY, pt['y'] + size)
            
            elif obj_type == 'shape':
                x = obj.get('x', 0)
                y = obj.get('y', 0)
                w = obj.get('w', 0)
                h = obj.get('h', 0)
                stroke = obj.get('strokeWidth', 2) / 2
                minX = min(minX, x - stroke)
                minY = min(minY, y - stroke)
                maxX = max(maxX, x + w + stroke)
                maxY = max(maxY, y + h + stroke)
            
            elif obj_type == 'image':
                x = obj.get('x', 0)
                y = obj.get('y', 0)
                w = obj.get('w', obj.get('width', 0))
                h = obj.get('h', obj.get('height', 0))
                # Account for rotation (simple approximation)
                rotation = obj.get('rotation', 0)
                if abs(rotation) > 0.01:  # If rotated
                    # Enlarge bbox by diagonal
                    diagonal = (w**2 + h**2)**0.5
                    centerX = x + w/2
                    centerY = y + h/2
                    half_diag = diagonal / 2
                    minX = min(minX, centerX - half_diag)
                    minY = min(minY, centerY - half_diag)
                    maxX = max(maxX, centerX + half_diag)
                    maxY = max(maxY, centerY + half_diag)
                else:
                    minX = min(minX, x)
                    minY = min(minY, y)
                    maxX = max(maxX, x + w)
                    maxY = max(maxY, y + h)
            
            elif obj_type == 'text':
                x = obj.get('x', 0)
                y = obj.get('y', 0)
                fontSize = obj.get('fontSize', 16)
                text = obj.get('text', '')
                # Rough text size estimation (8px per char width, fontSize height)
                textWidth = len(text) * fontSize * 0.6
                minX = min(minX, x)
                minY = min(minY, y - fontSize)
                maxX = max(maxX, x + textWidth)
                maxY = max(maxY, y)
        
        # Handle empty/invalid bounds
        if not all(val != float('inf') and val != float('-inf') for val in [minX, minY, maxX, maxY]):
            print(f"[THUMBNAIL] Invalid bounds for board {board_id}")
            return None
        
        # Add padding
        padding = 50
        minX -= padding
        minY -= padding
        maxX += padding
        maxY += padding
        
        contentWidth = maxX - minX
        contentHeight = maxY - minY
        
        if contentWidth <= 0 or contentHeight <= 0:
            print(f"[THUMBNAIL] Invalid content dimensions for board {board_id}")
            return None
        
        # Calculate scale to fit thumbnail dimensions
        scale = min(width / contentWidth, height / contentHeight)
        
        # Create image with dark background (matching theme)
        img = Image.new('RGB', (width, height), color='#0a0a0b')
        draw = ImageDraw.Draw(img)
        
        # Draw objects (simplified rendering)
        for obj in objects:
            obj_type = obj.get('type')
            color = obj.get('color', '#14b8a6')
            
            # Convert hex color to RGB tuple
            try:
                if color.startswith('#'):
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    rgb_color = (r, g, b)
                else:
                    rgb_color = (20, 184, 166)  # Default teal
            except:
                rgb_color = (20, 184, 166)
            
            # Transform coordinates to thumbnail space
            def transform(x, y):
                tx = (x - minX) * scale
                ty = (y - minY) * scale
                return (tx, ty)
            
            if obj_type == 'stroke' and obj.get('path'):
                path = obj['path']
                if len(path) > 1:
                    points = [transform(pt['x'], pt['y']) for pt in path if pt and 'x' in pt and 'y' in pt]
                    if len(points) > 1:
                        line_width = max(1, int(obj.get('size', 2) * scale))
                        draw.line(points, fill=rgb_color, width=line_width)
            
            elif obj_type == 'shape':
                x1, y1 = transform(obj.get('x', 0), obj.get('y', 0))
                x2, y2 = transform(obj.get('x', 0) + obj.get('w', 0), 
                                   obj.get('y', 0) + obj.get('h', 0))
                if obj.get('filled'):
                    draw.rectangle([x1, y1, x2, y2], fill=rgb_color, outline=rgb_color, width=1)
                else:
                    line_width = max(1, int(obj.get('strokeWidth', 2) * scale))
                    draw.rectangle([x1, y1, x2, y2], outline=rgb_color, width=line_width)
            
            elif obj_type == 'image':
                # Draw placeholder rectangle for images (avoid loading actual images)
                x1, y1 = transform(obj.get('x', 0), obj.get('y', 0))
                w = obj.get('w', obj.get('width', 0)) * scale
                h = obj.get('h', obj.get('height', 0)) * scale
                x2, y2 = x1 + w, y1 + h
                draw.rectangle([x1, y1, x2, y2], outline=(100, 100, 100), width=1)
            
            elif obj_type == 'text':
                x, y = transform(obj.get('x', 0), obj.get('y', 0))
                # Draw small dot for text position (full text rendering is complex)
                draw.ellipse([x-2, y-2, x+2, y+2], fill=rgb_color)
        
        # Save thumbnail
        img.save(thumbnail_path_abs, 'PNG', optimize=True)
        print(f"[THUMBNAIL] Generated thumbnail for board {board_id}: {thumbnail_filename}")
        
        # Return relative path
        return f"/static/uploads/thumbnails/{thumbnail_filename}"
        
    except Exception as e:
        print(f"[THUMBNAIL] Error generating thumbnail for board {board_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_thumbnail_url(file_obj):
    """
    Get thumbnail URL for a file, with fallback to placeholder.
    
    Args:
        file_obj: File model instance
    
    Returns:
        str: URL to thumbnail or None if not available
    """
    if not file_obj:
        return None
    
    # Check if thumbnail_path exists and file exists on disk
    if hasattr(file_obj, 'thumbnail_path') and file_obj.thumbnail_path:
        # Check if file exists
        import os
        
        # Convert relative URL to absolute path
        if file_obj.thumbnail_path.startswith('/static/uploads/thumbnails/'):
            filename = file_obj.thumbnail_path.split('/')[-1]
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'static')
            abs_path = os.path.join(static_dir, 'uploads', 'thumbnails', filename)
            
            if os.path.exists(abs_path):
                return file_obj.thumbnail_path
    
    # Return None if no thumbnail (template will handle fallback UI)
    return None
