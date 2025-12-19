"""Fix final Note/Board references"""
import re

# Fix notes_route.py
with open('blueprints/p2/notes_route.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'Board\.query\.filter_by\(user_id=current_user\.id\)', 
                 r"File.query.filter_by(owner_id=current_user.id, type='whiteboard')", 
                 content)
content = re.sub(r'Note\.query\.filter_by\(folder_id=([^,]+), user_id=([^)]+)\)', 
                 r"File.query.filter_by(folder_id=\1, owner_id=\2, type='note')", 
                 content)
content = re.sub(r'Board\.query\.filter_by\(folder_id=([^,]+), user_id=([^)]+)\)', 
                 r"File.query.filter_by(folder_id=\1, owner_id=\2, type='whiteboard')", 
                 content)

with open('blueprints/p2/notes_route.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed notes_route.py')

# Fix folder_ops.py
with open('blueprints/p2/folder_ops.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'note = Note\.query\.get\(note_id\)', 
                 'note = File.query.get(note_id)  # Legacy wrapper', 
                 content)
content = re.sub(r'board = Board\.query\.get\(board_id\)', 
                 'board = File.query.get(board_id)  # Legacy wrapper', 
                 content)

with open('blueprints/p2/folder_ops.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('✓ Fixed folder_ops.py')

print('\n✅ All done!')
