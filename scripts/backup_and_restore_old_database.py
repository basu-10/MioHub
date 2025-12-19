"""
Database backup and restore script
- Downloads complete dataset from MySQL database
- Creates backups in multiple formats: SQL dump, JSON, and CSV
- Packages backups into a single ZIP file
- Restores data from ZIP backups (SQL or JSON format)
"""
import mysql.connector
import json
import csv
import os
import config
from datetime import datetime
from pathlib import Path
import glob
import zipfile
import shutil

DB_HOST = config.DB_HOST
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_PORT = int(config.DB_PORT)

# Create backup directory with timestamp
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = Path(f"database_backups/backup_{TIMESTAMP}")

def create_backup_directories():
    """Create backup directory structure"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "json").mkdir(exist_ok=True)
    (BACKUP_DIR / "csv").mkdir(exist_ok=True)
    print(f"✓ Created backup directory: {BACKUP_DIR}")

def get_connection():
    """Create database connection"""
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )

def get_all_tables(cursor):
    """Get list of all tables in database"""
    cursor.execute("SHOW TABLES")
    return [table[0] for table in cursor.fetchall()]

def get_table_structure(cursor, table_name):
    """Get CREATE TABLE statement for a table"""
    cursor.execute(f"SHOW CREATE TABLE {table_name}")
    return cursor.fetchone()[1]

def backup_to_sql(conn, cursor, tables):
    """Create SQL dump file with all data"""
    print("\n=== Creating SQL Dump ===")
    sql_file = BACKUP_DIR / f"{DB_NAME}_backup.sql"
    
    with open(sql_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"-- MySQL Database Backup\n")
        f.write(f"-- Database: {DB_NAME}\n")
        f.write(f"-- Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"-- Host: {DB_HOST}:{DB_PORT}\n\n")
        f.write(f"SET FOREIGN_KEY_CHECKS=0;\n\n")
        
        for table in tables:
            print(f"  Dumping table: {table}")
            
            # Write CREATE TABLE statement
            create_stmt = get_table_structure(cursor, table)
            f.write(f"-- Table structure for {table}\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n")
            f.write(f"{create_stmt};\n\n")
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            row_count = cursor.fetchone()[0]
            
            if row_count > 0:
                # Write INSERT statements
                f.write(f"-- Data for table {table} ({row_count} rows)\n")
                cursor.execute(f"SELECT * FROM {table}")
                columns = [desc[0] for desc in cursor.description]
                
                # Fetch and write data in batches
                batch_size = 1000
                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    
                    for row in rows:
                        values = []
                        for val in row:
                            if val is None:
                                values.append('NULL')
                            elif isinstance(val, (int, float)):
                                values.append(str(val))
                            elif isinstance(val, datetime):
                                values.append(f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'")
                            elif isinstance(val, dict):
                                # Handle JSON columns
                                json_str = json.dumps(val).replace("'", "''")
                                values.append(f"'{json_str}'")
                            else:
                                # Escape strings
                                escaped = str(val).replace('\\', '\\\\').replace("'", "\\'")
                                values.append(f"'{escaped}'")
                        
                        insert_stmt = f"INSERT INTO `{table}` (`{'`, `'.join(columns)}`) VALUES ({', '.join(values)});\n"
                        f.write(insert_stmt)
                
                f.write("\n")
            else:
                f.write(f"-- No data in table {table}\n\n")
        
        f.write(f"SET FOREIGN_KEY_CHECKS=1;\n")
    
    file_size = os.path.getsize(sql_file) / 1024 / 1024  # MB
    print(f"✓ SQL dump created: {sql_file} ({file_size:.2f} MB)")
    return sql_file

def backup_to_json(cursor, tables):
    """Create JSON files for each table"""
    print("\n=== Creating JSON Backups ===")
    json_dir = BACKUP_DIR / "json"
    
    backup_data = {
        'backup_info': {
            'database': DB_NAME,
            'timestamp': datetime.now().isoformat(),
            'host': DB_HOST,
            'port': DB_PORT
        },
        'tables': {}
    }
    
    for table in tables:
        print(f"  Backing up table: {table}")
        cursor.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        # Convert rows to list of dictionaries
        table_data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # Convert datetime objects to ISO format strings
                if isinstance(value, datetime):
                    value = value.isoformat()
                # Convert bytes to string
                elif isinstance(value, bytes):
                    value = value.decode('utf-8', errors='ignore')
                row_dict[col] = value
            table_data.append(row_dict)
        
        backup_data['tables'][table] = {
            'row_count': len(table_data),
            'columns': columns,
            'data': table_data
        }
        
        # Save individual table JSON file
        table_file = json_dir / f"{table}.json"
        with open(table_file, 'w', encoding='utf-8') as f:
            json.dump(table_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"    ✓ {len(table_data)} rows saved to {table}.json")
    
    # Save combined backup file
    combined_file = BACKUP_DIR / "json" / "complete_backup.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False, default=str)
    
    file_size = os.path.getsize(combined_file) / 1024 / 1024  # MB
    print(f"✓ Combined JSON backup created: {combined_file} ({file_size:.2f} MB)")

def backup_to_csv(cursor, tables):
    """Create CSV files for each table"""
    print("\n=== Creating CSV Backups ===")
    csv_dir = BACKUP_DIR / "csv"
    
    for table in tables:
        print(f"  Backing up table: {table}")
        cursor.execute(f"SELECT * FROM {table}")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        if rows:
            csv_file = csv_dir / f"{table}.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)  # Header
                
                for row in rows:
                    # Convert each value to string, handling special types
                    cleaned_row = []
                    for val in row:
                        if val is None:
                            cleaned_row.append('')
                        elif isinstance(val, datetime):
                            cleaned_row.append(val.strftime('%Y-%m-%d %H:%M:%S'))
                        elif isinstance(val, (dict, list)):
                            cleaned_row.append(json.dumps(val))
                        elif isinstance(val, bytes):
                            cleaned_row.append(val.decode('utf-8', errors='ignore'))
                        else:
                            cleaned_row.append(str(val))
                    writer.writerow(cleaned_row)
            
            print(f"    ✓ {len(rows)} rows saved to {table}.csv")
        else:
            print(f"    ○ No data in {table}")

def create_metadata_file(tables, cursor):
    """Create metadata file with database statistics"""
    print("\n=== Creating Metadata File ===")
    
    metadata = {
        'backup_info': {
            'database': DB_NAME,
            'timestamp': datetime.now().isoformat(),
            'host': DB_HOST,
            'port': DB_PORT,
            'backup_directory': str(BACKUP_DIR)
        },
        'statistics': {}
    }
    
    total_rows = 0
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        total_rows += row_count
        
        # Get table size
        cursor.execute(f"""
            SELECT 
                ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
            FROM information_schema.TABLES 
            WHERE table_schema = '{DB_NAME}' 
            AND table_name = '{table}'
        """)
        size_result = cursor.fetchone()
        size_mb = size_result[0] if size_result and size_result[0] else 0
        
        metadata['statistics'][table] = {
            'row_count': row_count,
            'size_mb': float(size_mb) if size_mb else 0
        }
    
    metadata['statistics']['_total'] = {
        'total_tables': len(tables),
        'total_rows': total_rows
    }
    
    # Save metadata
    metadata_file = BACKUP_DIR / "backup_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Metadata saved: {metadata_file}")
    print(f"\nBackup Statistics:")
    print(f"  Total Tables: {len(tables)}")
    print(f"  Total Rows: {total_rows:,}")
    
    return metadata

def create_readme():
    """Create README file with backup instructions"""
    readme_content = f"""# Database Backup - {TIMESTAMP}

