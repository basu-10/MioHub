"""
Database cleanup script - Removes ALL data and resets tables.

CAUTION: This script will DELETE ALL:
- Users (including test users)
- Folders
- Files (notes, whiteboards, books, etc.)
- Chat sessions and messages
- Notifications
- All other data

This operation is IRREVERSIBLE!
"""

from flask import Flask
from extensions import db
from sqlalchemy import text
import config

def cleanup_database():
    """Clean up all data from the database."""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        print("=" * 60)
        print("DATABASE CLEANUP SCRIPT")
        print("=" * 60)
        print()
        print("⚠️  WARNING: This will DELETE ALL DATA from the database!")
        print()
        print("Tables that will be cleared:")
        print("  - user")
        print("  - folder")
        print("  - files (all content types)")
        print("  - notifications")
        print("  - chat_sessions")
        print("  - chat_messages")
        print("  - chat_memories")
        print("  - game_scores (P4 games)")
        print()
        
        # Get confirmation
        confirmation = input("Type 'DELETE ALL DATA' to proceed: ").strip()
        
        if confirmation != "DELETE ALL DATA":
            print("\n❌ Cleanup cancelled. No changes were made.")
            return
        
        print("\n🔄 Starting database cleanup...\n")
        
        try:
            # Disable foreign key checks temporarily
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            
            # List of tables to truncate (order doesn't matter with FK checks disabled)
            tables = [
                'notifications',
                'files',
                'folder',  # singular
                'user',    # singular
                'chat_memories',
                'chat_messages',
                'chat_sessions',
                'game_scores',  # P4 game scores
            ]
            
            for table in tables:
                try:
                    # Check if table exists
                    result = db.session.execute(text(
                        f"SHOW TABLES LIKE '{table}'"
                    )).fetchone()
                    
                    if result:
                        # Truncate table (removes all rows and resets auto_increment)
                        db.session.execute(text(f"TRUNCATE TABLE {table}"))
                        print(f"  ✓ Cleared table: {table}")
                    else:
                        print(f"  ⊘ Table not found: {table} (skipped)")
                        
                except Exception as e:
                    print(f"  ⚠️  Error clearing {table}: {e}")
            
            # Re-enable foreign key checks
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
            
            # Commit all changes
            db.session.commit()
            
            print("\n" + "=" * 60)
            print("✅ DATABASE CLEANUP COMPLETE!")
            print("=" * 60)
            print()
            print("All data has been removed.")
            print("Auto-increment counters have been reset.")
            print()
            print("Next steps:")
            print("  1. Run init_db.py to recreate test users")
            print("  2. Or start fresh with the application")
            print()
            
        except Exception as e:
            db.session.rollback()
            print("\n" + "=" * 60)
            print("❌ ERROR during cleanup!")
            print("=" * 60)
            print(f"\nError: {e}")
            print("\nDatabase has been rolled back. No changes were made.")
            raise

if __name__ == "__main__":
    cleanup_database()
