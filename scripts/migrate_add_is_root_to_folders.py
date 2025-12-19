"""
Migration: add is_root flag and root_key uniqueness for Folder home directories.
- Adds columns is_root (bool) and root_key (generated) if missing.
- Backfills a single root per user (first parentless folder) when none flagged.
- Adds a unique index on root_key and a check constraint to keep root parentless.
"""
from flask import Flask
from sqlalchemy import inspect, text

import config
from extensions import db
from blueprints.p2.models import User, Folder

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
db.init_app(app)


def column_exists(inspector, table, column):
    return any(col['name'] == column for col in inspector.get_columns(table))


def index_exists(inspector, table, index_name):
    return any(idx['name'] == index_name for idx in inspector.get_indexes(table))


def constraint_exists(inspector, table, constraint_name):
    return any(ck['name'] == constraint_name for ck in inspector.get_check_constraints(table))


with app.app_context():
    inspector = inspect(db.engine)

    # 1) Add is_root column if missing
    if not column_exists(inspector, 'folder', 'is_root'):
        db.session.execute(text("""
            ALTER TABLE folder
            ADD COLUMN is_root TINYINT(1) NOT NULL DEFAULT 0 AFTER parent_id
        """))
        print("Added column folder.is_root")

    # 2) Add generated root_key column if missing
    inspector = inspect(db.engine)
    if not column_exists(inspector, 'folder', 'root_key'):
        db.session.execute(text("""
            ALTER TABLE folder
            ADD COLUMN root_key INT GENERATED ALWAYS AS (CASE WHEN is_root THEN user_id ELSE NULL END) STORED
        """))
        print("Added column folder.root_key")

    # 3) Backfill: mark one root per user if none flagged
    inspector = inspect(db.engine)
    users = db.session.query(User.id).all()
    backfilled = 0
    for (user_id,) in users:
        existing_root = Folder.query.filter_by(user_id=user_id, is_root=True).first()
        if existing_root:
            continue
        candidate = (
            Folder.query
            .filter_by(user_id=user_id, parent_id=None)
            .order_by(Folder.id.asc())
            .first()
        )
        if candidate:
            candidate.is_root = True
            backfilled += 1
    if backfilled:
        db.session.commit()
        print(f"Backfilled is_root for {backfilled} users")

    # 4) Add unique index on root_key (allows multiple NULLs)
    inspector = inspect(db.engine)
    if not index_exists(inspector, 'folder', 'uq_folder_root_key'):
        db.session.execute(text("""
            CREATE UNIQUE INDEX uq_folder_root_key ON folder (root_key)
        """))
        print("Created unique index uq_folder_root_key on folder.root_key")

    # 5) Add check constraint to ensure roots stay parentless
    inspector = inspect(db.engine)
    if not constraint_exists(inspector, 'folder', 'ck_folder_root_parent_null'):
        db.session.execute(text("""
            ALTER TABLE folder
            ADD CONSTRAINT ck_folder_root_parent_null CHECK (NOT is_root OR parent_id IS NULL)
        """))
        print("Added check constraint ck_folder_root_parent_null")

    db.session.commit()
    print("Migration completed.")