## Backup Information
- **Database**: {DB_NAME}
- **Host**: {DB_HOST}:{DB_PORT}
- **Backup Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Contents

### 1. SQL Dump (`{DB_NAME}_backup.sql`)
Complete SQL dump file that can be restored using:
```bash
mysql -u {DB_USER} -p {DB_NAME} < {DB_NAME}_backup.sql
```

### 2. JSON Backups (`json/` directory)
- `complete_backup.json` - Single file with all data
- Individual table JSON files for selective restoration

### 3. CSV Backups (`csv/` directory)
- Individual CSV files for each table
- Can be imported into Excel, Google Sheets, or other tools

### 4. Static Images (`static_images/` directory)
- All uploaded images from `static/uploads/images/`
- Will be restored to the same location during restore operation

### 5. Metadata (`backup_metadata.json`)
- Database statistics
- Table sizes and row counts
- Backup information

## Restoration Options

### Full Restore (SQL)
```bash
# Drop existing database (CAUTION!)
mysql -u {DB_USER} -p -e "DROP DATABASE IF EXISTS {DB_NAME}; CREATE DATABASE {DB_NAME};"

# Restore from backup
mysql -u {DB_USER} -p {DB_NAME} < {DB_NAME}_backup.sql
```

### Selective Table Restore (SQL)
Extract specific table from SQL dump and restore individually.

