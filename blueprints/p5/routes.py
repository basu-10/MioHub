import io
import math
import os
import zipfile
from datetime import datetime
from urllib.parse import urlparse

from flask import flash, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from blueprints.p2.models import File
from extensions import db

from . import p5_blueprint
from .extension_api import get_or_create_web_clippings_folder, normalize_description_entries


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

    def serialize_clip(clip):
        preview_text, preview_image = extract_preview(clip.content_html)
        description_entries = normalize_description_entries((clip.metadata_json or {}).get('description'))
        clip_count = (clip.metadata_json or {}).get('clip_count', 1)
        reading_minutes = max(1, math.ceil(len(preview_text.split()) / 200)) if preview_text else 1

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
