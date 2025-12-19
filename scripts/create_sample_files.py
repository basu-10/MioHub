"""
Test script to create sample File records in the new files table.
Demonstrates creating different file types: markdown, todo, note, diagram.
"""

from flask import Flask
from extensions import db
from blueprints.p2.models import File, Folder, User
import config
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def create_sample_files():
    with app.app_context():
        # Get test user
        testuser = User.query.filter_by(username='testuser').first()
        if not testuser:
            print("❌ Error: testuser not found. Run init_db.py first.")
            return
        
        # Get root folder
        root_folder = Folder.query.filter_by(user_id=testuser.id, parent_id=None).first()
        if not root_folder:
            print("❌ Error: No root folder found for testuser.")
            return
        
        print(f"Creating sample files for user '{testuser.username}' in folder '{root_folder.name}'...")
        print("=" * 60)
        
        # 1. Markdown file
        markdown_file = File(
            owner_id=testuser.id,
            folder_id=root_folder.id,
            type='markdown',
            title='My First Markdown Note',
            content_text='# Welcome to MioSpace\n\nThis is a **markdown** file stored in the new universal File table.\n\n## Features\n- Type-specific content storage\n- Coexists with legacy Note/Board models\n- Future-proof for PDFs, todos, diagrams',
            metadata_json={'description': 'A markdown introduction to the new File system'},
            is_public=False
        )
        db.session.add(markdown_file)
        print(f"✓ Created: {markdown_file.title} (type: {markdown_file.type})")
        
        # 2. Todo list file
        todo_file = File(
            owner_id=testuser.id,
            folder_id=root_folder.id,
            type='todo',
            title='Weekly Tasks',
            content_json={
                'items': [
                    {'id': 1, 'text': 'Test File table migration', 'completed': True},
                    {'id': 2, 'text': 'Create file routes', 'completed': True},
                    {'id': 3, 'text': 'Build unified UI', 'completed': True},
                    {'id': 4, 'text': 'Add markdown editor', 'completed': False},
                    {'id': 5, 'text': 'Add PDF upload', 'completed': False}
                ]
            },
            metadata_json={'description': 'Development roadmap for File system'},
            is_public=False
        )
        db.session.add(todo_file)
        print(f"✓ Created: {todo_file.title} (type: {todo_file.type})")
        
        # 3. Diagram file (JSON-based)
        diagram_file = File(
            owner_id=testuser.id,
            folder_id=root_folder.id,
            type='diagram',
            title='System Architecture',
            content_json={
                'nodes': [
                    {'id': 'user', 'label': 'User', 'x': 100, 'y': 100},
                    {'id': 'folder', 'label': 'Folder', 'x': 300, 'y': 100},
                    {'id': 'note', 'label': 'Note (Legacy)', 'x': 500, 'y': 50},
                    {'id': 'board', 'label': 'Board (Legacy)', 'x': 500, 'y': 100},
                    {'id': 'file', 'label': 'File (New)', 'x': 500, 'y': 150}
                ],
                'edges': [
                    {'from': 'user', 'to': 'folder'},
                    {'from': 'folder', 'to': 'note'},
                    {'from': 'folder', 'to': 'board'},
                    {'from': 'folder', 'to': 'file'}
                ]
            },
            metadata_json={'description': 'Database schema relationships', 'diagram_type': 'flowchart'},
            is_public=True  # Make this one public for testing
        )
        db.session.add(diagram_file)
        print(f"✓ Created: {diagram_file.title} (type: {diagram_file.type}, public: True)")
        
        # 4. Note file (HTML content, demonstrating backwards compatibility)
        note_file = File(
            owner_id=testuser.id,
            folder_id=root_folder.id,
            type='note',
            title='Migration Notes',
            content_html='<h1>File Table Migration</h1><p>Successfully migrated to universal file storage!</p><ul><li>All content types in one table</li><li>Type discriminator for routing</li><li>Metadata for auxiliary info</li></ul>',
            metadata_json={'description': 'Technical notes about the migration'},
            is_public=False
        )
        db.session.add(note_file)
        print(f"✓ Created: {note_file.title} (type: {note_file.type})")
        
        # Commit all files
        db.session.commit()
        
        print("=" * 60)
        print(f"✅ Successfully created 4 sample files!")
        print("\nFile details:")
        files = File.query.filter_by(owner_id=testuser.id).all()
        for f in files:
            size = f.get_content_size()
            print(f"  - ID {f.id}: {f.title} ({f.type}, {size} bytes)")
        
        print(f"\n📂 View these files at: /folders/{root_folder.id}")
        print(f"🌐 Public diagram at: /public/file/{diagram_file.id}")

if __name__ == '__main__':
    create_sample_files()