### JSON/CSV Import
Use the JSON or CSV files for custom import scripts or manual data recovery.

## Notes
- All text data is UTF-8 encoded
- JSON fields are properly escaped
- Datetime fields are in ISO format in JSON, MySQL format in SQL
- Foreign key checks are disabled during SQL restore

## Safety Recommendations
1. Store this backup in multiple locations
2. Test restoration on a separate database
3. Keep multiple backup versions
4. Compress large backups for storage efficiency
"""
    
    readme_file = BACKUP_DIR / "README.md"
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print(f"✓ README created: {readme_file}")

def backup_static_images():
    """Backup images from static/uploads/images directory"""
    print("\n=== Backing Up Static Images ===")
    
    # Define source and destination paths
    images_source = Path("static/uploads/images")
    images_dest = BACKUP_DIR / "static_images"
    
    if not images_source.exists():
        print(f"  ○ No images directory found at {images_source}")
        return 0
    
    # Create destination directory
    images_dest.mkdir(parents=True, exist_ok=True)
    
    # Copy all images
    image_files = list(images_source.glob('*'))
    image_count = 0
    total_size = 0
    
    for image_file in image_files:
        if image_file.is_file():
            dest_file = images_dest / image_file.name
            shutil.copy2(image_file, dest_file)
            image_count += 1
            total_size += image_file.stat().st_size
    
    total_size_mb = total_size / 1024 / 1024
    print(f"  ✓ Backed up {image_count} images ({total_size_mb:.2f} MB)")
    
    return image_count

def create_zip_backup():
    """Create a ZIP file containing all backup files and static images"""
    print("\n=== Creating ZIP Archive ===")
    
    # Define zip file path
    zip_filename = f"{DB_NAME}_backup_{TIMESTAMP}.zip"
    zip_path = Path("database_backups") / zip_filename
    
    # Ensure parent directory exists
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating {zip_filename}...")
    
    # Create ZIP file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        # Add all files from backup directory
        for file_path in BACKUP_DIR.rglob('*'):
            if file_path.is_file():
                # Get relative path from backup directory
                arcname = file_path.relative_to(BACKUP_DIR.parent)
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")
    
    # Get sizes
    original_size = sum(f.stat().st_size for f in BACKUP_DIR.rglob('*') if f.is_file())
    zip_size = zip_path.stat().st_size
    compression_ratio = (1 - zip_size / original_size) * 100 if original_size > 0 else 0
    
    print(f"\n✓ ZIP archive created: {zip_path}")
    print(f"  Original size: {original_size / 1024 / 1024:.2f} MB")
    print(f"  Compressed size: {zip_size / 1024 / 1024:.2f} MB")
    print(f"  Compression: {compression_ratio:.1f}%")
    
    return zip_path

def extract_zip_backup(zip_path):
    """Extract a ZIP backup to a temporary directory"""
    print(f"\n=== Extracting ZIP Archive ===")
    print(f"Source: {zip_path}")
    
    # Create extraction directory
    extract_dir = Path("database_backups") / f"temp_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting to: {extract_dir}")
    
    # Extract ZIP file
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        zipf.extractall(extract_dir)
        print(f"✓ Extracted {len(zipf.namelist())} files")
    
    # Find the backup directory inside extracted files
    # It should be named backup_TIMESTAMP
    backup_dirs = list(extract_dir.glob("backup_*"))
    
    if backup_dirs:
        actual_backup_dir = backup_dirs[0]
        print(f"✓ Found backup directory: {actual_backup_dir.name}")
        return actual_backup_dir
    else:
        # If no backup_* directory, the extract_dir itself is the backup
        print(f"✓ Using extraction directory as backup location")
        return extract_dir

def list_available_backups():
    """List all available backup directories and ZIP files"""
    backup_base = Path("database_backups")
    if not backup_base.exists():
        return []
    
    backups = []
    
    # Check for ZIP files
    for zip_file in sorted(backup_base.glob("*.zip"), reverse=True):
        if zip_file.is_file():
            # Extract timestamp from filename
            # Expected format: {DB_NAME}_backup_YYYYMMDD_HHMMSS.zip
            try:
                timestamp = zip_file.stem.split('_backup_')[1]
            except:
                timestamp = zip_file.stem
            
            # Try to read metadata from zip without extracting
            metadata = {}
            sql_file = None
            json_file = None
            
            try:
                with zipfile.ZipFile(zip_file, 'r') as zipf:
                    # Look for metadata file
                    for name in zipf.namelist():
                        if name.endswith('backup_metadata.json'):
                            with zipf.open(name) as f:
                                metadata = json.load(f)
                        elif name.endswith('.sql'):
                            sql_file = name
                        elif name.endswith('complete_backup.json'):
                            json_file = name
            except:
                pass
            
            backups.append({
                'path': zip_file,
                'timestamp': timestamp,
                'sql_file': sql_file,
                'json_file': json_file,
                'metadata': metadata,
                'type': 'zip',
                'size': zip_file.stat().st_size
            })
    
    # Check for backup directories (backward compatibility)
    for backup_dir in sorted(backup_base.glob("backup_*"), reverse=True):
        if backup_dir.is_dir():
            # Check if it has the main SQL file
            sql_files = list(backup_dir.glob("*.sql"))
            json_file = backup_dir / "json" / "complete_backup.json"
            
            if sql_files or json_file.exists():
                metadata_file = backup_dir / "backup_metadata.json"
                metadata = {}
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                
                # Calculate directory size
                dir_size = sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file())
                
                backups.append({
                    'path': backup_dir,
                    'timestamp': backup_dir.name.replace('backup_', ''),
                    'sql_file': sql_files[0] if sql_files else None,
                    'json_file': json_file if json_file.exists() else None,
                    'metadata': metadata,
                    'type': 'directory',
                    'size': dir_size
                })
    
    # Sort by timestamp (most recent first)
    backups.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return backups

def restore_from_sql(sql_file, conn, cursor):
    """Restore database from SQL dump file"""
    print(f"\n=== Restoring from SQL: {sql_file.name} ===")
    
    # Read SQL file
    print("Reading SQL file...")
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Split into individual statements
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        # Skip comments and empty lines
        if line.strip().startswith('--') or not line.strip():
            continue
        
        current_statement.append(line)
        
        # Check if statement is complete (ends with semicolon)
        if line.strip().endswith(';'):
            statement = '\n'.join(current_statement)
            if statement.strip():
                statements.append(statement)
            current_statement = []
    
    # Execute statements
    print(f"Executing {len(statements)} SQL statements...")
    success_count = 0
    error_count = 0
    
    for i, statement in enumerate(statements, 1):
        try:
            # Show progress every 100 statements
            if i % 100 == 0:
                print(f"  Progress: {i}/{len(statements)} statements...")
            
            cursor.execute(statement)
            conn.commit()
            success_count += 1
            
        except mysql.connector.Error as err:
            # Show first few errors, then suppress
            if error_count < 5:
                print(f"  Warning: Error in statement {i}: {err}")
            error_count += 1
    
    print(f"\n✓ Restoration completed!")
    print(f"  Successful: {success_count} statements")
    if error_count > 0:
        print(f"  Errors: {error_count} statements (some errors are normal for existing data)")
    
    return success_count, error_count

def restore_static_images(backup_path):
    """Restore images from backup to static/uploads/images directory"""
    print("\n=== Restoring Static Images ===")
    
    # Define source and destination paths
    images_source = backup_path / "static_images"
    images_dest = Path("static/uploads/images")
    
    if not images_source.exists():
        print(f"  ○ No static_images directory found in backup")
        return 0
    
    # Create destination directory if it doesn't exist
    images_dest.mkdir(parents=True, exist_ok=True)
    
    # Copy all images
    image_files = list(images_source.glob('*'))
    image_count = 0
    skipped_count = 0
    total_size = 0
    
    for image_file in image_files:
        if image_file.is_file():
            dest_file = images_dest / image_file.name
            
            # Check if file already exists
            if dest_file.exists():
                # Skip if same size (assume same file)
                if dest_file.stat().st_size == image_file.stat().st_size:
                    skipped_count += 1
                    continue
            
            shutil.copy2(image_file, dest_file)
            image_count += 1
            total_size += image_file.stat().st_size
    
    total_size_mb = total_size / 1024 / 1024
    print(f"  ✓ Restored {image_count} images ({total_size_mb:.2f} MB)")
    if skipped_count > 0:
        print(f"  ○ Skipped {skipped_count} existing images")
    
    return image_count

def restore_from_json(json_file, conn, cursor):
    """Restore database from JSON backup"""
    print(f"\n=== Restoring from JSON: {json_file.name} ===")
    
    # Read JSON file
    print("Reading JSON file...")
    with open(json_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    if 'tables' not in backup_data:
        print("✗ Invalid JSON backup format")
        return 0, 0
    
    tables = backup_data['tables']
    print(f"Found {len(tables)} tables to restore")
    
    total_rows = 0
    error_count = 0
    
    # Table restoration order (respecting foreign keys)
    table_order = ['user', 'folder', 'note', 'shared_note', 'boards', 
                   'chat_sessions', 'chat_messages', 'chat_memories', 'game_scores']
    
    # Add any tables not in the order list
    all_tables = list(tables.keys())
    for table in all_tables:
        if table not in table_order:
            table_order.append(table)
    
    for table_name in table_order:
        if table_name not in tables:
            continue
        
        table_data = tables[table_name]
        rows = table_data.get('data', [])
        
        if not rows:
            print(f"  ○ {table_name}: No data to restore")
            continue
        
        print(f"  Restoring {table_name}: {len(rows)} rows...")
        
        # Get column names
        columns = table_data.get('columns', list(rows[0].keys()) if rows else [])
        
        # Prepare INSERT statement
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        success = 0
        for row in rows:
            try:
                # Extract values in column order
                values = [row.get(col) for col in columns]
                cursor.execute(insert_sql, values)
                success += 1
            except mysql.connector.Error as err:
                if error_count < 5:
                    print(f"    Warning: Error inserting row: {err}")
                error_count += 1
        
        conn.commit()
        total_rows += success
        print(f"    ✓ Inserted {success} rows")
    
    print(f"\n✓ Restoration completed!")
    print(f"  Total rows restored: {total_rows}")
    if error_count > 0:
        print(f"  Errors: {error_count} (some errors are normal for duplicate keys)")
    
    return total_rows, error_count

def restore_database():
    """Main restore function"""
    print("="*60)
    print("DATABASE RESTORE")
    print("="*60)
    
    # List available backups
    backups = list_available_backups()
    
    if not backups:
        print("✗ No backups found in 'database_backups/' directory")
        print("\nPlease create a backup first or place backup files in:")
        print("  database_backups/{DB_NAME}_backup_YYYYMMDD_HHMMSS.zip")
        print("  OR")
        print("  database_backups/backup_YYYYMMDD_HHMMSS/ (directory)")
        return 1
    
    print(f"\nAvailable backups ({len(backups)} found):\n")
    
    for i, backup in enumerate(backups, 1):
        timestamp = backup['timestamp']
        try:
            formatted_time = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
        except:
            formatted_time = timestamp
        
        metadata = backup.get('metadata', {})
        stats = metadata.get('statistics', {}).get('_total', {})
        
        backup_type = backup.get('type', 'directory')
        size_mb = backup.get('size', 0) / 1024 / 1024
        
        print(f"{i}. Backup from {formatted_time} [{backup_type.upper()}]")
        if stats:
            print(f"   Tables: {stats.get('total_tables', 'N/A')} | Rows: {stats.get('total_rows', 'N/A'):,}")
        
        formats = []
        if backup['sql_file']:
            formats.append('SQL')
        if backup['json_file']:
            formats.append('JSON')
        print(f"   Formats: {', '.join(formats)}")
        print(f"   Size: {size_mb:.2f} MB")
        print(f"   Path: {backup['path']}")
        print()
    
    # Select backup
    try:
        choice = int(input(f"Select backup to restore (1-{len(backups)}), or 0 to cancel: "))
        if choice == 0:
            print("Restore cancelled.")
            return 0
        if choice < 1 or choice > len(backups):
            print("✗ Invalid selection")
            return 1
        
        selected_backup = backups[choice - 1]
    except (ValueError, KeyboardInterrupt):
        print("\n✗ Invalid input or cancelled")
        return 1
    
    # Extract ZIP if needed
    temp_dir = None
    backup_path = selected_backup['path']
    
    if selected_backup.get('type') == 'zip':
        print(f"\nSelected ZIP backup: {selected_backup['path'].name}")
        backup_path = extract_zip_backup(selected_backup['path'])
        temp_dir = backup_path  # Remember to clean up later
        
        # Update file paths after extraction
        sql_files = list(backup_path.glob("*.sql"))
        json_file = backup_path / "json" / "complete_backup.json"
        
        selected_backup['sql_file'] = sql_files[0] if sql_files else None
        selected_backup['json_file'] = json_file if json_file.exists() else None
    else:
        print(f"\nSelected backup: {selected_backup['path'].name}")
    
    # Select format
    print("\nAvailable formats:")
    
    format_options = []
    if selected_backup['sql_file']:
        format_options.append(('SQL', selected_backup['sql_file']))
        print(f"1. SQL dump (recommended for full restore)")
    if selected_backup['json_file']:
        idx = len(format_options) + 1
        format_options.append(('JSON', selected_backup['json_file']))
        print(f"{idx}. JSON (selective restore, slower)")
    
    try:
        format_choice = int(input(f"\nSelect format (1-{len(format_options)}), or 0 to cancel: "))
        if format_choice == 0:
            print("Restore cancelled.")
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
                print(f"✓ Cleaned up temporary files")
            return 0
        if format_choice < 1 or format_choice > len(format_options):
            print("✗ Invalid selection")
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)
            return 1
        
        format_type, restore_file = format_options[format_choice - 1]
    except (ValueError, KeyboardInterrupt):
        print("\n✗ Invalid input or cancelled")
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
        return 1
    
    # Final confirmation
    print("\n" + "="*60)
    print("⚠ WARNING: RESTORE OPERATION")
    print("="*60)
    print(f"Database: {DB_NAME}")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"Backup: {selected_backup['path'].name}")
    print(f"Format: {format_type}")
    print("\nThis will:")
    print("  - INSERT data from backup into your database")
    print("  - May cause duplicate key errors if data already exists")
    print("  - Recommended: Backup current database first!")
    print("="*60)
    
    confirm = input("\nType 'RESTORE' to proceed: ")
    if confirm != 'RESTORE':
        print("Restore cancelled.")
        return 0
    
    try:
        # Connect to database
        print("\n✓ Connecting to database...")
        conn = get_connection()
        cursor = conn.cursor()
        
        # Disable foreign key checks during restore
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        conn.commit()
        
        # Restore based on format
        if format_type == 'SQL':
            success, errors = restore_from_sql(restore_file, conn, cursor)
        else:
            success, errors = restore_from_json(restore_file, conn, cursor)
        
        # Re-enable foreign key checks
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Restore static images
        images_restored = restore_static_images(backup_path)
        
        print("\n" + "="*60)
        print("✓ RESTORE COMPLETED")
        print("="*60)
        print(f"Database items restored: {success}")
        print(f"Images restored: {images_restored}")
        
        # Clean up temporary extraction directory
        if temp_dir and temp_dir.exists():
            print("\nCleaning up temporary files...")
            shutil.rmtree(temp_dir)
            print("✓ Temporary files removed")
        
        return 0
        
    except mysql.connector.Error as err:
        print(f"\n✗ DATABASE ERROR: {err}")
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
        return 1

def backup_database():
    """Main backup function"""
    print("="*60)
    print("DATABASE BACKUP")
    print("="*60)
    print(f"Database: {DB_NAME}")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print(f"User: {DB_USER}")
    print(f"Timestamp: {TIMESTAMP}")
    print("="*60)
    
    try:
        # Create backup directories
        create_backup_directories()
        
        # Connect to database
        print("\n✓ Connecting to database...")
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get all tables
        tables = get_all_tables(cursor)
        table_names = ', '.join(str(t) for t in tables)
        print(f"✓ Found {len(tables)} tables: {table_names}")
        
        # Create backups in different formats
        backup_to_sql(conn, cursor, tables)
        backup_to_json(cursor, tables)
        backup_to_csv(cursor, tables)
        
        # Create metadata
        metadata = create_metadata_file(tables, cursor)
        
        # Backup static images
        images_count = backup_static_images()
        
        # Create README
        create_readme()
        
        # Close connection
        cursor.close()
        conn.close()
        
        # Calculate total backup size
        total_size = sum(f.stat().st_size for f in BACKUP_DIR.rglob('*') if f.is_file())
        total_size_mb = total_size / 1024 / 1024
        
        # Create ZIP archive
        zip_path = create_zip_backup()
        zip_size_mb = zip_path.stat().st_size / 1024 / 1024
        
        print("\n" + "="*60)
        print("✓ BACKUP COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"Backup Directory: {BACKUP_DIR.absolute()}")
        print(f"Directory Size: {total_size_mb:.2f} MB")
        print(f"Total Files: {sum(1 for _ in BACKUP_DIR.rglob('*') if _.is_file())}")
        print(f"\nZIP Archive: {zip_path.absolute()}")
        print(f"ZIP Size: {zip_size_mb:.2f} MB")
        print("\nBackup contains:")
        print(f"  - SQL dump for full restoration")
        print(f"  - JSON files for programmatic access")
        print(f"  - CSV files for spreadsheet import")
        print(f"  - Static images ({images_count} files)")
        print(f"  - Metadata and README documentation")
        print("\n💡 You can now use the ZIP file for easy backup/restore")
        print("="*60)
        
        # Ask if user wants to delete the uncompressed directory
        print("\nThe original backup directory is still present.")
        cleanup = input("Delete uncompressed backup directory? (yes/no): ")
        if cleanup.lower() in ['yes', 'y']:
            shutil.rmtree(BACKUP_DIR)
            print(f"✓ Removed directory: {BACKUP_DIR}")
        else:
            print(f"✓ Kept directory: {BACKUP_DIR}")
        
        return 0
        
    except mysql.connector.Error as err:
        print(f"\n✗ DATABASE ERROR: {err}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

def restore_from_uploaded_zip(zip_path_str):
    """Restore database from an uploaded ZIP file (for web interface)"""
    print(f"\n=== Restoring from Uploaded ZIP ===")
    zip_path = Path(zip_path_str)
    
    if not zip_path.exists():
        print(f"✗ ZIP file not found: {zip_path}")
        return False
    
    temp_dir = None
    try:
        # Extract ZIP
        backup_path = extract_zip_backup(zip_path)
        temp_dir = backup_path
        
        # Find SQL or JSON file
        sql_files = list(backup_path.glob("*.sql"))
        json_file = backup_path / "json" / "complete_backup.json"
        
        if not sql_files and not json_file.exists():
            print("✗ No valid backup files found in ZIP")
            return False
        
        # Prefer SQL for faster restore
        restore_file = sql_files[0] if sql_files else json_file
        format_type = 'SQL' if sql_files else 'JSON'
        
        print(f"✓ Found {format_type} backup: {restore_file.name}")
        
        # Connect and restore
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        conn.commit()
        
        if format_type == 'SQL':
            success, errors = restore_from_sql(restore_file, conn, cursor)
        else:
            success, errors = restore_from_json(restore_file, conn, cursor)
        
        cursor.execute("SET FOREIGN_KEY_CHECKS=1")
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Restore static images
        images_restored = restore_static_images(backup_path)
        
        print(f"\n✓ Restore completed: {success} items restored, {images_restored} images restored")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Restore failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir)
            print("✓ Cleaned up temporary files")

def main():
    """Main menu function"""
    print("\n" + "="*60)
    print("DATABASE BACKUP & RESTORE UTILITY")
    print("="*60)
    print(f"Database: {DB_NAME}")
    print(f"Host: {DB_HOST}:{DB_PORT}")
    print("="*60)
    print("\nWhat would you like to do?\n")
    print("1. Backup database (create new ZIP backup)")
    print("2. Restore database (from existing backup)")
    print("3. List available backups")
    print("4. Restore from custom ZIP file path")
    print("0. Exit")
    print()
    
    try:
        choice = input("Enter your choice (0-4): ").strip()
        
        if choice == '1':
            print("\n⚠ This will create a complete backup of your database.")
            print(f"⚠ Backup will be saved to: database_backups/{DB_NAME}_backup_{TIMESTAMP}.zip")
            response = input("\nProceed with backup? (yes/no): ")
            
            if response.lower() in ['yes', 'y']:
                return backup_database()
            else:
                print("Backup cancelled.")
                return 0
        
        elif choice == '2':
            return restore_database()
        
        elif choice == '3':
            # Just list backups
            backups = list_available_backups()
            if not backups:
                print("\n✗ No backups found in 'database_backups/' directory")
            else:
                print(f"\nFound {len(backups)} backup(s):\n")
                for i, backup in enumerate(backups, 1):
                    timestamp = backup['timestamp']
                    try:
                        formatted_time = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
                    except:
                        formatted_time = timestamp
                    
                    metadata = backup.get('metadata', {})
                    stats = metadata.get('statistics', {}).get('_total', {})
                    backup_type = backup.get('type', 'directory')
                    size_mb = backup.get('size', 0) / 1024 / 1024
                    
                    print(f"{i}. {formatted_time} [{backup_type.upper()}]")
                    if stats:
                        print(f"   Tables: {stats.get('total_tables', 'N/A')} | Rows: {stats.get('total_rows', 'N/A'):,}")
                    print(f"   Size: {size_mb:.2f} MB")
                    print(f"   Path: {backup['path']}")
                    print()
            return 0
        
        elif choice == '4':
            # Restore from custom ZIP path
            print("\n=== Restore from Custom ZIP File ===")
            zip_path = input("Enter full path to ZIP file: ").strip().strip('"').strip("'")
            
            if not zip_path:
                print("✗ No path provided")
                return 1
            
            print(f"\n⚠ WARNING: This will restore data into {DB_NAME}")
            confirm = input("Type 'RESTORE' to proceed: ")
            
            if confirm != 'RESTORE':
                print("Restore cancelled.")
                return 0
            
            success = restore_from_uploaded_zip(zip_path)
            return 0 if success else 1
        
        elif choice == '0':
            print("Exiting.")
            return 0
        
        else:
            print("✗ Invalid choice. Please enter 0-4.")
            return 1
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 0
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
