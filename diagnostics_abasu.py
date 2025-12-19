"""
Newbii Diagnostic & Database Management Tool
=============================================
Menu-based tool for system diagnostics and database operations on Hetzner cloud deployment.

Usage: python scripts/diagnostics.py
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import platform

# Add parent directory to path for imports
BASE_DIR = Path(__file__).resolve().parent
# Session-scoped working directory that can be updated via Settings
SESSION_BASE_DIR = BASE_DIR
sys.path.insert(0, str(BASE_DIR.parent))


def ensure_working_directory():
    """Ensure the script runs from its own directory (Explorer double-click fix)."""
    global SESSION_BASE_DIR
    try:
        os.chdir(SESSION_BASE_DIR)
    except Exception:
        # If changing directories fails, continue with current cwd.
        pass


def set_base_directory():
    """Allow the user to set a session-only base directory for all operations."""
    global SESSION_BASE_DIR

    print_header("SET BASE DIRECTORY")
    print_info(f"Current base directory: {SESSION_BASE_DIR}")

    new_path_input = input(f"{Colors.OKCYAN}Enter new base directory (blank to keep current): {Colors.ENDC}").strip()

    if not new_path_input:
        print_info("Base directory unchanged.")
        return

    # Resolve relative paths against current working directory for convenience
    new_path = Path(new_path_input).expanduser().resolve()

    if not new_path.exists() or not new_path.is_dir():
        print_error(f"Invalid directory: {new_path}")
        return

    try:
        os.chdir(new_path)
        SESSION_BASE_DIR = new_path
        print_success(f"Session base directory set to: {SESSION_BASE_DIR}")
    except Exception as e:
        print_error(f"Failed to set base directory: {str(e)}")


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_status_bar():
    """Print status bar with important system information"""
    try:
        current_dir = Path.cwd()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        python_ver = platform.python_version()
        
        # Get disk usage if psutil is available
        disk_info = ""
        try:
            import psutil
            disk = psutil.disk_usage(str(current_dir))
            disk_free_gb = disk.free / (1024**3)
            disk_info = f" | Disk Free: {disk_free_gb:.1f} GB"
        except:
            pass
        
        print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
        print(f"{Colors.BOLD}📁 Folder:{Colors.ENDC} {current_dir}")
        print(f"{Colors.BOLD}🕒 Time:{Colors.ENDC} {current_time} | {Colors.BOLD}🐍 Python:{Colors.ENDC} {python_ver}{disk_info}")
        print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
    except Exception as e:
        print_warning(f"Error displaying status bar: {str(e)}")


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def find_sqlite_databases(root_path: Path = None) -> List[Dict]:
    """
    Recursively find all SQLite database files from root_path.
    
    Returns:
        List of dicts with db info: {path, name, size, tables}
    """
    if root_path is None:
        root_path = Path.cwd()
    
    databases = []
    
    print_info(f"Scanning for SQLite databases from: {root_path}")
    
    # Common SQLite extensions
    extensions = ['.db', '.sqlite', '.sqlite3', '.db3']
    
    for ext in extensions:
        for db_file in root_path.rglob(f'*{ext}'):
            try:
                # Verify it's actually a SQLite database
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Get tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Get columns for each table
                table_info = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    # Get row count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    row_count = cursor.fetchone()[0]
                    
                    table_info[table] = {
                        'columns': columns,
                        'row_count': row_count
                    }
                
                conn.close()
                
                databases.append({
                    'path': str(db_file),
                    'name': db_file.name,
                    'size': db_file.stat().st_size,
                    'tables': table_info
                })
                
            except sqlite3.Error:
                # Not a valid SQLite database
                continue
            except Exception as e:
                print_warning(f"Error reading {db_file.name}: {str(e)}")
                continue
    
    return databases


def display_database_structure(databases: List[Dict]):
    """Display all found databases with their structure"""
    if not databases:
        print_warning("No SQLite databases found!")
        return
    
    print_header(f"Found {len(databases)} SQLite Database(s)")
    
    for idx, db in enumerate(databases, 1):
        size_mb = db['size'] / (1024 * 1024)
        print(f"\n{Colors.BOLD}[{idx}] {db['name']}{Colors.ENDC}")
        print(f"    Path: {db['path']}")
        print(f"    Size: {size_mb:.2f} MB")
        print(f"    Tables: {len(db['tables'])}")
        
        for table_name, table_data in db['tables'].items():
            print(f"\n    📊 Table: {Colors.OKBLUE}{table_name}{Colors.ENDC} ({table_data['row_count']} rows)")
            print(f"       Columns: {', '.join(table_data['columns'])}")


def get_first_n_rows(db_path: str, table: str, n: int = 5):
    """Get first N rows from a table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT * FROM {table} LIMIT {n}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        conn.close()
        
        return columns, rows
    except Exception as e:
        print_error(f"Error fetching rows: {str(e)}")
        return None, None


