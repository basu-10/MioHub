#!/usr/bin/env python3
"""
Fix database column type for large content storage
"""
from flask_app import app
from extensions import db
from sqlalchemy import text

def check_and_fix_column():
    with app.app_context():
        # Check current column type and size
        result = db.session.execute(text("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'boards' 
            AND COLUMN_NAME = 'content'
        """))
        
        column_info = result.fetchone()
        if column_info:
            print(f"Current column info:")
            print(f"  Column: {column_info[0]}")
            print(f"  Data Type: {column_info[1]}")
            print(f"  Max Length: {column_info[2]}")
            print(f"  Column Type: {column_info[3]}")
        
        # Check MySQL limits
        result = db.session.execute(text("SHOW VARIABLES LIKE 'max_allowed_packet'"))
        max_packet = result.fetchone()
        if max_packet:
            print(f"\nMySQL max_allowed_packet: {max_packet[1]} bytes")
        
        # Check current database mode
        result = db.session.execute(text("SELECT @@sql_mode"))
        sql_mode = result.fetchone()
        if sql_mode:
            print(f"MySQL sql_mode: {sql_mode[0]}")
        
        # Try to modify the column to ensure it can handle large content
        try:
            print("\nTrying to modify column to LONGTEXT with explicit charset...")
            db.session.execute(text("""
                ALTER TABLE boards 
                MODIFY COLUMN content LONGTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
            """))
            db.session.commit()
            print("✅ Column modification successful!")
        except Exception as e:
            print(f"❌ Column modification failed: {e}")
            db.session.rollback()
        
        # Re-check column after modification
        result = db.session.execute(text("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'boards' 
            AND COLUMN_NAME = 'content'
        """))
        
        column_info = result.fetchone()
        if column_info:
            print(f"\nUpdated column info:")
            print(f"  Column: {column_info[0]}")
            print(f"  Data Type: {column_info[1]}")
            print(f"  Max Length: {column_info[2]}")
            print(f"  Column Type: {column_info[3]}")

if __name__ == '__main__':
    check_and_fix_column()