#folder ops

from blueprints.p2.models import Folder, Board, Note, db
from flask_login import current_user
from blueprints.p2.models import User
from .utils import collect_images_from_content, copy_images_to_user, save_data_uri_images_for_user
import re

def create_folder(name, parent_id=None, description=None):
    """Create a new folder with optional description"""
    folder = Folder(name=name, user_id=current_user.id, parent_id=parent_id, description=description)
    db.session.add(folder)
    db.session.commit()
    return folder

def rename_folder(folder_id, new_name, new_description=None):
    """Rename folder and optionally update description"""
    folder = Folder.query.get(folder_id)
    if folder and folder.user_id == current_user.id:
        folder.name = new_name
        if new_description is not None:
            folder.description = new_description
        db.session.commit()
        return True
    return False

def delete_folder(folder_id):
    folder = Folder.query.get(folder_id)

    if not folder or folder.user_id != current_user.id:
        return False

    def delete_recursive(f):
        # Delete all notes in this folder
        for note in f.notes:
            db.session.delete(note)

        # Recursively delete all subfolders
        for child in f.children:
            delete_recursive(child)

        db.session.delete(f)

    delete_recursive(folder)
    db.session.commit()
    return True


# build and pass the breadcrumb
def build_folder_breadcrumb(folder):
    """Return list of folders from root -> ... -> current folder."""
    chain = []
    f = folder
    while f is not None:
        chain.append(f)
        f = f.parent  # assumes Folder.parent relationship
    chain.reverse()
    return chain

def move_folder(folder_id, target_parent_id):
    folder = Folder.query.get(folder_id)
    target_parent = Folder.query.get(target_parent_id)

    if (
        folder and folder.user_id == current_user.id
        and target_parent and target_parent.user_id == current_user.id
        and folder.id != target_parent_id  # prevent self-parenting
    ):
        folder.parent_id = target_parent_id
        db.session.commit()
        return True
    return False



def copy_folder_recursive(original_folder_id, target_parent_id, allow_external=False):
    """Recursively copy a folder. By default only allows copying folders owned by current_user.
    If allow_external is True, allows copying other users' public folders into current_user's tree.
    Returns the cloned root Folder instance on success, or None on failure.
    """
    original = Folder.query.get(original_folder_id)
    if not original:
        return None
    if not allow_external and original.user_id != current_user.id:
        return None

    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    # Track visited folders to prevent infinite recursion from circular references
    visited = set()

    def clone_folder(folder, new_parent_id, depth=0):
        # Prevent circular references and excessive depth
        if folder.id in visited:
            print(f"WARNING: Circular reference detected for folder {folder.id} '{folder.name}'")
            return None
        if depth > 100:  # Maximum nesting depth
            print(f"WARNING: Maximum folder depth (100) exceeded for folder {folder.id} '{folder.name}'")
            return None
        
        visited.add(folder.id)
        
        # Folder.name column is String(100)
        new_folder_name = truncate((folder.name or '') + ' (copy)', 100)
        # Preserve folder description when copying (truncate to column length)
        new_folder_description = truncate(folder.description, 500) if getattr(folder, 'description', None) else None
        new_folder = Folder(name=new_folder_name, user_id=current_user.id, parent_id=new_parent_id, description=new_folder_description)
        db.session.add(new_folder)
        db.session.flush()  # get new_folder.id

        # Copy notes (assign to current_user)
        for note in folder.notes:
            # Note.title column is String(200)
            new_note_title = truncate((note.title or '') + ' (copy)', 200)
            new_note = Note(
                title=new_note_title,
                content=note.content,
                description=getattr(note, 'description', None),
                user_id=current_user.id,
                folder_id=new_folder.id
            )
            db.session.add(new_note)

        # Copy boards (assign to current_user)
        for board in folder.boards:
            # Board.title column is String(100)
            new_board_title = truncate((board.title or '') + ' (copy)', 100)
            new_board = Board(
                title=new_board_title,
                content=board.content,
                description=getattr(board, 'description', None),
                user_id=current_user.id,
                folder_id=new_folder.id
            )
            db.session.add(new_board)

        # Recurse into children
        for sub in folder.children:
            clone_folder(sub, new_folder.id, depth + 1)

        return new_folder

    cloned_root = clone_folder(original, target_parent_id)
    db.session.commit()
    return cloned_root


def _sanitize_username_for_folder(username):
    """Sanitize username to be safe in folder name: lowercase, replace non-alnum with underscore"""
    if not username:
        return 'unknown'
    s = username.strip().lower()
    s = re.sub(r'[^a-z0-9_\-]', '_', s)
    return s