def get_last_n_rows(db_path: str, table: str, n: int = 5):
    """Get last N rows from a table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total = cursor.fetchone()[0]
        
        # Get last N rows
        offset = max(0, total - n)
        cursor.execute(f"SELECT * FROM {table} LIMIT {n} OFFSET {offset}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        conn.close()
        
        return columns, rows
    except Exception as e:
        print_error(f"Error fetching rows: {str(e)}")
        return None, None


def search_by_column(db_path: str, table: str, column: str, search_value: str, fuzzy: bool = False):
    """Search for rows where column matches search_value with fuzzy matching options"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        if fuzzy:
            # Fuzzy search: case-insensitive, space-insensitive
            # Remove spaces and make case-insensitive for better matching
            search_terms = search_value.lower().split()
            
            # Build query with multiple LIKE conditions for each term
            conditions = []
            params = []
            for term in search_terms:
                conditions.append(f"LOWER({column}) LIKE ?")
                params.append(f'%{term}%')
            
            query = f"SELECT * FROM {table} WHERE {' AND '.join(conditions)}"
            cursor.execute(query, params)
        else:
            # Standard search with LIKE for partial matches
            query = f"SELECT * FROM {table} WHERE {column} LIKE ?"
            cursor.execute(query, (f'%{search_value}%',))
        
        rows = cursor.fetchall()
        
        conn.close()
        
        return columns, rows
    except Exception as e:
        print_error(f"Error searching: {str(e)}")
        return None, None


