import io
import logging
import math
import os
import re
import zipfile
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

import requests
from flask import flash, jsonify, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.attributes import flag_modified

from blueprints.p2.models import File
from blueprints.p2.utils import save_data_uri_images_for_user
from extensions import db
from utilities_main import check_guest_limit, update_user_data_size

from . import p5_blueprint
from .extension_api import (
    append_to_html_content,
    build_extension_description_entries,
    calculate_data_uri_bytes,
    find_or_create_extension_file,
    get_or_create_web_clippings_folder,
    merge_description_entries,
    normalize_description_entries,
    normalize_url,
)


def extract_preview(html_value):
    text = ''
    image = None
    if not html_value:
        return text, image

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_value, 'html.parser')
        first_img = soup.find('img')
        if first_img and first_img.get('src'):
            image = first_img.get('src')

        # If no <img> tag was found, fall back to common meta image tags
        if not image:
            og_image = soup.find('meta', attrs={'property': 'og:image'})
            if og_image and og_image.get('content'):
                image = og_image.get('content')

        # As a last resort, look for bare image URLs in the HTML/text
        if not image:
            image_match = re.search(r"https?://[^\s'\"]+\.(?:png|jpe?g|gif|webp)", html_value, re.IGNORECASE)
            if image_match:
                image = image_match.group(0)

        paragraphs = [el.get_text(' ', strip=True) for el in soup.find_all(['p', 'li', 'blockquote']) if el.get_text(strip=True)]
        text = ' '.join(paragraphs) if paragraphs else soup.get_text(' ', strip=True)
    except Exception:
        text = html_value

    text = (text or '').strip()
    if len(text) > 320:
        text = text[:320].rsplit(' ', 1)[0] + '…'
    return text, image


def extract_domain(url):
    if not url:
        return 'Saved via extension'
    try:
        parsed = urlparse(url)
        host = parsed.netloc.replace('www.', '') or parsed.hostname or ''
        return host or 'Saved via extension'
    except Exception:
        return 'Saved via extension'


@p5_blueprint.route('/extension-settings')
@login_required
def extension_settings():
    """Chrome Extension settings page for API token management."""
    response = make_response(
        render_template(
            'p5/extension_settings.html',
            now=datetime.utcnow(),
            server_url=request.host_url.rstrip('/'),
        )
    )
    # Prevent cached HTML from leaking a previous user's token after account switches
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@p5_blueprint.route('/extension-home')
@login_required
def extension_home():
    """Reading-style home for Chrome extension clippings."""

    def serialize_clip(clip):
        preview_text, preview_image = extract_preview(clip.content_html)
        description_entries = normalize_description_entries((clip.metadata_json or {}).get('description'))
        clip_count = (clip.metadata_json or {}).get('clip_count', 1)
        
        # Calculate reading time from full content, not just preview
        full_text = ''
        if clip.content_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(clip.content_html, 'html.parser')
                full_text = soup.get_text(' ', strip=True)
            except Exception:
                full_text = clip.content_html
        
        reading_minutes = max(1, math.ceil(len(full_text.split()) / 200)) if full_text else 1

        return {
            'id': clip.id,
            'title': clip.title or 'Untitled web clip',
            'domain': extract_domain(clip.source_url),
            'source_url': clip.source_url,
            'clip_count': clip_count,
            'created_at': clip.created_at,
            'last_modified': clip.last_modified,
            'preview_text': preview_text,
            'preview_image': preview_image,
            'description_entries': description_entries,
            'reading_minutes': reading_minutes,
            'is_public': clip.is_public,
            'owner_id': clip.owner_id,
        }

    # Ensure folder exists and fetch clippings
    folder = get_or_create_web_clippings_folder(current_user)
    db.session.commit()

    clippings = File.query.filter_by(
        owner_id=current_user.id,
        folder_id=folder.id,
        type='proprietary_note'
    ).order_by(File.last_modified.desc()).all()

    items = []
    total_clips = 0
    latest_ts = None

    for clip in clippings:
        serialized = serialize_clip(clip)
        items.append(serialized)
        total_clips += serialized['clip_count']

        last_ts = clip.last_modified or clip.created_at
        if last_ts and (latest_ts is None or last_ts > latest_ts):
            latest_ts = last_ts

    # Public explore feed (includes current user and others)
    explore_items = [
        serialize_clip(clip)
        for clip in File.query.filter(
            File.is_public.is_(True),
            File.type == 'proprietary_note'
        )
        .order_by(File.last_modified.desc())
        .limit(60)
        .all()
    ]

    domains = sorted({item['domain'] for item in items if item['domain']})

    stats = {
        'total_articles': len(items),
        'total_clips': total_clips,
        'last_updated': latest_ts,
    }

    return render_template(
        'p5/extension_home.html',
        folder=folder,
        clippings=items,
        explore_clippings=explore_items,
        domains=domains,
        stats=stats,
    )


