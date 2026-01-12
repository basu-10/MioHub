"""
Migration: Add source_url column to files table for Chrome extension URL grouping.

This enables smart grouping of extension saves by source URL, reducing file proliferation.
"""

from flask import Flask
from extensions import db
from sqlalchemy import text, inspect
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def migrate():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Check if files table exists
        if 'files' not in inspector.get_table_names():
            print("❌ Files table does not exist. Run file model migration first.")
            return
        
        # Check if source_url column already exists
        columns = [col['name'] for col in inspector.get_columns('files')]
        
        if 'source_url' in columns:
            print("✅ source_url column already exists. No migration needed.")
            return
        
        print("Adding source_url column to files table...")
        
        try:
            # Add source_url column with index for fast lookups
            db.session.execute(text("""
                ALTER TABLE files 
                ADD COLUMN source_url VARCHAR(2048) NULL,
                ADD INDEX idx_files_source_url (source_url(255))
            """))
            
            db.session.commit()
            print("✅ Successfully added source_url column with index")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {str(e)}")
            raise

if __name__ == '__main__':
    migrate()
