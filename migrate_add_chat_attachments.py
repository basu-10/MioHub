"""
Migration: Add chat_attachments table and session_folder_id to chat_sessions
Run: python migrate_add_chat_attachments.py
Created: December 30, 2024
"""
import env_loader

env_loader.load_env_from_wsgi()

from flask import Flask
from extensions import db
from sqlalchemy import text
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = config.get_database_uri()
db.init_app(app)

def run_migration():
    """Execute migration with proper error handling"""
    with app.app_context():
        inspector = db.inspect(db.engine)
        
        print("Starting chat attachments migration...")
        print("=" * 60)
        
        # 1. Create chat_attachments table
        if 'chat_attachments' not in inspector.get_table_names():
            print("\n[1/2] Creating chat_attachments table...")
            db.session.execute(text("""
                CREATE TABLE chat_attachments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id INT NOT NULL,
                    file_id INT NOT NULL,
                    summary_file_id INT NULL,
                    summary_status VARCHAR(20) DEFAULT 'pending',
                    summary_error TEXT NULL,
                    original_filename VARCHAR(500) NOT NULL,
                    file_type VARCHAR(50) NOT NULL,
                    file_size INT NOT NULL,
                    file_hash VARCHAR(64) NULL,
                    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    summarized_at DATETIME NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    INDEX idx_session (session_id),
                    INDEX idx_file_hash (file_hash),
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
                    FOREIGN KEY (summary_file_id) REFERENCES files(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            print("✓ Created chat_attachments table")
        else:
            print("\n[1/2] chat_attachments table already exists, skipping...")
        
        # 2. Add session_folder_id to chat_sessions
        columns = [col['name'] for col in inspector.get_columns('chat_sessions')]
        if 'session_folder_id' not in columns:
            print("\n[2/2] Adding session_folder_id to chat_sessions...")
            db.session.execute(text("""
                ALTER TABLE chat_sessions 
                ADD COLUMN session_folder_id INT NULL,
                ADD FOREIGN KEY (session_folder_id) REFERENCES folder(id) ON DELETE SET NULL;
            """))
            print("✓ Added session_folder_id to chat_sessions")
        else:
            print("\n[2/2] session_folder_id already exists in chat_sessions, skipping...")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("\nNew features enabled:")
        print("  • Chat attachments (PDF, DOCX, images, code files)")
        print("  • File deduplication via SHA256 hashing")
        print("  • AI summarization for uploaded documents")
        print("  • Session folder integration with MioSpace")


if __name__ == '__main__':
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
