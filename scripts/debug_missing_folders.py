"""
Debug script to find why folders/notes exist in database but don't show in app
"""
import mysql.connector
import config
from datetime import datetime

DB_HOST = config.DB_HOST
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_PORT = int(config.DB_PORT)

def get_connection():
    """Create database connection"""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )

def check_folder_details(cursor, folder_id=107):
    """Check all details about a specific folder"""
    print("="*80)
    print(f"FOLDER DETAILS (ID: {folder_id})")
    print("="*80)
    
    cursor.execute(f"""
        SELECT id, name, user_id, parent_id, created_at
        FROM folder
        WHERE id = {folder_id}
    """)
    folder = cursor.fetchone()
    
    if folder:
        print(f"ID: {folder[0]}")
        print(f"Name: {folder[1]}")
        print(f"User ID: {folder[2]}")
        print(f"Parent ID: {folder[3]}")
        print(f"Created At: {folder[4]}")
        return folder
    else:
        print(f"❌ Folder {folder_id} not found!")
        return None

def check_column_exists(cursor, table_name):
    """Check what columns exist in a table"""
    print(f"\n{'='*80}")
    print(f"COLUMNS IN {table_name.upper()} TABLE")
    print("="*80)
    
    cursor.execute(f"DESCRIBE {table_name}")
    columns = cursor.fetchall()
    
    col_names = []
    for col in columns:
        col_names.append(col[0])
        print(f"{col[0]}: {col[1]} {'NULL' if col[2] == 'YES' else 'NOT NULL'} {f'DEFAULT {col[4]}' if col[4] else ''}")
    
    return col_names

def check_folders_missing_created_at(cursor):
    """Check if any folders are missing created_at values"""
    print(f"\n{'='*80}")
    print("FOLDERS WITH NULL created_at")
    print("="*80)
    
    cursor.execute("""
        SELECT id, name, user_id, parent_id, created_at
        FROM folder
        WHERE created_at IS NULL
    """)
    folders = cursor.fetchall()
    
    if folders:
        print(f"⚠ Found {len(folders)} folders with NULL created_at:")
        for folder in folders:
            print(f"  ID: {folder[0]}, Name: {folder[1]}, User: {folder[2]}, Parent: {folder[3]}")
    else:
        print("✓ All folders have created_at values")
    
    return folders

def check_notes_missing_created_at(cursor):
    """Check if any notes are missing created_at values"""
    print(f"\n{'='*80}")
    print("NOTES WITH NULL created_at")
    print("="*80)
    
    cursor.execute("""
        SELECT id, title, user_id, folder_id, created_at
        FROM note
        WHERE created_at IS NULL
    """)
    notes = cursor.fetchall()
    
    if notes:
        print(f"⚠ Found {len(notes)} notes with NULL created_at:")
        for note in notes:
            print(f"  ID: {note[0]}, Title: {note[1]}, User: {note[2]}, Folder: {note[3]}")
    else:
        print("✓ All notes have created_at values")
    
    return notes

def check_boards_missing_created_at(cursor):
    """Check if any boards are missing created_at values"""
    print(f"\n{'='*80}")
    print("BOARDS WITH NULL created_at")
    print("="*80)
    
    cursor.execute("""
        SELECT id, title, user_id, folder_id, created_at
        FROM boards
        WHERE created_at IS NULL
    """)
    boards = cursor.fetchall()
    
    if boards:
        print(f"⚠ Found {len(boards)} boards with NULL created_at:")
        for board in boards:
            print(f"  ID: {board[0]}, Title: {board[1]}, User: {board[2]}, Folder: {board[3]}")
    else:
        print("✓ All boards have created_at values")
    
    return boards

def check_folder_hierarchy(cursor, folder_id=107):
    """Check the folder hierarchy path"""
    print(f"\n{'='*80}")
    print(f"FOLDER HIERARCHY FOR FOLDER {folder_id}")
    print("="*80)
    
    path = []
    current_id = folder_id
    
    while current_id:
        cursor.execute(f"""
            SELECT id, name, parent_id, user_id
            FROM folder
            WHERE id = {current_id}
        """)
        folder = cursor.fetchone()
        
        if folder:
            path.insert(0, folder)
            current_id = folder[2]  # parent_id
        else:
            break
    
    print("Path from root to folder:")
    for i, folder in enumerate(path):
        indent = "  " * i
        print(f"{indent}└─ {folder[1]} (ID: {folder[0]}, User: {folder[3]})")
    
    return path

def check_notes_in_folder(cursor, folder_id=107):
    """Check notes in a specific folder"""
    print(f"\n{'='*80}")
    print(f"NOTES IN FOLDER {folder_id}")
    print("="*80)
    
    cursor.execute(f"""
        SELECT id, title, user_id, folder_id, created_at
        FROM note
        WHERE folder_id = {folder_id}
        ORDER BY created_at DESC
    """)
    notes = cursor.fetchall()
    
    if notes:
        print(f"Found {len(notes)} notes:")
        for note in notes:
            print(f"  ID: {note[0]}, Title: {note[1]}, User: {note[2]}, Created: {note[4]}")
    else:
        print("No notes in this folder")
    
    return notes

