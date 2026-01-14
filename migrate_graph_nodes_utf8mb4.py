"""
Migration: Fix UTF-8mb4 charset for graph_nodes table to support emoji and special Unicode characters.

The title and summary columns need to use utf8mb4 charset to properly store 4-byte Unicode characters
like emoji (e.g., 🦞) that may be copied from web content.
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

def migrate():
    with app.app_context():
        inspector = db.inspect(db.engine)
        
        # Check if graph_nodes table exists
        if 'graph_nodes' not in inspector.get_table_names():
            print("⚠️  graph_nodes table not found. Nothing to migrate.")
            return
        
        print("🔧 Updating graph_nodes table to support UTF-8mb4 (emoji support)...")
        
        try:
            # Convert title column to VARCHAR with utf8mb4
            db.session.execute(text("""
                ALTER TABLE graph_nodes 
                MODIFY COLUMN title VARCHAR(255) 
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL
            """))
            print("✅ Updated graph_nodes.title to utf8mb4")
            
            # Convert summary column to TEXT with utf8mb4
            db.session.execute(text("""
                ALTER TABLE graph_nodes 
                MODIFY COLUMN summary TEXT 
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL
            """))
            print("✅ Updated graph_nodes.summary to utf8mb4")
            
            db.session.commit()
            print("✅ Migration completed successfully!")
            print("📝 Graph nodes can now store emoji and 4-byte Unicode characters.")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == '__main__':
    migrate()
