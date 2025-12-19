# folder_description_handlers.py
"""
Handlers for folder description functionality
Provides utility functions for creating and updating folders with descriptions
"""

from blueprints.p2.models import Folder, db
from flask_login import current_user
from datetime import datetime


def create_folder_with_description(name, description=None, parent_id=None):
    """
    Create a new folder with optional description
    
    Args:
        name (str): Folder name
        description (str, optional): Folder description
        parent_id (int, optional): Parent folder ID
        
    Returns:
        Folder: The created folder object
    """
    folder = Folder(
        name=name,
        description=description,
        user_id=current_user.id,
        parent_id=parent_id
    )
    db.session.add(folder)
    db.session.commit()
    return folder


def update_folder_details(folder_id, new_name=None, new_description=None):
    """
    Update folder name and/or description
    
    Args:
        folder_id (int): Folder ID to update
        new_name (str, optional): New folder name
        new_description (str, optional): New folder description
        
    Returns:
        bool: True if successful, False otherwise
    """
    folder = Folder.query.get(folder_id)
    
    if not folder or folder.user_id != current_user.id:
        return False
    
    if new_name is not None:
        folder.name = new_name
    
    if new_description is not None:
        folder.description = new_description
    
    folder.last_modified = datetime.utcnow()
    db.session.commit()
    return True


def get_folder_description(folder_id):
    """
    Get the description for a specific folder
    
    Args:
        folder_id (int): Folder ID
        
    Returns:
        str or None: Folder description if exists, None otherwise
    """
    folder = Folder.query.get(folder_id)
    
    if not folder or folder.user_id != current_user.id:
        return None
    
    return folder.description


def validate_folder_input(name, description=None):
    """
    Validate folder name and description input
    
    Args:
        name (str): Folder name
        description (str, optional): Folder description
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not name or not name.strip():
        return False, "Folder name cannot be empty"
    
    if len(name) > 100:
        return False, "Folder name cannot exceed 100 characters"
    
    if description and len(description) > 500:
        return False, "Folder description cannot exceed 500 characters"
    
    return True, None
