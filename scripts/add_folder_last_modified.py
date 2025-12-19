"""
Migration script to add last_modified column to Folder table.
For existing records, last_modified will be set to created_at value.
"""
import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Flask and database imports
from flask import Flask
from extensions import db
from blueprints.p2.models import Folder
import config
from datetime import datetime
from sqlalchemy import text, inspect

def setup_app():
    """Set up Flask app and database configuration."""
    app = Flask(__name__)
    
    # Database configuration
    DB_NAME = config.DB_NAME
    DB_USER = config.DB_USER
    DB_PASSWORD = config.DB_PASSWORD
    DB_PORT = config.DB_PORT
    DB_HOST = config.DB_HOST
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    return app

def add_folder_last_modified_column():
    """Add last_modified column to Folder table."""
    app = setup_app()
    
    with app.app_context():
        # Check if folder table has last_modified column
        inspector = inspect(db.engine)
        folder_columns = inspector.get_columns('folder')
        column_names = [col['name'] for col in folder_columns]
        folder_has_last_modified = 'last_modified' in column_names
        
        print("Folder Migration Status:")
        print(f"Folder has last_modified: {folder_has_last_modified}")
        
        # Add last_modified column to folder table if it doesn't exist
        if not folder_has_last_modified:
            print("Adding last_modified column to folder table...")
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE folder ADD COLUMN last_modified DATETIME"))
                conn.commit()
            
            # Populate last_modified with created_at values for existing folders
            print("Populating last_modified with created_at values for existing folders...")
            with db.engine.connect() as conn:
                conn.execute(text("UPDATE folder SET last_modified = created_at WHERE last_modified IS NULL"))
                conn.commit()
            
            print("✅ Folder table last_modified column added and populated")
        else:
            print("Folder table already has last_modified column")
        
        print("Migration completed successfully!")

if __name__ == '__main__':
    add_folder_last_modified_column()