"""Backfill script to recalc User.total_data_size from existing DB content and disk images.

Usage (PowerShell):
    python scripts/recalculate_total_data_size.py [--user-id 123] [--dry-run]

- Sums file content sizes per user using File.get_content_size().
- Adds sizes of uploaded images in UPLOAD_FOLDER whose filenames start with "<user_id>_".
- Writes the new total into User.total_data_size (unless --dry-run).
"""
import argparse
import os
import sys
from pathlib import Path
from flask import Flask

# Ensure project root is on sys.path so `config` and app modules can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from extensions import db
from values_main import UPLOAD_FOLDER
from blueprints.p2.models import User, File


def build_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def bytes_for_user_images(user_id: int) -> int:
    """Sum bytes of image files prefixed with the user id in UPLOAD_FOLDER."""
    if not os.path.isdir(UPLOAD_FOLDER):
        return 0
    prefix = f"{user_id}_"
    total = 0
    try:
        for name in os.listdir(UPLOAD_FOLDER):
            if not name.startswith(prefix):
                continue
            path = os.path.join(UPLOAD_FOLDER, name)
            if os.path.isfile(path):
                try:
                    total += os.path.getsize(path)
                except OSError:
                    # Ignore unreadable files
                    continue
    except OSError:
        return total
    return total


def bytes_for_user_files(user_id: int) -> int:
    """Sum bytes of file contents for a user via get_content_size()."""
    total = 0
    for f in File.query.filter_by(owner_id=user_id):
        try:
            total += f.get_content_size() or 0
        except Exception:
            # Skip corrupted rows but keep going
            continue
    return total


def recalc_user(user: User) -> dict:
    content_bytes = bytes_for_user_files(user.id)
    image_bytes = bytes_for_user_images(user.id)
    new_total = content_bytes + image_bytes
    return {
        'user_id': user.id,
        'username': user.username,
        'prev_total': int(user.total_data_size or 0),
        'content_bytes': content_bytes,
        'image_bytes': image_bytes,
        'new_total': new_total,
    }


def main():
    parser = argparse.ArgumentParser(description="Recalculate total_data_size for all users")
    parser.add_argument('--user-id', type=int, help='Recalculate a single user only')
    parser.add_argument('--dry-run', action='store_true', help='Do not write changes, just report')
    args = parser.parse_args()

    app = build_app()
    with app.app_context():
        query = User.query
        if args.user_id is not None:
            query = query.filter_by(id=args.user_id)
        users = query.all()
        print(f"Processing {len(users)} user(s)")

        updates = []
        for user in users:
            info = recalc_user(user)
            updates.append(info)
            print(
                f"user={info['user_id']} ({info['username']}): prev={info['prev_total']} "
                f"-> new={info['new_total']} (content={info['content_bytes']} image={info['image_bytes']})"
            )
            if not args.dry_run:
                user.total_data_size = info['new_total']

        if args.dry_run:
            print("Dry run complete; no changes committed.")
            return

        db.session.commit()
        print("Update complete.")


if __name__ == '__main__':
    main()
