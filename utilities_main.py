


######################################
# notes , whiteboard side utilities
######################################
from datetime import datetime
from extensions import db, login_manager
from flask import flash
import os   



# build and pass the breadcrumb
def build_folder_breadcrumb(folder):
    """Return list of folders from root -> ... -> current folder."""
    chain = []
    f = folder
    while f is not None:
        chain.append(f)
        f = f.parent  # assumes Folder.parent relationship
    chain.reverse()
    print(chain)
    return chain

# --- Data size cap helpers ---
def calculate_content_size(content):
    return len(content.encode('utf-8')) if content else 0

def calculate_image_size(file_path):
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0

# Check if guest user exceeds 50MB cap
def check_guest_limit(user, additional_size):
    if getattr(user, 'user_type', None) == 'guest':
        max_size = 50 * 1024 * 1024
        if (user.total_data_size or 0) + additional_size > max_size:
            flash("Data limit exceeded (50MB max for guests). Please delete some data or upgrade your account.", "danger")
            return False
    return True

# Update user's total data size
def update_user_data_size(user, delta):
    user.total_data_size = (user.total_data_size or 0) + delta
    db.session.commit()