def check_boards_in_folder(cursor, folder_id=107):
    """Check boards in a specific folder"""
    print(f"\n{'='*80}")
    print(f"BOARDS IN FOLDER {folder_id}")
    print("="*80)
    
    cursor.execute(f"""
        SELECT id, title, user_id, folder_id, created_at
        FROM boards
        WHERE folder_id = {folder_id}
        ORDER BY created_at DESC
    """)
    boards = cursor.fetchall()
    
    if boards:
        print(f"Found {len(boards)} boards:")
        for board in boards:
            print(f"  ID: {board[0]}, Title: {board[1]}, User: {board[2]}, Created: {board[4]}")
    else:
        print("No boards in this folder")
    
    return boards

def check_all_users(cursor):
    """List all users"""
    print(f"\n{'='*80}")
    print("ALL USERS")
    print("="*80)
    
    cursor.execute("SELECT id, username, user_type FROM user")
    users = cursor.fetchall()
    
    for user in users:
        print(f"ID: {user[0]}, Username: {user[1]}, Type: {user[2]}")
    
    return users

def check_recent_folders(cursor, limit=20):
    """Show most recently created folders"""
    print(f"\n{'='*80}")
    print(f"RECENT FOLDERS (Last {limit})")
    print("="*80)
    
    cursor.execute(f"""
        SELECT id, name, user_id, parent_id, created_at
        FROM folder
        ORDER BY created_at DESC
        LIMIT {limit}
    """)
    folders = cursor.fetchall()
    
    for folder in folders:
        print(f"ID: {folder[0]}, Name: {folder[1]}, User: {folder[2]}, Parent: {folder[3]}, Created: {folder[4]}")
    
    return folders

def main():
    """Main debugging function"""
    print("\n" + "="*80)
    print("DATABASE DEBUGGING TOOL - MISSING FOLDERS/FILES")
    print("="*80)
    print(f"Database: {DB_NAME}")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print("="*80)
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get folder ID from user
        folder_id_input = input("\nEnter folder ID to debug (default: 107): ").strip()
        folder_id = int(folder_id_input) if folder_id_input else 107
        
        # Check table structures
        check_column_exists(cursor, 'folder')
        check_column_exists(cursor, 'note')
        check_column_exists(cursor, 'boards')
        
        # Check for NULL created_at values
        null_folders = check_folders_missing_created_at(cursor)
        null_notes = check_notes_missing_created_at(cursor)
        null_boards = check_boards_missing_created_at(cursor)
        
        # Check specific folder
        folder = check_folder_details(cursor, folder_id)
        
        if folder:
            # Check folder hierarchy
            check_folder_hierarchy(cursor, folder_id)
            
            # Check contents
            check_notes_in_folder(cursor, folder_id)
            check_boards_in_folder(cursor, folder_id)
        
        # Show all users
        check_all_users(cursor)
        
        # Show recent folders
        check_recent_folders(cursor)
        
        # DIAGNOSIS SUMMARY
        print("\n" + "="*80)
        print("DIAGNOSIS SUMMARY")
        print("="*80)
        
        issues_found = []
        
        if null_folders:
            issues_found.append(f"⚠ {len(null_folders)} folders with NULL created_at")
        if null_notes:
            issues_found.append(f"⚠ {len(null_notes)} notes with NULL created_at")
        if null_boards:
            issues_found.append(f"⚠ {len(null_boards)} boards with NULL created_at")
        
        if issues_found:
            print("\nIssues detected:")
            for issue in issues_found:
                print(f"  {issue}")
            
            print("\n🔧 POSSIBLE CAUSES:")
            print("  1. Items with NULL created_at might be filtered out by queries")
            print("  2. The migration added the column but didn't backfill existing rows")
            print("  3. App might be filtering by created_at or ordering by it")
            
            print("\n💡 SOLUTIONS:")
            print("  1. Run the fix script to update NULL created_at values")
            print("  2. Check your folder/note query routes for ORDER BY created_at")
            print("  3. Check if there are any WHERE created_at IS NOT NULL filters")
        else:
            print("✓ No NULL created_at values found")
            print("\n🔧 OTHER POSSIBLE CAUSES:")
            print("  1. User ID mismatch (check if you're logged in as the right user)")
            print("  2. Parent folder relationship issue")
            print("  3. Session state issue (check session['current_folder_id'])")
            print("  4. Frontend JavaScript filtering")
        
        cursor.close()
        conn.close()
        
        print("\n" + "="*80)
        
    except mysql.connector.Error as err:
        print(f"\n✗ ERROR: {err}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
