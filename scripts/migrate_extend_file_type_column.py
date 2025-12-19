"""
Migration: Extend files.type column to VARCHAR(50)

The type column was VARCHAR(20), but proprietary file types like 
'proprietary_whiteboard' (23 chars) and 'proprietary_infinite_whiteboard' (30 chars) 
exceed this limit. This migration extends it to VARCHAR(50) to accommodate all current 
and future file types.

Run: python migrate_extend_file_type_column.py
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
    """Extend the type column in files table to VARCHAR(50)."""
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Check if files table exists
        if 'files' not in inspector.get_table_names():
            print("❌ ERROR: files table does not exist. Run init_db.py first.")
            return False
        
        # Get current column info
        columns = {col['name']: col for col in inspector.get_columns('files')}
        
        if 'type' not in columns:
            print("❌ ERROR: type column does not exist in files table.")
            return False
        
        type_col = columns['type']
        print(f"✓ Current type column definition: {type_col}")
        
        # Check if already modified
        # MySQL reports varchar as 'VARCHAR' with max_length property
        if hasattr(type_col['type'], 'length') and type_col['type'].length >= 50:
            print(f"✓ Column already extended to VARCHAR({type_col['type'].length}). Skipping migration.")
            return True
        
        # Perform migration
        print("\n🔧 Extending files.type column to VARCHAR(50)...")
        try:
            with db.engine.connect() as conn:
                # Use ALTER TABLE to modify column
                conn.execute(text("ALTER TABLE files MODIFY COLUMN type VARCHAR(50) NOT NULL"))
                conn.commit()
            
            print("✅ Successfully extended files.type to VARCHAR(50)")
            
            # Verify the change
            inspector = inspect(db.engine)
            columns = {col['name']: col for col in inspector.get_columns('files')}
            type_col = columns['type']
            print(f"✓ New type column definition: {type_col}")
            
            return True
            
        except Exception as e:
            print(f"❌ ERROR during migration: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Extend files.type column to VARCHAR(50)")
    print("=" * 60)
    success = migrate()
    print("=" * 60)
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed. See errors above.")
    print("=" * 60)
