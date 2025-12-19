"""
Generate thumbnails for all infinite whiteboards that have content but no thumbnail
"""
from flask import Flask
from extensions import db
from blueprints.p2.models import File
from blueprints.p2.utils import generate_whiteboard_thumbnail
from sqlalchemy.orm.attributes import flag_modified
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    boards = File.query.filter_by(type='proprietary_infinite_whiteboard').all()
    
    print(f"\n[THUMBNAIL GENERATOR] Found {len(boards)} infinite whiteboards\n")
    
    generated = 0
    skipped = 0
    failed = 0
    
    for board in boards:
        # Skip if already has thumbnail
        if board.thumbnail_path and board.thumbnail_path.strip():
            print(f"[SKIP] Board {board.id} '{board.title}' already has thumbnail: {board.thumbnail_path}")
            skipped += 1
            continue
        
        # Skip if no content
        if not board.content_json:
            print(f"[SKIP] Board {board.id} '{board.title}' has no content_json")
            skipped += 1
            continue
        
        objects = board.content_json.get('objects', [])
        if not objects:
            print(f"[SKIP] Board {board.id} '{board.title}' has no objects ({len(objects)})")
            skipped += 1
            continue
        
        # Generate thumbnail
        print(f"[GENERATE] Board {board.id} '{board.title}' ({len(objects)} objects)...")
        try:
            thumbnail_path = generate_whiteboard_thumbnail(
                board.content_json,
                board.owner_id,
                board.id
            )
            
            if thumbnail_path:
                board.thumbnail_path = thumbnail_path
                flag_modified(board, 'thumbnail_path')
                db.session.commit()
                print(f"  ✓ Generated: {thumbnail_path}")
                generated += 1
            else:
                print(f"  ✗ Generation returned None")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
    
    print(f"\n[SUMMARY]")
    print(f"  Generated: {generated}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(boards)}")
