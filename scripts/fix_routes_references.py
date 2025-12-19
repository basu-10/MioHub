"""Fix all remaining Note/Board references in routes.py and utils.py"""
import re

def fix_routes_py():
    """Update routes.py to use File instead of Note/Board"""
    with open('blueprints/p2/routes.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace Note.query patterns
    content = re.sub(r'Note\.query\.filter_by\(user_id=([^)]+)\)', r"File.query.filter_by(owner_id=\1, type='note')", content)
    content = re.sub(r'Note\.query\.filter_by\(folder_id=([^)]+)\)', r"File.query.filter_by(folder_id=\1, type='note')", content)  
    content = re.sub(r'Note\.query\.filter\(Note\.user_id', r"File.query.filter(File.owner_id", content)
    content = re.sub(r'Note\.query\.get_or_404', 'File.query.get_or_404', content)
    content = re.sub(r'Note\.user_id', 'File.owner_id', content)
    content = re.sub(r'\.content\.contains', '.content_html.contains', content)
    content = re.sub(r'Note\.id', 'File.id', content)
    content = re.sub(r'Note\.last_modified', 'File.last_modified', content)
    content = re.sub(r'Note\.created_at', 'File.created_at', content)
    content = re.sub(r'Note\.is_public', 'File.is_public', content)
    content = re.sub(r'Note\.folder_id', 'File.folder_id', content)

    # Replace Board.query patterns
    content = re.sub(r'Board\.query\.filter_by\(user_id=([^)]+)\)', r"File.query.filter_by(owner_id=\1, type='whiteboard')", content)
    content = re.sub(r'Board\.query\.filter_by\(folder_id=([^)]+)\)', r"File.query.filter_by(folder_id=\1, type='whiteboard')", content)
    content = re.sub(r'Board\.query\.filter\(Board\.user_id', r"File.query.filter(File.owner_id", content)
    content = re.sub(r'Board\.query\.get_or_404', 'File.query.get_or_404', content)
    content = re.sub(r'Board\.user_id', 'File.owner_id', content)
    content = re.sub(r'Board\.content', 'File.content_json', content)
    content = re.sub(r'Board\.description', "(File.metadata_json.get('description') or '')", content)
    content = re.sub(r'Board\.id', 'File.id', content)
    content = re.sub(r'Board\.last_modified', 'File.last_modified', content)
    content = re.sub(r'Board\.created_at', 'File.created_at', content)
    content = re.sub(r'Board\.is_public', 'File.is_public', content)
    content = re.sub(r'Board\.folder_id', 'File.folder_id', content)

    # Remove SharedNote references
    content = re.sub(r'from blueprints\.p2\.models import SharedNote\n', '', content)
    content = re.sub(r'shared_entries = SharedNote\.query[^\n]+', 'shared_entries = []  # SharedNote removed', content)

    with open('blueprints/p2/routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ Fixed routes.py')

def fix_utils_py():
    """Update utils.py to use File instead of Note/Board"""
    with open('blueprints/p2/utils.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Update imports
    content = re.sub(r'from blueprints\.p2\.models import Note, Board, User', 'from blueprints.p2.models import File, User', content)
    content = re.sub(r'from blueprints\.p2\.models import Board\n', '', content)
    
    # Replace queries
    content = re.sub(r'Note\.query\.filter_by\(user_id=user_id\)', "File.query.filter_by(owner_id=user_id, type='note')", content)
    content = re.sub(r'Board\.query\.filter_by\(user_id=user_id\)', "File.query.filter_by(owner_id=user_id, type='whiteboard')", content)
    
    with open('blueprints/p2/utils.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ Fixed utils.py')

def fix_whiteboard_routes():
    """Update whiteboard_routes.py to use File"""
    with open('blueprints/p2/whiteboard_routes.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the Note.query references in session cleanup code
    content = re.sub(r'for n in Note\.query\.filter_by\(user_id=current_user\.id\)', "for n in File.query.filter_by(owner_id=current_user.id, type='note')", content)
    content = re.sub(r'for b in BoardModel\.query\.filter_by\(user_id=current_user\.id\)', "for b in File.query.filter_by(owner_id=current_user.id, type='whiteboard')", content)
    
    with open('blueprints/p2/whiteboard_routes.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('✓ Fixed whiteboard_routes.py')

if __name__ == '__main__':
    print("Fixing remaining Note/Board references...")
    fix_routes_py()
    fix_utils_py()
    fix_whiteboard_routes()
    print("\n✅ All files fixed!")
