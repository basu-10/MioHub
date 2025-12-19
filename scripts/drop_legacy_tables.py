"""
Drop legacy Note and Board tables after successful migration to File table.

ONLY RUN THIS AFTER:
1. Migration script has completed successfully
2. All routes have been updated to use File table
3. All tests pass
4. Production verification complete
"""

from flask import Flask
from extensions import db
from sqlalchemy import text
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def drop_legacy_tables():
    """Drop Note and Board tables from database."""
    with app.app_context():
        print("\n" + "="*80)
        print("DROPPING LEGACY TABLES")
        print("="*80)
        
        # Check if tables exist
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        tables_to_drop = []
        if 'note' in tables:
            tables_to_drop.append('note')
        if 'boards' in tables:
            tables_to_drop.append('boards')
        if 'shared_note' in tables:
            tables_to_drop.append('shared_note')
        
        if not tables_to_drop:
            print("\nNo legacy tables found. Already dropped or never existed.")
            return
        
        print(f"\nTables to drop: {', '.join(tables_to_drop)}")
        print("\nWARNING: This operation cannot be undone!")
        print("Ensure you have:")
        print("  1. Verified migration completed successfully")
        print("  2. Updated all routes to use File table")
        print("  3. Tested thoroughly")
        print("  4. Created database backup")
        
        response = input("\nProceed with dropping tables? (yes/no): ").strip().lower()
        
        if response == 'yes':
            try:
                # Drop tables in correct order (foreign keys first)
                if 'shared_note' in tables_to_drop:
                    print("\nDropping shared_note table...")
                    db.session.execute(text("DROP TABLE IF EXISTS shared_note"))
                    print("  ✓ Dropped shared_note")
                
                if 'note' in tables_to_drop:
                    print("\nDropping note table...")
                    db.session.execute(text("DROP TABLE IF EXISTS note"))
                    print("  ✓ Dropped note")
                
                if 'boards' in tables_to_drop:
                    print("\nDropping boards table...")
                    db.session.execute(text("DROP TABLE IF EXISTS boards"))
                    print("  ✓ Dropped boards")
                
                db.session.commit()
                
                print("\n" + "="*80)
                print("LEGACY TABLES DROPPED SUCCESSFULLY")
                print("="*80)
                print("\nNext steps:")
                print("  1. Remove Note and Board model classes from models.py")
                print("  2. Remove legacy route blueprints")
                print("  3. Update documentation")
                print("="*80 + "\n")
                
            except Exception as e:
                db.session.rollback()
                print(f"\n{'='*80}")
                print(f"ERROR: {str(e)}")
                print(f"{'='*80}\n")
                raise
        else:
            print("\nOperation cancelled. No tables were dropped.")

if __name__ == '__main__':
    drop_legacy_tables()
