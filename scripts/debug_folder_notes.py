"""
Diagnostic script to check what notes are being returned for folder 72
Run this on your remote server to debug the missing notes issue
"""

import config
from flask import Flask
from blueprints.p2.models import db, User, Note, Folder
from sqlalchemy import text
import json

def diagnose_folder_notes():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        print("=" * 80)
        print("DIAGNOSTIC: Folder 72 Notes Investigation")
        print("=" * 80)
        
        # Get folder
        folder = Folder.query.get(72)
        if not folder:
            print("❌ Folder 72 not found!")
            return
        
        print(f"\n✅ Folder found: {folder.name} (ID: {folder.id}, User ID: {folder.user_id})")
        
        # Get notes via relationship
        print(f"\n📊 Notes via relationship (folder.notes):")
        relationship_notes = folder.notes
        print(f"   Count: {len(relationship_notes)}")
        for note in relationship_notes:
            print(f"   - ID: {note.id}, Title: '{note.title}', User: {note.user_id}, Folder: {note.folder_id}")
        
        # Get notes via direct query
        print(f"\n📊 Notes via direct query (Note.query.filter_by):")
        direct_notes = Note.query.filter_by(folder_id=72).all()
        print(f"   Count: {len(direct_notes)}")
        for note in direct_notes:
            print(f"   - ID: {note.id}, Title: '{note.title}', User: {note.user_id}, Folder: {note.folder_id}")
        
        # Check for combined documents filtering
        print(f"\n🔍 Checking for combined documents logic:")
        combined_docs = []
        regular_notes = []
        
        for note in relationship_notes:
            if note.content:
                try:
                    content_data = json.loads(note.content)
                    if isinstance(content_data, list) and any(
                        block.get('type') in ['note', 'board'] for block in content_data if isinstance(block, dict)
                    ):
                        combined_docs.append(note)
                        print(f"   - Note {note.id} identified as COMBINED DOC")
                    else:
                        regular_notes.append(note)
                        print(f"   - Note {note.id} is regular note")
                except (json.JSONDecodeError, TypeError):
                    regular_notes.append(note)
                    print(f"   - Note {note.id} is regular note (not JSON)")
            else:
                regular_notes.append(note)
                print(f"   - Note {note.id} is regular note (no content)")
        
        print(f"\n📈 SUMMARY:")
        print(f"   Total notes: {len(relationship_notes)}")
        print(f"   Regular notes: {len(regular_notes)}")
        print(f"   Combined docs: {len(combined_docs)}")
        
        # Check raw SQL
        print(f"\n🗄️  Raw SQL query:")
        result = db.session.execute(
            text("SELECT id, title, user_id, folder_id FROM note WHERE folder_id = 72 ORDER BY id")
        )
        sql_notes = result.fetchall()
        print(f"   Count: {len(sql_notes)}")
        for row in sql_notes:
            print(f"   - ID: {row[0]}, Title: '{row[1]}', User: {row[2]}, Folder: {row[3]}")
        
        # Check for the specific missing notes
        print(f"\n🔎 Checking specific notes (326, 327):")
        for note_id in [326, 327]:
            note = Note.query.get(note_id)
            if note:
                print(f"\n   Note {note_id}:")
                print(f"     - Title: '{note.title}'")
                print(f"     - User ID: {note.user_id}")
                print(f"     - Folder ID: {note.folder_id}")
                print(f"     - Created: {note.created_at}")
                print(f"     - Content length: {len(note.content or '')}")
                print(f"     - Content preview: {(note.content or '')[:100]}")
            else:
                print(f"   ❌ Note {note_id} not found in database!")
        
        print("\n" + "=" * 80)

if __name__ == '__main__':
    diagnose_folder_notes()