@p5_blueprint.route('/save-clean-page', methods=['POST'])
@login_required
def save_clean_page_from_modal():
    """
    Proxy to extension API using user's session.
    This route uses r.jina.ai to fetch clean content (may fail for some sites with 451/403 errors).
    For better reliability, use the Chrome extension which fetches content directly from the browser.
    """
    payload = request.get_json(silent=True) or request.form or {}
    target_url = (payload.get('url') or '').strip()
    custom_title = (payload.get('title') or '').strip()

    logger.info(f"[CleanSave] URL={target_url}")

    if not target_url:
        logger.warning(f"[CleanSave] Missing URL")
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    if not target_url.startswith(('http://', 'https://')):
        target_url = f'https://{target_url}'

    try:
        fetch_url = f"https://r.jina.ai/{target_url}"

        def _fetch_once(url):
            return requests.get(url, timeout=20)

        resp = _fetch_once(fetch_url)
        if resp.status_code != 200 or not (resp.text or '').strip():
            # Retry with http prefix as a fallback for some sites
            logger.info(f"[CleanSave] Retry: status={resp.status_code} URL={target_url}")
            alt_url = f"https://r.jina.ai/http://{target_url.replace('https://', '').replace('http://', '')}"
            resp = _fetch_once(alt_url)

        if resp.status_code != 200:
            logger.error(f"[CleanSave] Fetch failed: status={resp.status_code} URL={target_url}")
            return jsonify({'success': False, 'error': 'Unable to fetch clean page (upstream error)'}), 400

        markdown_body = (resp.text or '').strip()
        if not markdown_body:
            logger.error(f"[CleanSave] Empty response: URL={target_url}")
            return jsonify({'success': False, 'error': 'Empty clean page response from readability service'}), 400

        normalized_url = normalize_url(target_url)
        folder = get_or_create_web_clippings_folder(current_user)
        db.session.commit()

        def extract_title_from_markdown(body: str) -> str:
            """Derive a readable title from common r.jina.ai markdown shapes."""
            link_pattern = re.compile(r'^\s*\[([^\]]+)\]\([^\)]+\)')
            title_pattern = re.compile(r'^\s*title\s*:\s*(.+)$', re.IGNORECASE)

            for line in body.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue

                # 1) Prefer markdown headings
                if stripped.startswith('#'):
                    heading = stripped.lstrip('#').strip()
                    if heading:
                        return heading

                # 2) Look for markdown link at top: [Title](url)
                link_match = link_pattern.match(stripped)
                if link_match:
                    candidate = link_match.group(1).strip()
                    if candidate:
                        return candidate

                # 3) Fallback to lines like `Title: Something`
                title_match = title_pattern.match(stripped)
                if title_match:
                    candidate = title_match.group(1).strip()
                    if candidate:
                        return candidate

                # 4) First non-empty, non-URL-ish line
                if not stripped.lower().startswith(('http://', 'https://')):
                    return stripped

            return ''

        resolved_title = custom_title or extract_title_from_markdown(markdown_body) or normalized_url

        new_html_content = ''
        bytes_added_from_images = 0
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        new_html_content += f'<p style="color: #999; font-size: 0.85em; margin-bottom: 10px;">📌 Saved clean page: {timestamp}</p>'

        content = markdown_body

        # Process any embedded data URI images
        image_pattern = r'!\[([^\]]*)\]\((data:image[^)]+)\)'
        for alt_text, data_uri in re.findall(image_pattern, content):
            estimated_size = calculate_data_uri_bytes(data_uri)
            if estimated_size > 0:
                if current_user.user_type == 'guest' and not check_guest_limit(current_user, estimated_size):
                    content = content.replace(f'![{alt_text}]({data_uri})', '[Image removed: quota exceeded]')
                    continue

                temp_html = f'<img src="{data_uri}" alt="{alt_text}" />'
                processed_html, img_bytes = save_data_uri_images_for_user(temp_html, current_user.id)

                if processed_html and img_bytes > 0:
                    bytes_added_from_images += img_bytes
                    img_match = re.search(r'src="([^"]+)"', processed_html)
                    if img_match:
                        new_img_path = img_match.group(1)
                        content = content.replace(data_uri, new_img_path)

        # Convert markdown to HTML
        try:
            import markdown

            html_content = markdown.markdown(
                content,
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            new_html_content += f'<div class="clean-page-content" style="max-width: 800px;">{html_content}</div>'
        except ImportError:
            lines = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').split('\n')
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

        target_file, is_new_file = find_or_create_extension_file(
            current_user,
            folder,
            normalized_url,
            resolved_title,
        )

        old_content_size = len(target_file.content_html.encode('utf-8')) if not is_new_file and target_file.content_html else 0

        if is_new_file:
            target_file.content_html = new_html_content
        else:
            target_file.content_html = append_to_html_content(target_file.content_html, new_html_content)
            target_file.last_modified = datetime.utcnow()

        if not target_file.metadata_json:
            target_file.metadata_json = {}
        clip_count = target_file.metadata_json.get('clip_count', 0) + 1
        target_file.metadata_json['clip_count'] = clip_count
        target_file.metadata_json['last_clip_at'] = datetime.utcnow().isoformat()

        existing_entries = normalize_description_entries(target_file.metadata_json.get('description'))
        extension_entries = build_extension_description_entries(normalized_url, save_source='web')
        target_file.metadata_json['description'] = merge_description_entries(existing_entries, extension_entries)

        if (
            not target_file.title
            or target_file.title == normalized_url
            or target_file.title.lower().startswith(('http://', 'https://'))
        ):
            target_file.title = resolved_title

        flag_modified(target_file, 'content_html')
        flag_modified(target_file, 'metadata_json')

        new_content_size = len(target_file.content_html.encode('utf-8'))
        content_size_delta = new_content_size - old_content_size

        if is_new_file:
            db.session.add(target_file)

        folder.last_modified = datetime.utcnow()
        db.session.commit()

        total_delta = content_size_delta + bytes_added_from_images
        if total_delta > 0:
            if current_user.user_type == 'guest' and not check_guest_limit(current_user, total_delta):
                db.session.rollback()
                return jsonify({'success': False, 'error': 'Storage quota exceeded'}), 403

            update_user_data_size(current_user, total_delta)

        # Serialize for UI updates
        preview_text, preview_image = extract_preview(target_file.content_html)
        
        # Calculate reading time from full content
        full_text = ''
        if target_file.content_html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(target_file.content_html, 'html.parser')
                full_text = soup.get_text(' ', strip=True)
            except Exception:
                full_text = target_file.content_html
        
        reading_minutes = max(1, math.ceil(len(full_text.split()) / 200)) if full_text else 1
        clip_payload = {
            'id': target_file.id,
            'title': target_file.title or 'Untitled web clip',
            'domain': extract_domain(target_file.source_url),
            'source_url': target_file.source_url,
            'clip_count': target_file.metadata_json.get('clip_count', 1) if target_file.metadata_json else 1,
            'created_at': target_file.created_at,
            'last_modified': target_file.last_modified,
            'preview_text': preview_text,
            'preview_image': preview_image,
            'description_entries': normalize_description_entries((target_file.metadata_json or {}).get('description')),
            'reading_minutes': reading_minutes,
            'is_public': target_file.is_public,
            'owner_id': target_file.owner_id,
        }

        logger.info(f"[CleanSave] Success: file_id={target_file.id} title={target_file.title[:50]}")

        if request.headers.get('HX-Request'):
            return render_template('p5/partials/clip_oob.html', clip=clip_payload)

        note_url = url_for('notes.edit_note', note_id=target_file.id)
        return jsonify({
            'success': True,
            'message': 'Clean page saved to LaterGram',
            'note_url': note_url,
            'file_id': target_file.id,
        })

    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(f"[CleanSave] DB error: {exc} URL={target_url}")
        return jsonify({'success': False, 'error': 'Database error'}), 500
    except Exception as exc:
        db.session.rollback()
        logger.error(f"[CleanSave] Error: {exc} URL={target_url}")
        return jsonify({'success': False, 'error': str(exc)}), 500


@p5_blueprint.route('/download-chrome-extension')
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
        return redirect(url_for('p5_bp.extension_settings'))
