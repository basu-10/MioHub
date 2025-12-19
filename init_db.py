'''
run once from terminal 
to create db, table, 
createa a sample user, note.

'''

import config
from sqlalchemy import inspect
from flask import Flask
from blueprints.p2.models import db, User, File, Folder
from blueprints.p3.models import ChatSession, ChatMessage, ChatMemory, GameScore
from werkzeug.security import generate_password_hash
from datetime import datetime

# Step 1: Initialize Flask + SQLAlchemy and create tables
def init_app_and_tables():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        if not tables:
            db.create_all()
            print("✅ All tables created.")
        else:
            print("ℹ️ Main tables already exist.")
            # Always ensure chatbot tables exist
            from blueprints.p3.models import ChatSession, ChatMessage, ChatMemory, GameScore
            db.create_all()
            print("✅ Chatbot tables created/verified.")

        # Check if testuser already exists
        existing_user = User.query.filter_by(username='testuser').first()
        if not existing_user:
            test_user = User(
                username='testuser',
                email='test@example.com',
                password_hash=generate_password_hash('password123'),
                security_answer='blue',
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
                user_prefs={
                    "theme": "flatly",
                    "isPinned": False
                },
                profile_pic_url=''
            )
            db.session.add(test_user)
            db.session.commit()

            # Create root folder
            root_folder = Folder(name='root', user_id=test_user.id, parent_id=None, is_root=True)
            db.session.add(root_folder)
            db.session.commit()

            # Create test markdown file inside root
            test_file = File(
                owner_id=test_user.id,
                folder_id=root_folder.id,
                type='markdown',
                title='Default Note',
                content_text='# Welcome\n\nThis is a test markdown file inside root folder. From init_db.py',
                metadata_json={'description': 'Initial test file'}
            )
            db.session.add(test_file)
            db.session.commit()

            print("✅ Test user, root folder, and test file created.")
        else:
            print("ℹ️ Test user already exists.")

        # Check if admin user already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if not existing_admin:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin123'),
                security_answer='admin',
                user_type='admin',
                created_at=datetime.utcnow(),
                last_login=datetime.utcnow(),
                user_prefs={
                    "theme": "flatly",
                    "isPinned": False
                },
                profile_pic_url=''
            )
            db.session.add(admin_user)
            db.session.commit()

            print("✅ Admin user created.")
        else:
            print("ℹ️ Admin user already exists.")
        

if __name__ == '__main__':
    init_app_and_tables()
