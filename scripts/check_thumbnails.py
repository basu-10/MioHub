"""
Quick diagnostic script to check thumbnail_path values for infinite whiteboards
"""
import os

# Set environment file to prod.env before importing config
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

from flask import Flask
from extensions import db
from blueprints.p2.models import File
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    boards = File.query.filter_by(type='proprietary_infinite_whiteboard').all()
    
    print(f"\n[DIAGNOSTIC] Found {len(boards)} infinite whiteboards:\n")
    
    for board in boards:
        print(f"ID: {board.id}")
        print(f"  Title: {board.title}")
        print(f"  Owner ID: {board.owner_id}")
        print(f"  Thumbnail Path: {repr(board.thumbnail_path)}")
        print(f"  Has content_json: {board.content_json is not None}")
        if board.content_json:
            objects = board.content_json.get('objects', [])
            print(f"  Objects count: {len(objects)}")
        print()
