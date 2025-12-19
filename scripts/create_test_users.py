'''
Create additional test users for admin dashboard testing
'''

import sys
import os
# Add parent directory to path so we can import from blueprints
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from blueprints.p2.models import db, User, File, Folder  
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random
import config

def create_test_users():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        # Create test users
        test_users_data = [
            {"username": "testuser", "email": "alice@example.com", "user_type": "guest"},
            {"username": "testuser222", "email": "bob@example.com", "user_type": "user"},
            {"username": "charlie_brown", "email": "charlie@example.com", "user_type": "user"},
            {"username": "diana_prince", "email": "diana@example.com", "user_type": "user"},
            {"username": "eve_wilson", "email": "eve@example.com", "user_type": "user"},
            {"username": "frank_miller", "email": "frank@example.com", "user_type": "user"},
            {"username": "grace_hopper", "email": "grace@example.com", "user_type": "user"},
            {"username": "henry_ford", "email": "henry@example.com", "user_type": "user"},
            {"username": "iris_watson", "email": "iris@example.com", "user_type": "user"},
            {"username": "jack_daniels", "email": "jack@example.com", "user_type": "user"},
            {"username": "moderator1", "email": "mod1@example.com", "user_type": "admin"},
            {"username": "moderator2", "email": "mod2@example.com", "user_type": "admin"},
        ]

        created_count = 0
        for user_data in test_users_data:
            # Check if user already exists
            existing_user = User.query.filter_by(username=user_data["username"]).first()
            if not existing_user:
                # Create user with random creation time in the past 30 days
                created_at = datetime.utcnow() - timedelta(days=random.randint(1, 30))
                last_login = created_at + timedelta(days=random.randint(0, 5))
                
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash=generate_password_hash('password123'),
                    security_answer='blue',
                    user_type=user_data["user_type"],
                    created_at=created_at,
                    last_login=last_login,
                    user_prefs={
                        "theme": "flatly",
                        "isPinned": False,
                        "display": {
                            "columns": 3,
                            "view_mode": "grid",
                            "card_size": "normal",
                            "show_previews": True
                        }
                    },
                    profile_pic_url='',
                    total_data_size=0
                )
                db.session.add(new_user)
                db.session.flush()

                # Create root folder for each user
                root_folder = Folder(name='root', user_id=new_user.id, parent_id=None, is_root=True)
                db.session.add(root_folder)
                db.session.flush()

                # Create some random files (notes) for each user using File model
                for i in range(random.randint(1, 5)):
                    file = File(
                        owner_id=new_user.id,
                        title=f'Note {i+1} by {user_data["username"]}',
                        type='note',  # Legacy note type
                        content_html=f'<p>This is test note {i+1} created by {user_data["username"]}.</p>',
                        folder_id=root_folder.id,
                        metadata_json={'description': f'Test note {i+1}'}
                    )
                    db.session.add(file)

                created_count += 1
                print(f"✅ Created user: {user_data['username']}")
            else:
                print(f"⚠️  User already exists: {user_data['username']}")

        db.session.commit()
        print(f"\n✅ Created {created_count} new test users with sample data.")
        print(f"Total test users: {len(test_users_data)}")

if __name__ == '__main__':
    create_test_users()