def get_or_create_folder_path(user_id, segments):
    """Ensure that a nested path exists for a given user and return the final folder id.

    Example: segments=['social','received','from_alice'] -> ensures root/social/received/from_alice exist and returns the id for 'from_alice'
    """
    if not segments:
        return None
    # find the user's root folder; create one if it does not exist
    root = Folder.query.filter_by(user_id=user_id, parent_id=None).first()
    if not root:
        root = Folder(name='root', user_id=user_id)
        db.session.add(root)
        db.session.flush()

    parent = root
    for seg in segments:
        # try to find child with exact name
        child = Folder.query.filter_by(user_id=user_id, parent_id=parent.id, name=seg).first()
        if not child:
            child = Folder(name=seg, user_id=user_id, parent_id=parent.id)
            db.session.add(child)
            db.session.flush()
        parent = child
    db.session.commit()
    return parent.id


def copy_folder_to_user(original_folder_id, receiver_user_id, sender_username=None):
    """Copy a folder (and its contents) from current_user to receiver_user's folder tree under root/social/received/from_<sender_username>
    Returns tuple: (cloned_folder, actual_bytes_written) or (None, 0) on failure
    """
    original = Folder.query.get(original_folder_id)
    if not original or original.user_id != current_user.id:
        return (None, 0)

    receiver = User.query.get(receiver_user_id)
    if not receiver:
        return (None, 0)

    # Build path segments
    sender_segment = 'from_' + _sanitize_username_for_folder(sender_username or current_user.username or 'unknown')
    segments = ['social', 'received', sender_segment]
    target_parent_id = get_or_create_folder_path(receiver_user_id, segments)
    if not target_parent_id:
        print(f"ERROR: copy_folder_to_user - failed to create/get folder path for receiver {receiver_user_id}")
        return (None, 0)

    # Track total bytes written
    total_bytes_written = 0

    # We'll implement a recursive clone similar to copy_folder_recursive, but set user_id to receiver_user_id
    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    def clone_folder_to_user(folder, new_parent_id):
        nonlocal total_bytes_written
        new_folder = Folder(name=truncate(folder.name, 100), user_id=receiver_user_id, parent_id=new_parent_id, description=truncate(folder.description, 500) if getattr(folder, 'description', None) else None)
        db.session.add(new_folder)
        db.session.flush()

        for note in folder.notes:
            # Convert inline data URIs into receiver's upload folder
            note_content = note.content
            note_description = getattr(note, 'description', None)
            bytes_from_datauris = 0
            if note_content:
                note_content, added = save_data_uri_images_for_user(note_content, receiver_user_id)
                bytes_from_datauris += added
            if note_description:
                note_description, added = save_data_uri_images_for_user(note_description, receiver_user_id)
                bytes_from_datauris += added
            # Now copy referenced uploaded images (by filename) to receiver and fix links
            image_filenames = set()
            if note_content:
                collect_images_from_content(note_content, image_filenames)
            if note_description:
                collect_images_from_content(note_description or '', image_filenames)
            mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
            if mapping:
                for old_fn, new_fn in mapping.items():
                    if note_content:
                        note_content = note_content.replace(old_fn, new_fn)
                    if note_description:
                        note_description = note_description.replace(old_fn, new_fn)
            # Track content bytes
            content_bytes = len(note_content.encode('utf-8')) if note_content else 0
            total_bytes_written += content_bytes + bytes_from_datauris + image_bytes
            new_note = Note(title=truncate(note.title, 200), content=note_content, description=note_description, user_id=receiver_user_id, folder_id=new_folder.id)
            db.session.add(new_note)

        for board in folder.boards:
            board_content = board.content
            board_description = getattr(board, 'description', None)
            bytes_from_datauris = 0
            if board_content:
                board_content, added = save_data_uri_images_for_user(board_content, receiver_user_id)
                bytes_from_datauris += added
            if board_description:
                board_description, added = save_data_uri_images_for_user(board_description, receiver_user_id)
                bytes_from_datauris += added
            image_filenames = set()
            if board_content:
                collect_images_from_content(board_content, image_filenames)
            if board_description:
                collect_images_from_content(board_description or '', image_filenames)
            mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
            if mapping:
                for old_fn, new_fn in mapping.items():
                    if board_content:
                        board_content = board_content.replace(old_fn, new_fn)
                    if board_description:
                        board_description = board_description.replace(old_fn, new_fn)
            # Track content bytes
            content_bytes = len(board_content.encode('utf-8')) if board_content else 0
            total_bytes_written += content_bytes + bytes_from_datauris + image_bytes
            new_board = Board(title=truncate(board.title, 100), content=board_content, description=board_description, user_id=receiver_user_id, folder_id=new_folder.id)
            db.session.add(new_board)

        for sub in folder.children:
            clone_folder_to_user(sub, new_folder.id)

        return new_folder

    cloned_root = clone_folder_to_user(original, target_parent_id)
    # Remove commit - let caller control transaction
    print(f"DEBUG: copy_folder_to_user - cloned folder {original_folder_id} to receiver {receiver_user_id} as folder {cloned_root.id if cloned_root else 'None'}, bytes={total_bytes_written}")
    return (cloned_root, total_bytes_written)