def search_all_columns(db_path: str, table: str, search_value: str):
    """Search for rows where ANY column matches search_value"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Build query to search across all columns
        search_terms = search_value.lower().split()
        conditions = []
        params = []
        
        for col in columns:
            for term in search_terms:
                conditions.append(f"LOWER(CAST({col} AS TEXT)) LIKE ?")
                params.append(f'%{term}%')
        
        query = f"SELECT * FROM {table} WHERE {' OR '.join(conditions)}"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        conn.close()
        
        return columns, rows
    except Exception as e:
        print_error(f"Error searching: {str(e)}")
        return None, None


def display_table_data(columns: List[str], rows: List[Tuple]):
    """Display table data in a formatted way"""
    if not rows:
        print_warning("No data found!")
        return
    
    # Calculate column widths
    col_widths = [len(col) for col in columns]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))
    
    # Print header
    header = " | ".join([col.ljust(col_widths[i]) for i, col in enumerate(columns)])
    print(f"\n{Colors.BOLD}{header}{Colors.ENDC}")
    print("-" * len(header))
    
    # Print rows (limit display for very wide tables)
    for row in rows:
        row_str = " | ".join([str(val).ljust(col_widths[i]) for i, val in enumerate(row)])
        print(row_str)
    
    print(f"\n{Colors.OKGREEN}Total rows: {len(rows)}{Colors.ENDC}")


def get_generic_database_stats(db_path: str, db_info: Dict):
    """Get generic statistics from any database"""
    print_header(f"DATABASE STATISTICS: {db_info['name']}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Database size
        size_mb = db_info['size'] / (1024 * 1024)
        print(f"{Colors.BOLD}Database Size:{Colors.ENDC} {size_mb:.2f} MB")
        print(f"{Colors.BOLD}Total Tables:{Colors.ENDC} {len(db_info['tables'])}")
        
        # Table statistics
        print(f"\n{Colors.BOLD}Table Statistics:{Colors.ENDC}")
        total_rows = 0
        for table_name, table_data in db_info['tables'].items():
            row_count = table_data['row_count']
            col_count = len(table_data['columns'])
            total_rows += row_count
            
            print(f"\n  {Colors.OKBLUE}{table_name}{Colors.ENDC}")
            print(f"    Rows: {row_count:,}")
            print(f"    Columns: {col_count}")
            print(f"    Column Names: {', '.join(table_data['columns'][:5])}" + 
                  (f"... (+{col_count-5} more)" if col_count > 5 else ""))
            
            # Show sample data from each table (first row)
            try:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
                sample = cursor.fetchone()
                if sample:
                    print(f"    Sample data: {str(sample)[:80]}..." if len(str(sample)) > 80 else f"    Sample data: {sample}")
            except:
                pass
        
        print(f"\n{Colors.BOLD}Summary:{Colors.ENDC}")
        print(f"  Total Rows Across All Tables: {total_rows:,}")
        print(f"  Average Rows per Table: {total_rows // len(db_info['tables']) if db_info['tables'] else 0:,}")
        
        conn.close()
        
    except Exception as e:
        print_error(f"Error reading database: {str(e)}")


def database_operations_menu():
    """Database operations submenu"""
    databases = []
    
    while True:
        print("\n" + "="*70)
        print_header("DATABASE OPERATIONS")
        
        print("1. Scan/Rescan for SQLite Databases")
        print("2. Display Database Structure")
        print("3. View Database Statistics")
        print("4. Get First 5 Rows")
        print("5. Get Last 5 Rows")
        print("6. Search by Column Value (with Fuzzy Search)")
        print("7. Search Across All Columns")
        print("8. Custom SQL Query")
        print("0. Back to Main Menu")
        
        choice = input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}").strip()
        
        if choice == '0':
            break
        
        elif choice == '1':
            databases = find_sqlite_databases()
            print_success(f"Found {len(databases)} database(s)")
            
            # Display database names and first 10 tables
            if databases:
                print(f"\n{Colors.BOLD}Database Overview:{Colors.ENDC}")
                for idx, db in enumerate(databases, 1):
                    print(f"\n  [{idx}] {Colors.OKBLUE}{db['name']}{Colors.ENDC}")
                    print(f"      Path: {db['path']}")
                    
                    tables = list(db['tables'].keys())
                    table_count = len(tables)
                    
                    if table_count > 0:
                        print(f"      Tables ({table_count} total):")
                        # Show first 10 tables
                        for table_name in tables[:10]:
                            row_count = db['tables'][table_name]['row_count']
                            print(f"        • {table_name} ({row_count} rows)")
                        
                        # Indicate if there are more tables
                        if table_count > 10:
                            print(f"        ... and {table_count - 10} more table(s)")
                    else:
                        print(f"      Tables: None")
            
            input("\nPress Enter to continue...")
        
        elif choice == '2':
            if not databases:
                databases = find_sqlite_databases()
            display_database_structure(databases)
            input("\nPress Enter to continue...")
        
        elif choice == '3':
            if not databases:
                print_warning("No databases scanned yet. Scanning now...")
                databases = find_sqlite_databases()
            
            if not databases:
                print_error("No databases found!")
                input("\nPress Enter to continue...")
                continue
            
            # Select database
            print("\nAvailable Databases:")
            for idx, db in enumerate(databases, 1):
                print(f"  [{idx}] {db['name']}")
            
            db_choice = input(f"\n{Colors.OKCYAN}Select database (1-{len(databases)}): {Colors.ENDC}")
            try:
                db_idx = int(db_choice) - 1
                selected_db = databases[db_idx]
                get_generic_database_stats(selected_db['path'], selected_db)
            except (ValueError, IndexError):
                print_error("Invalid selection!")
            
            input("\nPress Enter to continue...")
        
        elif choice in ['4', '5', '6', '7', '8']:
            if not databases:
                print_warning("No databases scanned yet. Scanning now...")
                databases = find_sqlite_databases()
            
            if not databases:
                print_error("No databases found!")
                input("\nPress Enter to continue...")
                continue
            
            # Select database
            print("\nAvailable Databases:")
            for idx, db in enumerate(databases, 1):
                print(f"  [{idx}] {db['name']}")
            
            db_choice = input(f"\n{Colors.OKCYAN}Select database (1-{len(databases)}): {Colors.ENDC}").strip()
            try:
                db_idx = int(db_choice) - 1
                selected_db = databases[db_idx]
            except (ValueError, IndexError):
                print_error("Invalid selection!")
                input("\nPress Enter to continue...")
                continue
            
            # Select table
            print(f"\nTables in {selected_db['name']}:")
            tables = list(selected_db['tables'].keys())
            for idx, table in enumerate(tables, 1):
                print(f"  [{idx}] {table}")
            
            table_choice = input(f"\n{Colors.OKCYAN}Select table (1-{len(tables)}): {Colors.ENDC}").strip()
            try:
                table_idx = int(table_choice) - 1
                selected_table = tables[table_idx]
            except (ValueError, IndexError):
                print_error("Invalid selection!")
                input("\nPress Enter to continue...")
                continue
            
            # Execute operation
            if choice == '4':
                columns, rows = get_first_n_rows(selected_db['path'], selected_table)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '5':
                columns, rows = get_last_n_rows(selected_db['path'], selected_table)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '6':
                print(f"\nColumns in {selected_table}:")
                columns_list = selected_db['tables'][selected_table]['columns']
                for idx, col in enumerate(columns_list, 1):
                    print(f"  [{idx}] {col}")
                
                col_choice = input(f"\n{Colors.OKCYAN}Select column (1-{len(columns_list)}): {Colors.ENDC}").strip()
                try:
                    col_idx = int(col_choice) - 1
                    selected_column = columns_list[col_idx]
                except (ValueError, IndexError):
                    print_error("Invalid selection!")
                    input("\nPress Enter to continue...")
                    continue
                
                search_value = input(f"{Colors.OKCYAN}Enter search value: {Colors.ENDC}").strip()
                use_fuzzy = input(f"{Colors.OKCYAN}Use fuzzy search? (Y/n): {Colors.ENDC}").strip().lower()
                fuzzy = use_fuzzy in ['y', 'yes', '']
                
                if fuzzy:
                    print_info("Using fuzzy search (case-insensitive, matches all terms)...")
                
                columns, rows = search_by_column(selected_db['path'], selected_table, selected_column, search_value, fuzzy)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '7':
                search_value = input(f"{Colors.OKCYAN}Enter search value (searches ALL columns): {Colors.ENDC}").strip()
                print_info(f"Searching across all columns in {selected_table}...")
                columns, rows = search_all_columns(selected_db['path'], selected_table, search_value)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '8':
                print(f"\n{Colors.WARNING}Warning: Use SELECT queries only!{Colors.ENDC}")
                query = input(f"{Colors.OKCYAN}Enter SQL query: {Colors.ENDC}").strip()
                
                try:
                    conn = sqlite3.connect(selected_db['path'])
                    cursor = conn.cursor()
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    conn.close()
                    
                    if columns:
                        display_table_data(columns, rows)
                    else:
                        print_success("Query executed successfully!")
                except Exception as e:
                    print_error(f"Query error: {str(e)}")
            
            input("\nPress Enter to continue...")


# ============================================================================
# SYSTEM DIAGNOSTICS
# ============================================================================

def get_system_info():
    """Get system information"""
    try:
        import psutil
        
        print_header("SYSTEM INFORMATION")
        
        # OS Info
        print(f"{Colors.BOLD}Operating System:{Colors.ENDC}")
        print(f"  Platform: {platform.system()} {platform.release()}")
        print(f"  Architecture: {platform.machine()}")
        print(f"  Hostname: {platform.node()}")
        
        # CPU Info
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        print(f"\n{Colors.BOLD}CPU:{Colors.ENDC}")
        print(f"  Cores: {cpu_count}")
        print(f"  Usage: {cpu_percent}%")
        
        # Memory Info
        mem = psutil.virtual_memory()
        print(f"\n{Colors.BOLD}Memory:{Colors.ENDC}")
        print(f"  Total: {mem.total / (1024**3):.2f} GB")
        print(f"  Used: {mem.used / (1024**3):.2f} GB ({mem.percent}%)")
        print(f"  Available: {mem.available / (1024**3):.2f} GB")
        
        # Disk Info
        disk = psutil.disk_usage('/')
        print(f"\n{Colors.BOLD}Disk:{Colors.ENDC}")
        print(f"  Total: {disk.total / (1024**3):.2f} GB")
        print(f"  Used: {disk.used / (1024**3):.2f} GB ({disk.percent}%)")
        print(f"  Free: {disk.free / (1024**3):.2f} GB")
        
        # Network Info
        net_io = psutil.net_io_counters()
        print(f"\n{Colors.BOLD}Network:{Colors.ENDC}")
        print(f"  Bytes Sent: {net_io.bytes_sent / (1024**2):.2f} MB")
        print(f"  Bytes Received: {net_io.bytes_recv / (1024**2):.2f} MB")
        
    except ImportError:
        print_warning("psutil not installed. Install with: pip install psutil")
        print_info("\nBasic system info:")
        print(f"  Platform: {platform.system()} {platform.release()}")
        print(f"  Python: {platform.python_version()}")


def get_python_environment():
    """Get Python environment information"""
    print_header("PYTHON ENVIRONMENT")
    
    print(f"{Colors.BOLD}Python Version:{Colors.ENDC} {platform.python_version()}")
    print(f"{Colors.BOLD}Executable:{Colors.ENDC} {sys.executable}")
    print(f"{Colors.BOLD}Virtual Env:{Colors.ENDC} {os.environ.get('VIRTUAL_ENV', 'Not in venv')}")
    
    # Check common packages (optional, won't fail if not present)
    print(f"\n{Colors.BOLD}Common Packages:{Colors.ENDC}")
    common_packages = ['flask', 'django', 'fastapi', 'pandas', 'numpy', 'requests', 'pytest', 'sqlalchemy']
    
    installed_count = 0
    for package in common_packages:
        try:
            mod = __import__(package)
            version = getattr(mod, '__version__', 'unknown')
            print_success(f"  {package}: {version}")
            installed_count += 1
        except ImportError:
            pass  # Don't show not installed to reduce clutter
    
    if installed_count == 0:
        print_info("  No common packages detected (or different package set)")


def delete_cache_folders():
    """Delete common cache folders recursively"""
    print_header("DELETE CACHE FOLDERS")
    
    root = Path.cwd()
    cache_patterns = ['__pycache__', '.pytest_cache', '.ruff_cache', 'node_modules', '.mypy_cache']
    
    found_caches = []
    
    print_info("Scanning for cache folders...")
    for pattern in cache_patterns:
        for cache_dir in root.rglob(pattern):
            if cache_dir.is_dir():
                size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file()) / (1024**2)
                found_caches.append((cache_dir, size))
    
    if not found_caches:
        print_success("No cache folders found!")
        return
    
    print(f"\n{Colors.BOLD}Found {len(found_caches)} cache folder(s):{Colors.ENDC}")
    total_size = 0
    for cache_dir, size in found_caches:
        print(f"  {cache_dir.relative_to(root)} ({size:.2f} MB)")
        total_size += size
    
    print(f"\n{Colors.WARNING}Total size to be freed: {total_size:.2f} MB{Colors.ENDC}")
    confirm = input(f"\n{Colors.FAIL}Delete all cache folders? (y/N): {Colors.ENDC}").strip().lower()
    
    if confirm in ['y', 'yes']:
        deleted = 0
        for cache_dir, _ in found_caches:
            try:
                import shutil
                shutil.rmtree(cache_dir)
                deleted += 1
                print_success(f"Deleted: {cache_dir.relative_to(root)}")
            except Exception as e:
                print_error(f"Failed to delete {cache_dir.name}: {str(e)}")
        
        print_success(f"\nDeleted {deleted}/{len(found_caches)} cache folders ({total_size:.2f} MB freed)")
    else:
        print_info("Operation cancelled.")


def delete_specific_path():
    """Delete a specific file or folder by name/path"""
    print_header("DELETE SPECIFIC FILE/FOLDER")
    
    root = Path.cwd()
    
    target = input(f"{Colors.OKCYAN}Enter file/folder name or path to delete: {Colors.ENDC}").strip()
    
    if not target:
        print_warning("No input provided.")
        return
    
    # Check if it's a relative path or just a name
    target_path = root / target if not Path(target).is_absolute() else Path(target)
    
    if not target_path.exists():
        print_error(f"Path does not exist: {target_path}")
        return
    
    # Show what will be deleted
    if target_path.is_file():
        size = target_path.stat().st_size / 1024
        print(f"\n{Colors.BOLD}File:{Colors.ENDC} {target_path}")
        print(f"{Colors.BOLD}Size:{Colors.ENDC} {size:.2f} KB")
    else:
        file_count = len(list(target_path.rglob('*')))
        size = sum(f.stat().st_size for f in target_path.rglob('*') if f.is_file()) / (1024**2)
        print(f"\n{Colors.BOLD}Folder:{Colors.ENDC} {target_path}")
        print(f"{Colors.BOLD}Contents:{Colors.ENDC} {file_count} items")
        print(f"{Colors.BOLD}Size:{Colors.ENDC} {size:.2f} MB")
    
    confirm = input(f"\n{Colors.FAIL}Are you sure you want to delete this? (y/N): {Colors.ENDC}").strip().lower()
    
    if confirm in ['y', 'yes']:
        try:
            import shutil
            if target_path.is_file():
                target_path.unlink()
            else:
                shutil.rmtree(target_path)
            print_success(f"Deleted: {target_path}")
        except Exception as e:
            print_error(f"Failed to delete: {str(e)}")
    else:
        print_info("Operation cancelled.")


def smart_duplicate_folder():
    """Create a smart duplicate of current folder with exclusions"""
    print_header("SMART FOLDER DUPLICATE")
    
    root = Path.cwd()
    
    # Exclusion patterns
    exclusions = [
        '.venv', 'venv', 'env',
        '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache',
        'node_modules',
        '*.pyc', '*.pyo', '*.pyd',
        '.git',
        '*.log',
        '.DS_Store', 'Thumbs.db',
        'build', 'dist', '*.egg-info'
    ]
    
    print(f"{Colors.BOLD}Current folder:{Colors.ENDC} {root}")
    print(f"\n{Colors.BOLD}Will exclude:{Colors.ENDC}")
    for exc in exclusions:
        print(f"  - {exc}")
    
    # Get new folder name
    default_name = f"{root.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    new_name = input(f"\n{Colors.OKCYAN}Enter new folder name [{default_name}]: {Colors.ENDC}").strip()
    
    if not new_name:
        new_name = default_name
    
    target_path = root.parent / new_name
    
    if target_path.exists():
        print_error(f"Folder already exists: {target_path}")
        return
    
    print(f"\n{Colors.WARNING}Creating duplicate at: {target_path}{Colors.ENDC}")
    confirm = input(f"{Colors.OKCYAN}Proceed? (Y/n): {Colors.ENDC}").strip().lower()
    
    if confirm not in ['y', 'yes', '']:
        print_info("Operation cancelled.")
        return
    
    import shutil
    
    def should_exclude(path: Path) -> bool:
        """Check if path matches exclusion patterns"""
        path_str = str(path.relative_to(root))
        path_parts = path.parts
        
        for exclusion in exclusions:
            # Check if any part of the path matches
            if exclusion.startswith('*.'):
                # File extension pattern
                if path.suffix == exclusion[1:]:
                    return True
            else:
                # Directory or file name pattern
                if exclusion in path_parts or path.name == exclusion:
                    return True
        return False
    
    try:
        copied_files = 0
        skipped_files = 0
        
        # Create target directory
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Walk through source directory
        for item in root.rglob('*'):
            if should_exclude(item):
                skipped_files += 1
                continue
            
            relative_path = item.relative_to(root)
            target_item = target_path / relative_path
            
            try:
                if item.is_dir():
                    target_item.mkdir(parents=True, exist_ok=True)
                elif item.is_file():
                    target_item.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target_item)
                    copied_files += 1
                    
                    if copied_files % 100 == 0:
                        print_info(f"Copied {copied_files} files...")
            except Exception as e:
                print_warning(f"Skipped {relative_path}: {str(e)}")
                skipped_files += 1
        
        size = sum(f.stat().st_size for f in target_path.rglob('*') if f.is_file()) / (1024**2)
        
        print_success(f"\nDuplicate created successfully!")
        print(f"  Location: {target_path}")
        print(f"  Files copied: {copied_files}")
        print(f"  Files skipped: {skipped_files}")
        print(f"  Total size: {size:.2f} MB")
        
    except Exception as e:
        print_error(f"Failed to create duplicate: {str(e)}")
        # Try to clean up partial copy
        if target_path.exists():
            try:
                shutil.rmtree(target_path)
                print_info("Cleaned up partial copy.")
            except:
                pass


def analyze_logs():
    """Analyze log files"""
    print_header("LOG FILE ANALYSIS")
    
    root = Path.cwd()
    
    # Try common log directories
    possible_dirs = [
        root / 'logs',
        root / 'src' / 'logs',
        root / 'src' / 'logs_server',
        root / 'log',
        root
    ]
    
    log_files = []
    log_dir = None
    
    for dir_path in possible_dirs:
        if dir_path.exists():
            found_logs = list(dir_path.glob('*.log'))
            if found_logs:
                log_files = found_logs
                log_dir = dir_path
                break
    
    if not log_files:
        print_warning("No log files found in common directories!")
        print_info("Searched: logs/, src/logs/, src/logs_server/, log/, ./")
        return
    
    for log_file in log_files:
        print(f"\n{Colors.BOLD}{log_file.name}:{Colors.ENDC}")
        print(f"  Size: {log_file.stat().st_size / 1024:.2f} KB")
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                total_lines = len(lines)
                
                # Count errors and warnings
                errors = sum(1 for line in lines if 'ERROR' in line.upper() or 'FAIL' in line.upper())
                warnings = sum(1 for line in lines if 'WARNING' in line.upper() or 'WARN' in line.upper())
                
                print(f"  Total Lines: {total_lines}")
                if errors > 0:
                    print_error(f"  Errors: {errors}")
                else:
                    print_success(f"  Errors: 0")
                
                if warnings > 0:
                    print_warning(f"  Warnings: {warnings}")
                else:
                    print_success(f"  Warnings: 0")
                
                # Show last 5 lines
                print(f"\n  {Colors.BOLD}Last 5 lines:{Colors.ENDC}")
                for line in lines[-5:]:
                    print(f"    {line.rstrip()}")
        
        except Exception as e:
            print_error(f"  Error reading file: {str(e)}")


def check_configurations():
    """Check YAML/JSON/INI configurations"""
    print_header("CONFIGURATION AUDIT")
    
    root = Path.cwd()
    
    # Try common config directories and files
    possible_dirs = [
        root / 'config',
        root / 'configs',
        root / 'data' / 'configs',
        root / 'conf',
        root
    ]
    
    config_files = []
    for dir_path in possible_dirs:
        if dir_path.exists():
            config_files.extend(list(dir_path.glob('*.yaml')))
            config_files.extend(list(dir_path.glob('*.yml')))
            config_files.extend(list(dir_path.glob('*.json')))
            config_files.extend(list(dir_path.glob('*.ini')))
            config_files.extend(list(dir_path.glob('*.toml')))
            if config_files:
                break
    
    if not config_files:
        print_warning("No configuration files found!")
        print_info("Searched for: *.yaml, *.yml, *.json, *.ini, *.toml")
        return
    
    for config_file in config_files:
        print(f"\n{Colors.BOLD}{config_file.name}:{Colors.ENDC}")
        
        try:
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            if config:
                for key, value in config.items():
                    # Mask sensitive data
                    if 'key' in key.lower() or 'secret' in key.lower() or 'password' in key.lower():
                        display_value = '***MASKED***' if value else 'NOT SET'
                        if value:
                            print_success(f"  {key}: {display_value}")
                        else:
                            print_error(f"  {key}: {display_value}")
                    else:
                        print(f"  {key}: {value}")
            else:
                print_warning("  Empty configuration")
        
        except Exception as e:
            print_error(f"  Error reading: {str(e)}")


def get_database_stats():
    """Get statistics from user_flows database"""
    print_header("DATABASE STATISTICS")
    
    root = Path.cwd()
    db_path = root / 'src' / 'logs' / 'user_flows.db'
    
    if not db_path.exists():
        print_error("user_flows.db not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Total sessions
        cursor.execute("SELECT COUNT(*) FROM user_flows")
        total_sessions = cursor.fetchone()[0]
        print_success(f"Total Sessions: {total_sessions}")
        
        # Flow type breakdown
        cursor.execute("SELECT flow_type, COUNT(*) FROM user_flows GROUP BY flow_type")
        flow_types = cursor.fetchall()
        print(f"\n{Colors.BOLD}Flow Type Breakdown:{Colors.ENDC}")
        for flow_type, count in flow_types:
            print(f"  {flow_type}: {count}")
        
        # Recent sessions (last 10)
        print(f"\n{Colors.BOLD}Recent Sessions (Last 10):{Colors.ENDC}")
        cursor.execute("""
            SELECT session_id, user_query, selected_ticker, timestamp 
            FROM user_flows 
            ORDER BY timestamp DESC 
            LIMIT 10
        """)
        
        recent = cursor.fetchall()
        for row in recent:
            session_id, query, ticker, timestamp = row
            query_short = query[:50] + '...' if len(query) > 50 else query
            print(f"  [{session_id[:8]}] {ticker} - {query_short}")
            print(f"    {timestamp}")
        
        # Performance stats
        cursor.execute("""
            SELECT 
                AVG(total_return) as avg_return,
                MAX(total_return) as max_return,
                MIN(total_return) as min_return,
                AVG(sharpe_ratio) as avg_sharpe
            FROM user_flows 
            WHERE total_return IS NOT NULL
        """)
        
        stats = cursor.fetchone()
        if stats and stats[0] is not None:
            print(f"\n{Colors.BOLD}Performance Metrics:{Colors.ENDC}")
            print(f"  Avg Return: {stats[0]:.2f}%")
            print(f"  Max Return: {stats[1]:.2f}%")
            print(f"  Min Return: {stats[2]:.2f}%")
            print(f"  Avg Sharpe: {stats[3]:.2f}" if stats[3] else "  Avg Sharpe: N/A")
        
        conn.close()
        
    except Exception as e:
        print_error(f"Error reading database: {str(e)}")


def show_last_modified_files():
    """Show last modified files (most recent first)"""
    print_header("LAST MODIFIED FILES")
    
    # Ask user for number of entries
    default_count = 5
    count_input = input(f"{Colors.OKCYAN}How many files to show? [{default_count}]: {Colors.ENDC}").strip()
    
    try:
        count = int(count_input) if count_input else default_count
        if count <= 0:
            print_error("Count must be positive!")
            return
    except ValueError:
        print_error("Invalid number!")
        return
    
    root = Path.cwd()
    print_info(f"Scanning files from: {root}")
    print_info(f"Excluding directories starting with '.' or '_'")
    
    # Collect all files with modification times
    files_with_mtime = []
    
    try:
        for item in root.rglob('*'):
            # Skip directories starting with . or _
            skip = False
            for part in item.parts:
                part_name = Path(part).name
                if part_name.startswith('.') or part_name.startswith('_'):
                    skip = True
                    break
            
            if skip:
                continue
            
            # Only process files, not directories
            if item.is_file():
                try:
                    mtime = item.stat().st_mtime
                    files_with_mtime.append((item, mtime))
                except Exception as e:
                    # Skip files that can't be accessed
                    continue
        
        if not files_with_mtime:
            print_warning("No files found!")
            return
        
        # Sort by modification time (most recent first)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        
        # Display the top N files
        print(f"\n{Colors.BOLD}Top {count} most recently modified files:{Colors.ENDC}\n")
        
        for idx, (file_path, mtime) in enumerate(files_with_mtime[:count], 1):
            try:
                # Format modification time
                mod_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                
                # Get file size
                size = file_path.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024**2:
                    size_str = f"{size/1024:.2f} KB"
                else:
                    size_str = f"{size/(1024**2):.2f} MB"
                
                # Get relative path
                rel_path = file_path.relative_to(root)
                
                print(f"{Colors.BOLD}[{idx}]{Colors.ENDC} {Colors.OKBLUE}{rel_path}{Colors.ENDC}")
                print(f"    Modified: {Colors.OKGREEN}{mod_time}{Colors.ENDC} | Size: {size_str}")
                print()
                
            except Exception as e:
                print_warning(f"Error displaying file: {str(e)}")
                continue
        
        total_files = len(files_with_mtime)
        print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
        print_info(f"Total files scanned: {total_files}")
        
    except Exception as e:
        print_error(f"Error scanning files: {str(e)}")


def file_operations_menu():
    """File operations submenu"""
    while True:
        print("\n" + "="*70)
        print_header("FILE OPERATIONS")
        
        print("1. Delete Cache Folders (__pycache__, etc.)")
        print("2. Delete Specific File/Folder")
        print("3. Smart Duplicate Current Folder")
        print("4. Show Last Modified Files (Most Recent First)")
        print("0. Back to Main Menu")
        
        choice = input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            delete_cache_folders()
            input("\nPress Enter to continue...")
        elif choice == '2':
            delete_specific_path()
            input("\nPress Enter to continue...")
        elif choice == '3':
            smart_duplicate_folder()
            input("\nPress Enter to continue...")
        elif choice == '4':
            show_last_modified_files()
            input("\nPress Enter to continue...")


def settings_menu():
    """Settings submenu"""
    while True:
        print("\n" + "="*70)
        print_header("SETTINGS")
        print(f"Current base directory: {SESSION_BASE_DIR}")

        print("1. Set Base Directory for Session")
        print("0. Back to Main Menu")

        choice = input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}").strip()

        if choice == '0':
            break
        elif choice == '1':
            set_base_directory()
            input("\nPress Enter to continue...")
        else:
            print_error("Invalid choice! Please try again.")


def system_diagnostics_menu():
    """System diagnostics submenu"""
    while True:
        print("\n" + "="*70)
        print_header("SYSTEM DIAGNOSTICS")
        
        print("1. System Information (CPU, RAM, Disk)")
        print("2. Python Environment")
        print("3. Full Diagnostic Report")
        print("0. Back to Main Menu")
        
        choice = input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}").strip()
        
        if choice == '0':
            break
        elif choice == '1':
            get_system_info()
            input("\nPress Enter to continue...")
        elif choice == '2':
            get_python_environment()
            input("\nPress Enter to continue...")
        elif choice == '3':
            get_system_info()
            get_python_environment()
            input("\nPress Enter to continue...")


# ============================================================================
# MAIN MENU
# ============================================================================

def main_menu():
    """Main menu loop"""
    while True:
        print("\n" + "="*70)
        print_header("Basus DIAGNOSTIC TOOL")
        print_status_bar()
        print(f"\n{Colors.BOLD}::MAIN MENU::{Colors.ENDC}\n")
        
        print("1. Database Operations")
        print("2. System Diagnostics")
        print("3. File Operations")
        print("4. Quick Health Check")
        print("5. Settings")
        print("0. Exit")
        
        choice = input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}").strip()
        
        if choice == '0':
            print_success("\nExiting. Goodbye!")
            sys.exit(0)
        
        elif choice == '1':
            database_operations_menu()
        
        elif choice == '2':
            system_diagnostics_menu()
        
        elif choice == '3':
            file_operations_menu()
        
        elif choice == '4':
            print_header("QUICK HEALTH CHECK")
            print_info("Running quick diagnostics...")
            
            root = Path.cwd()
            
            # Check for any SQLite databases
            print_info("Scanning for databases...")
            databases = find_sqlite_databases()
            if databases:
                total_size = sum(db['size'] for db in databases) / (1024**2)
                print_success(f"Databases: Found {len(databases)} ({total_size:.2f} MB total)")
                for db in databases[:3]:  # Show first 3
                    print(f"  • {db['name']} - {len(db['tables'])} tables")
                if len(databases) > 3:
                    print(f"  ... and {len(databases)-3} more")
            else:
                print_info("Databases: None found")
            
            # Check Python
            print_success(f"Python: {platform.python_version()}")
            
            # Check disk space
            try:
                import psutil
                disk = psutil.disk_usage('/')
                if disk.percent < 90:
                    print_success(f"Disk Space: {disk.free / (1024**3):.2f} GB free ({100-disk.percent:.1f}%)")
                else:
                    print_warning(f"Disk Space: LOW ({100-disk.percent:.1f}% free)")
            except:
                print_info("Disk Space: Cannot check (install psutil)")
            
            # Check for config files
            config_count = len(list(root.rglob('*.yaml'))) + len(list(root.rglob('*.yml'))) + len(list(root.rglob('*.json')))
            if config_count > 0:
                print_success(f"Config Files: Found {config_count}")
            else:
                print_info("Config Files: None found")
            
            input("\nPress Enter to continue...")

        elif choice == '5':
            settings_menu()


if __name__ == "__main__":
    try:
        ensure_working_directory()
        main_menu()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Interrupted by user. Exiting...{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
