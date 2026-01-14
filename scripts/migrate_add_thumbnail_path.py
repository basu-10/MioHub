"""
Migration to add thumbnail_path column to files table for caching whiteboard previews.
Run this once to add the column.
"""

import os

# Set environment file to prod.env before importing config
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

from flask import Flask
from extensions import db
from sqlalchemy import text
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    inspector = db.inspect(db.engine)
    
    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns('files')]
    
    if 'thumbnail_path' not in columns:
        print("[MIGRATION] Adding thumbnail_path column to files table...")
        db.session.execute(text("""
            ALTER TABLE files 
            ADD COLUMN thumbnail_path VARCHAR(500) NULL
            COMMENT 'Cached thumbnail path for visual content (whiteboards, diagrams, etc.)'
        """))
        db.session.commit()
        print("[MIGRATION] ✓ thumbnail_path column added successfully")
    else:
        print("[MIGRATION] thumbnail_path column already exists, skipping")

print("[MIGRATION] Migration complete!")
