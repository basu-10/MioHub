import config
from sqlalchemy import create_engine, text

# Get database URL from config
DATABASE_URL = config.get_database_uri()

def add_created_at_columns():
    """Add created_at columns to folder, note, and board tables if they don't exist."""
    engine = create_engine(DATABASE_URL)

    tables_columns = [
        ('folder', 'created_at'),
        ('note', 'created_at'),
        ('boards', 'created_at')
    ]

    with engine.connect() as conn:
        for table_name, column_name in tables_columns:
            # Check if column exists
            result = conn.execute(text("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = :db_name
                AND TABLE_NAME = :table_name
                AND COLUMN_NAME = :column_name
            """), {"db_name": config.DB_NAME, "table_name": table_name, "column_name": column_name})

            if result.fetchone():
                print(f"Column '{column_name}' already exists in table '{table_name}'.")
                continue

            # Add the column with current timestamp as default
            conn.execute(text(f"""
                ALTER TABLE {table_name}
                ADD COLUMN {column_name} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            conn.commit()
            print(f"Column '{column_name}' added to table '{table_name}' successfully.")

if __name__ == "__main__":
    add_created_at_columns()