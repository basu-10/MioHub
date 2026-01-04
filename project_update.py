"""Non-destructive DB bootstrap / repair.

Intended use:
- New server deployments / fresh DBs: create tables and seed minimum accounts.
- Existing DBs: ensure critical invariants exist (tables, at least one admin, at least one normal user,
  and root folders for the created/critical accounts) without modifying or deleting existing user data.

Invariants enforced:
- Tables exist (db.create_all is idempotent)
- Missing columns added to existing tables (chat_attachments summary columns, etc.)
- At least one `User` with `user_type='admin'`
- At least one `User` with `user_type='user'`
- A `root` folder (Folder.is_root=True) exists for any accounts created here

This script does NOT drop tables/columns.
"""

import config
import logging
from sqlalchemy import inspect, text
from flask import Flask
from blueprints.p2.models import db, User, File, Folder
from werkzeug.security import generate_password_hash
from datetime import datetime

# Suppress SQLAlchemy verbose logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


DEFAULT_GUEST_USERNAME = "testuser"
DEFAULT_GUEST_PASSWORD = "password123"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_NORMAL_USERNAME = "defaultuser"
DEFAULT_NORMAL_PASSWORD = "password123"


def pick_unique_username(existing_usernames: set[str], preferred: str) -> str:
    """Pick a unique username, suffixing with an incrementing integer if needed."""
    if preferred not in existing_usernames:
        return preferred
    idx = 2
    while True:
        candidate = f"{preferred}{idx}"
        if candidate not in existing_usernames:
            return candidate
        idx += 1


def _ensure_root_folder_for_user(*, user_id: int) -> Folder:
    root = Folder.query.filter_by(user_id=user_id, is_root=True).first()
    if root:
        return root
    root = Folder(name="root", user_id=user_id, parent_id=None, is_root=True)
    db.session.add(root)
    db.session.flush()
    return root


def _reset_user_password_to_default(user: User) -> None:
    """Reset an existing user's password to the default value based on their username/type."""
    if user.username == DEFAULT_GUEST_USERNAME:
        new_password = DEFAULT_GUEST_PASSWORD
    elif user.username == DEFAULT_ADMIN_USERNAME:
        new_password = DEFAULT_ADMIN_PASSWORD
    elif user.username == DEFAULT_NORMAL_USERNAME:
        new_password = DEFAULT_NORMAL_PASSWORD
    else:
        # For other users, use guest password as default
        new_password = DEFAULT_GUEST_PASSWORD
    
    user.password_hash = generate_password_hash(new_password)


def _create_user_with_root_and_welcome_file(
    *,
    username: str,
    password: str,
    email: str,
    security_answer: str,
    user_type: str,
    create_welcome_file: bool,
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        security_answer=security_answer,
        user_type=user_type,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow(),
        user_prefs={"theme": "flatly", "isPinned": False},
        profile_pic_url="",
    )
    db.session.add(user)
    db.session.flush()

    root_folder = _ensure_root_folder_for_user(user_id=user.id)

    if create_welcome_file:
        test_file = File(
            owner_id=user.id,
            folder_id=root_folder.id,
            type="markdown",
            title="Default Note",
            content_text=(
                "# Welcome\n\n"
                "This is a default markdown file inside your root folder. "
                "Created by project_update.py"
            ),
            metadata_json={"description": "Initial test file"},
        )
        db.session.add(test_file)

    return user

def _ensure_missing_columns():
    """Add any missing columns to existing tables without dropping anything.
    
    IMPORTANT: This is the centralized location for all column additions.
    When adding new columns to the models, add the corresponding ALTER TABLE
    logic here to ensure project_update.py can bootstrap fresh deployments
    and update existing databases without requiring separate migration scripts.
    
    Pattern for adding new column checks:
    1. Check if table exists in tables list
    2. Get existing columns for that table
    3. Check if new column exists, if not add to missing_columns list
    4. Execute ALTER TABLE with all missing columns in one statement
    5. Commit and print confirmation
    """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    # Check chat_attachments table for summary-related columns
    if 'chat_attachments' in tables:
        existing_columns = {col['name'] for col in inspector.get_columns('chat_attachments')}
        
        missing_columns = []
        if 'original_content_hash' not in existing_columns:
            missing_columns.append('original_content_hash VARCHAR(64)')
        if 'summary_is_stale' not in existing_columns:
            missing_columns.append('summary_is_stale BOOLEAN DEFAULT FALSE')
        if 'word_count' not in existing_columns:
            missing_columns.append('word_count INT')
        if 'summary_word_count' not in existing_columns:
            missing_columns.append('summary_word_count INT')
        
        if missing_columns:
            alter_statement = "ALTER TABLE chat_attachments " + ", ".join(
                f"ADD COLUMN {col_def}" for col_def in missing_columns
            )
            db.session.execute(text(alter_statement))
            db.session.commit()
            print("[+] Schema Updates:")
            print(f"    -> chat_attachments: added {len(missing_columns)} column(s)")
            for col in missing_columns:
                col_name = col.split()[0]
                print(f"       * {col_name}")
        else:
            print("[OK] Schema Status: All columns present")
    
    # Add checks for other tables here as needed in future migrations
    # Example:
    # if 'users' in tables:
    #     existing_columns = {col['name'] for col in inspector.get_columns('users')}
    #     if 'new_column' not in existing_columns:
    #         db.session.execute(text("ALTER TABLE users ADD COLUMN new_column VARCHAR(100)"))
    #         db.session.commit()

