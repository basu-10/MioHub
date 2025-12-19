"""
Regenerate thumbnail for board 14 (has path but file might not exist)
"""
from flask import Flask
from extensions import db
from blueprints.p2.models import File
from blueprints.p2.utils import generate_whiteboard_thumbnail
from sqlalchemy.orm.attributes import flag_modified
import config
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    board = File.query.get(14)
    
    if board:
        print(f"[REGENERATE] Board {board.id} '{board.title}'")
        print(f"  Current thumbnail_path: {board.thumbnail_path}")
        
        # Check if file exists
        if board.thumbnail_path:
            full_path = os.path.join('static', 'uploads', 'thumbnails', board.thumbnail_path.split('/')[-1])
            print(f"  File exists: {os.path.exists(full_path)}")
        
        objects = board.content_json.get('objects', []) if board.content_json else []
        print(f"  Objects count: {len(objects)}")
        
        if objects:
            print(f"[GENERATE] Generating thumbnail...")
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
                else:
                    print(f"  ✗ Generation returned None")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[SKIP] No objects to render")
    else:
        print("[ERROR] Board 14 not found")
