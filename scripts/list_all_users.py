"""
Script to list all users in the database with their details.
"""

import os

# Set environment file to prod.env before importing config
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

from flask import Flask
from extensions import db
from blueprints.p2.models import User
import config
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def format_bytes(bytes_value):
    """Convert bytes to human-readable format."""
    if bytes_value is None:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"

def format_datetime(dt):
    """Format datetime to readable string."""
    if dt is None:
        return "Never"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def list_all_users():
    """Query and display all users with their details."""
    with app.app_context():
        users = User.query.order_by(User.id).all()
        
        if not users:
            print("No users found in the database.")
            return
        
        print(f"\n{'='*120}")
        print(f"Total Users: {len(users)}")
        print(f"{'='*120}\n")
        
        for user in users:
            print(f"{'─'*120}")
            print(f"ID:              {user.id}")
            print(f"Username:        {user.username}")
            print(f"Email:           {user.email or 'Not set'}")
            print(f"User Type:       {user.user_type}")
            print(f"Is Admin:        {user.is_admin}")
            print(f"Storage Used:    {format_bytes(user.total_data_size)}")
            print(f"Created At:      {format_datetime(user.created_at)}")
            print(f"Last Login:      {format_datetime(user.last_login)}")
            print(f"Profile Pic:     {user.profile_pic_url or 'None'}")
            
            # Display user preferences
            if user.user_prefs:
                print(f"Preferences:")
                print(f"  - Theme:       {user.user_prefs.get('theme', 'Not set')}")
                print(f"  - Is Pinned:   {user.user_prefs.get('isPinned', False)}")
                if 'display' in user.user_prefs:
                    display = user.user_prefs['display']
                    print(f"  - View Mode:   {display.get('view_mode', 'Not set')}")
                    print(f"  - Columns:     {display.get('columns', 'Not set')}")
                if 'pinned_users' in user.user_prefs:
                    pinned = user.user_prefs['pinned_users']
                    print(f"  - Pinned Users: {len(pinned)} pinned")
            
            # Count user's folders and files
            folder_count = len(user.folders)
            
            # Count files (across all folders)
            file_count = 0
            for folder in user.folders:
                file_count += len(folder.files)
            
            print(f"Folders:         {folder_count}")
            print(f"Files:           {file_count}")
            print(f"{'─'*120}\n")
        
        # Summary by user type
        print(f"\n{'='*120}")
        print("Summary by User Type:")
        print(f"{'='*120}")
        
        type_counts = {}
        type_storage = {}
        
        for user in users:
            user_type = user.user_type
            type_counts[user_type] = type_counts.get(user_type, 0) + 1
            type_storage[user_type] = type_storage.get(user_type, 0) + (user.total_data_size or 0)
        
        for user_type in sorted(type_counts.keys()):
            count = type_counts[user_type]
            storage = type_storage[user_type]
            print(f"{user_type:15} {count:3} users    Total Storage: {format_bytes(storage)}")
        
        print(f"{'='*120}\n")

if __name__ == '__main__':
    try:
        list_all_users()
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