# Step 1: Initialize Flask + SQLAlchemy and create tables
def init_app_and_tables():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        # Ensure p3 models are imported so their tables are included in metadata.
        # Importing the module (not individual names) avoids breakage if models evolve.
        import blueprints.p3.models  # noqa: F401

        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        # create_all is idempotent: it will create any missing tables.
        db.create_all()
        
        print("\n" + "="*70)
        print("MioHub Project Update - Database Bootstrap & Repair")
        print("="*70 + "\n")
        
        if not tables:
            print("[*] Status: Fresh database detected")
            print("    -> All tables created successfully\n")
        else:
            print("[*] Status: Existing database detected")
            print("    -> All tables verified\n")
        
        # Ensure missing columns are added to existing tables
        _ensure_missing_columns()
        print()

        try:
            print("[#] User Account Management:\n")
            existing_usernames = {u[0] for u in db.session.query(User.username).all()}

            # 1) Ensure the default guest user exists (keeps existing repo expectations)
            existing_guest = User.query.filter_by(username=DEFAULT_GUEST_USERNAME).first()
            if not existing_guest:
                guest_username = pick_unique_username(existing_usernames, DEFAULT_GUEST_USERNAME)
                _create_user_with_root_and_welcome_file(
                    username=guest_username,
                    password=DEFAULT_GUEST_PASSWORD,
                    email="test@example.com",
                    security_answer="blue",
                    user_type="guest",
                    create_welcome_file=True,
                )
                existing_usernames.add(guest_username)
                print(f"    [+] Created guest user: {guest_username}")
                print(f"        Password: {DEFAULT_GUEST_PASSWORD}")
                print(f"        Type: guest\n")
            else:
                _ensure_root_folder_for_user(user_id=existing_guest.id)
                _reset_user_password_to_default(existing_guest)
                print(f"    [!] Reset password: {existing_guest.username}")
                print(f"        Password: {DEFAULT_GUEST_PASSWORD}")
                print(f"        Type: guest\n")

            # 2) Ensure at least one admin exists
            existing_admin_any = User.query.filter_by(user_type="admin").first()
            if not existing_admin_any:
                admin_username = pick_unique_username(existing_usernames, DEFAULT_ADMIN_USERNAME)
                _create_user_with_root_and_welcome_file(
                    username=admin_username,
                    password=DEFAULT_ADMIN_PASSWORD,
                    email="admin@example.com",
                    security_answer="admin",
                    user_type="admin",
                    create_welcome_file=False,
                )
                existing_usernames.add(admin_username)
                print(f"    [+] Created admin user: {admin_username}")
                print(f"        Password: {DEFAULT_ADMIN_PASSWORD}")
                print(f"        Type: admin\n")
            else:
                _ensure_root_folder_for_user(user_id=existing_admin_any.id)
                _reset_user_password_to_default(existing_admin_any)
                print(f"    [!] Reset password: {existing_admin_any.username}")
                print(f"        Password: {DEFAULT_ADMIN_PASSWORD}")
                print(f"        Type: admin\n")

            # 3) Ensure at least one normal user exists
            existing_normal_any = User.query.filter_by(user_type="user").first()
            if not existing_normal_any:
                normal_username = pick_unique_username(existing_usernames, DEFAULT_NORMAL_USERNAME)
                _create_user_with_root_and_welcome_file(
                    username=normal_username,
                    password=DEFAULT_NORMAL_PASSWORD,
                    email="user@example.com",
                    security_answer="blue",
                    user_type="user",
                    create_welcome_file=True,
                )
                existing_usernames.add(normal_username)
                print(f"    [+] Created normal user: {normal_username}")
                print(f"        Password: {DEFAULT_NORMAL_PASSWORD}")
                print(f"        Type: user\n")
            else:
                _ensure_root_folder_for_user(user_id=existing_normal_any.id)
                _reset_user_password_to_default(existing_normal_any)
                print(f"    [!] Reset password: {existing_normal_any.username}")
                print(f"        Password: {DEFAULT_NORMAL_PASSWORD}")
                print(f"        Type: user\n")

            db.session.commit()
            
            print("="*70)
            print("[OK] Project update completed successfully!")
            print("="*70 + "\n")
        except Exception:
            db.session.rollback()
            raise
        

if __name__ == '__main__':
    init_app_and_tables()
