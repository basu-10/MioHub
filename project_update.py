"""Non-destructive DB bootstrap / repair.

Intended use:
- New server deployments / fresh DBs: create tables and seed minimum accounts.
- Existing DBs: ensure critical invariants exist (tables, at least one admin, at least one normal user,
  and root folders for the created/critical accounts) without modifying or deleting existing user data.

Invariants enforced:
- Tables exist (db.create_all is idempotent)
- At least one `User` with `user_type='admin'`
- At least one `User` with `user_type='user'`
- A `root` folder (Folder.is_root=True) exists for any accounts created here

This script does NOT drop tables/columns.
"""

import config
from sqlalchemy import inspect
from flask import Flask
from blueprints.p2.models import db, User, File, Folder
from werkzeug.security import generate_password_hash
from datetime import datetime


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
    print(f"🔑 Password reset for user: {user.username}")


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
        if not tables:
            print("✅ All tables created.")
        else:
            print("✅ Tables verified (create_all).")

        try:
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
                print(f"✅ Guest user created: {guest_username} (user_type=guest)")
            else:
                _ensure_root_folder_for_user(user_id=existing_guest.id)
                _reset_user_password_to_default(existing_guest)
                print(f"ℹ️ Guest user already exists: {existing_guest.username}")

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
                print(f"✅ Admin user created: {admin_username} (user_type=admin)")
            else:
                _ensure_root_folder_for_user(user_id=existing_admin_any.id)
                _reset_user_password_to_default(existing_admin_any)
                print(f"ℹ️ Admin user already exists (user_type=admin): {existing_admin_any.username}")

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
                print(f"✅ Normal user created: {normal_username} (user_type=user)")
            else:
                _ensure_root_folder_for_user(user_id=existing_normal_any.id)
                _reset_user_password_to_default(existing_normal_any)
                print(f"ℹ️ Normal user already exists (user_type=user): {existing_normal_any.username}")

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        

if __name__ == '__main__':
    init_app_and_tables()