def copy_note_to_user(note_id, receiver_user_id, sender_username=None):
    """Copy a single note to receiver's path root/social/received/from_<sender> and return tuple (new_note, actual_bytes)"""
    note = Note.query.get(note_id)
    if not note or note.user_id != current_user.id:
        return (None, 0)
    receiver = User.query.get(receiver_user_id)
    if not receiver:
        return (None, 0)

    sender_segment = 'from_' + _sanitize_username_for_folder(sender_username or current_user.username or 'unknown')
    segments = ['social', 'received', sender_segment]
    target_parent_id = get_or_create_folder_path(receiver_user_id, segments)
    if not target_parent_id:
        print(f"ERROR: copy_note_to_user - failed to create/get folder path for receiver {receiver_user_id}")
        return (None, 0)

    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]

    total_bytes_written = 0
    # initialize content variables
    new_content = note.content
    new_description = getattr(note, 'description', None)
    # First convert inline base64 images in content/description to receiver's upload folder
    if new_content:
        new_content, added = save_data_uri_images_for_user(new_content, receiver_user_id)
        total_bytes_written += added
    if new_description:
        new_description, added = save_data_uri_images_for_user(new_description, receiver_user_id)
        total_bytes_written += added
    image_filenames = set()
    if new_content:
        collect_images_from_content(new_content, image_filenames)
    if new_description:
        collect_images_from_content(new_description or '', image_filenames)
    mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
    total_bytes_written += image_bytes
    print(f"DEBUG: copy_note_to_user - mapping for note {note.id} -> mapping: {mapping}, total_bytes={total_bytes_written}")
    if new_content:
        for old_fn, new_fn in mapping.items():
            new_content = new_content.replace(old_fn, new_fn)
    new_description = new_description
    if new_description:
        for old_fn, new_fn in mapping.items():
            new_description = new_description.replace(old_fn, new_fn)
    # Track content bytes
    content_bytes = len(new_content.encode('utf-8')) if new_content else 0
    total_bytes_written += content_bytes
    new_note = Note(title=truncate(note.title, 200), content=new_content, description=new_description, user_id=receiver_user_id, folder_id=target_parent_id)
    db.session.add(new_note)
    db.session.flush()  # Flush to get ID but don't commit
    print(f"DEBUG: copy_note_to_user - created new note {new_note.id} for receiver {receiver_user_id}, bytes={total_bytes_written}")
    return (new_note, total_bytes_written)


def copy_board_to_user(board_id, receiver_user_id, sender_username=None):
    """Copy a single board to receiver's path root/social/received/from_<sender> and return tuple (new_board, actual_bytes)"""
    board = Board.query.get(board_id)
    if not board or board.user_id != current_user.id:
        return (None, 0)
    receiver = User.query.get(receiver_user_id)
    if not receiver:
        return (None, 0)
    sender_segment = 'from_' + _sanitize_username_for_folder(sender_username or current_user.username or 'unknown')
    segments = ['social', 'received', sender_segment]
    target_parent_id = get_or_create_folder_path(receiver_user_id, segments)
    if not target_parent_id:
        print(f"ERROR: copy_board_to_user - failed to create/get folder path for receiver {receiver_user_id}")
        return (None, 0)
    def truncate(s, l):
        if not s:
            return ''
        try:
            s = str(s)
        except Exception:
            return ''
        return s if len(s) <= l else s[:l]
    total_bytes_written = 0
    # initialize content variables
    new_content = board.content
    new_description = getattr(board, 'description', None)
    # Save inline data URIs to receiver
    if new_content:
        new_content, added = save_data_uri_images_for_user(new_content, receiver_user_id)
        total_bytes_written += added
    if new_description:
        new_description, added = save_data_uri_images_for_user(new_description, receiver_user_id)
        total_bytes_written += added
    image_filenames = set()
    if new_content:
        collect_images_from_content(new_content, image_filenames)
    if new_description:
        collect_images_from_content(new_description or '', image_filenames)
    mapping, image_bytes = copy_images_to_user(image_filenames, receiver_user_id)
    total_bytes_written += image_bytes
    # Keep converted content in new_content
    if new_content:
        for old_fn, new_fn in mapping.items():
            new_content = new_content.replace(old_fn, new_fn)
    # Use the processed new_description variable
    if new_description:
        for old_fn, new_fn in mapping.items():
            new_description = new_description.replace(old_fn, new_fn)
    # Track content bytes
    content_bytes = len(new_content.encode('utf-8')) if new_content else 0
    total_bytes_written += content_bytes
    print(f"DEBUG: copy_board_to_user - mapping for board {board.id} -> mapping: {mapping}, total_bytes={total_bytes_written}")
    new_board = Board(title=truncate(board.title, 100), content=new_content, description=new_description, user_id=receiver_user_id, folder_id=target_parent_id)
    db.session.add(new_board)
    db.session.flush()  # Flush to get ID but don't commit
    print(f"DEBUG: copy_board_to_user - created new board {new_board.id} for receiver {receiver_user_id}, bytes={total_bytes_written}")
    return (new_board, total_bytes_written)
