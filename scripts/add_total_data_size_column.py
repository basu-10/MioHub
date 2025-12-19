import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from blueprints.p2.models import User, Note, Board
from extensions import db
import config

# Get database URL from config module
DATABASE_URL = config.get_database_uri()

def add_total_data_size_column():
    """Add total_data_size column to user table if it doesn't exist."""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :db_name
            AND TABLE_NAME = 'user'
            AND COLUMN_NAME = 'total_data_size'
        """), {"db_name": config.DB_NAME})

        if result.fetchone():
            print("Column 'total_data_size' already exists.")
            return

        # Add the column
        conn.execute(text("""
            ALTER TABLE user
            ADD COLUMN total_data_size BIGINT DEFAULT 0
        """))
        conn.commit()
        print("Column 'total_data_size' added successfully.")

def calculate_initial_sizes():
    """Calculate and set initial total_data_size for all users."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    users = session.query(User).all()
    for user in users:
        size = 0
        # Notes
        notes = session.query(Note).filter_by(user_id=user.id).all()
        for note in notes:
            size += len(note.content.encode('utf-8')) if note.content else 0
        # Boards
        boards = session.query(Board).filter_by(user_id=user.id).all()
        for board in boards:
            size += len(board.content.encode('utf-8')) if board.content else 0
        # Images
        image_dir = 'static/uploads/images'
        if os.path.exists(image_dir):
            for filename in os.listdir(image_dir):
                if filename.startswith(f"{user.id}_"):
                    filepath = os.path.join(image_dir, filename)
                    if os.path.isfile(filepath):
                        size += os.path.getsize(filepath)
        user.total_data_size = size
        session.commit()
        print(f"Calculated size for user {user.username}: {size} bytes")

    session.close()
    print("Initial sizes calculated for all users.")

if __name__ == "__main__":
    add_total_data_size_column()
    calculate_initial_sizes()