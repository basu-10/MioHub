import sys
import os

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)

from flask import Flask
from extensions import db
from blueprints.p2.models import User, Folder
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    print("=== DEBUG: User and Folder Analysis ===")
    
    # Get all users
    users = User.query.all()
    print(f"\nTotal users: {len(users)}")
    for user in users:
        print(f"  User ID: {user.id}, Username: {user.username}, Type: {user.user_type}")
    
    # Get all folders
    folders = Folder.query.all()
    print(f"\nTotal folders: {len(folders)}")
    
    # Group folders by user
    user_folders = {}
    for folder in folders:
        if folder.user_id not in user_folders:
            user_folders[folder.user_id] = []
        user_folders[folder.user_id].append(folder)
    
    for user_id, folder_list in user_folders.items():
        user = User.query.get(user_id)
        username = user.username if user else "UNKNOWN"
        print(f"\nUser {user_id} ({username}) has {len(folder_list)} folders:")
        
        # Show root folders only
        root_folders = [f for f in folder_list if f.parent_id is None]
        print(f"  Root folders: {len(root_folders)}")
        for folder in root_folders:
            print(f"    - {folder.name} (ID: {folder.id})")
            # Show children
            children = [f for f in folder_list if f.parent_id == folder.id]
            for child in children:
                print(f"      └─ {child.name} (ID: {child.id})")
                # Show grandchildren
                grandchildren = [f for f in folder_list if f.parent_id == child.id]
                for grandchild in grandchildren:
                    print(f"         └─ {grandchild.name} (ID: {grandchild.id})")