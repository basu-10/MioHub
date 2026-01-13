"""
Migration script to add API token support for Chrome extension.

Adds columns:
- api_token: Stores authentication token for extension
- api_token_expires: Token expiration timestamp

Run this once to enable extension API functionality.
"""

import env_loader

env_loader.load_env_from_wsgi()

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
        columns = [col['name'] for col in inspector.get_columns('user')]
        
        migrations = []
        
        # Add api_token column
        if 'api_token' not in columns:
            migrations.append("""
                ALTER TABLE user 
                ADD COLUMN api_token VARCHAR(255) NULL DEFAULT NULL,
                ADD INDEX idx_api_token (api_token)
            """)
            print("✓ Will add api_token column")
        else:
            print("✓ api_token column already exists")
        
        # Add api_token_expires column
        if 'api_token_expires' not in columns:
            migrations.append("""
                ALTER TABLE user 
                ADD COLUMN api_token_expires DATETIME NULL DEFAULT NULL
            """)
            print("✓ Will add api_token_expires column")
        else:
            print("✓ api_token_expires column already exists")
        
        # Execute migrations
        if migrations:
            print("\nExecuting migrations...")
            for migration in migrations:
                try:
                    db.session.execute(text(migration))
                    db.session.commit()
                    print("✓ Migration executed successfully")
                except Exception as e:
                    db.session.rollback()
                    print(f"✗ Migration failed: {e}")
                    return False
            
            print("\n✓ All migrations completed successfully!")
            return True
        else:
            print("\n✓ Database already up to date")
            return True

if __name__ == '__main__':
    print("=" * 60)
    print("Chrome Extension API Token Migration")
    print("=" * 60)
    print()
    
    success = migrate()
    
    if success:
        print("\n" + "=" * 60)
        print("Migration complete! Chrome extension API is ready.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Migration failed. Please check errors above.")
        print("=" * 60)
