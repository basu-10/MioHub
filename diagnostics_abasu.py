"""
Generic  Diagnostic & Database Management Tool
=============================================
Menu-based tool for system diagnostics and file operations, some db operations. 
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
from diagnostics_abasu_util import format_table
import zipfile
import shutil


# Add parent directory to path for imports
BASE_DIR = Path(__file__).resolve().parent
# Session-scoped working directory that can be updated via Settings
SESSION_BASE_DIR = BASE_DIR
sys.path.insert(0, str(BASE_DIR.parent))


# ============================================================================
# GLOBAL INPUT QUEUE FOR BATCH OPERATIONS
# ============================================================================
INPUT_QUEUE = []

def parse_input_chain(chain_str: str):
    """Parse input chain string into queue.
    
    Supports formats:
    - Comma-separated: "3,3,20"
    - 'y' separator: "3y3y20y" or "3y3y20"
    - Space-separated: "3 3 20"
    """
    global INPUT_QUEUE
    
    # Remove trailing separators
    chain_str = chain_str.strip().rstrip(',y ')
    
    # Try different delimiters
    if ',' in chain_str:
        INPUT_QUEUE = [x.strip() for x in chain_str.split(',') if x.strip()]
    elif 'y' in chain_str.lower():
        INPUT_QUEUE = [x.strip() for x in chain_str.lower().split('y') if x.strip()]
    elif ' ' in chain_str and len(chain_str.split()) > 1:
        INPUT_QUEUE = [x.strip() for x in chain_str.split() if x.strip()]
    else:
        # Single value
        INPUT_QUEUE = [chain_str.strip()] if chain_str.strip() else []
    
    if INPUT_QUEUE:
        print_info(f"Input queue loaded: {' -> '.join(INPUT_QUEUE)}")

def smart_input(prompt: str) -> str:
    """Smart input wrapper that uses queue if available, otherwise prompts user"""
    global INPUT_QUEUE
    
    if INPUT_QUEUE:
        value = INPUT_QUEUE.pop(0)
        print(f"{prompt}{Colors.WARNING}{value}{Colors.ENDC}  {Colors.OKBLUE}[auto]{Colors.ENDC}")
        return value
    
    return input(prompt).strip()


#----------------------------------------------------------------------------
MAIN_EXCLUSION_LIST= [
    '.db', '.sqlite', '.sqlite3', '.db3', 
    '.venv', 'venv', '.env','env',
    '__pycache__', '.pytest_cache', '.ruff_cache', '.mypy_cache',
    'node_modules',
    '*.pyc', '*.pyo', '*.pyd',
    '.git',
    '*.log',
    '.DS_Store', 'Thumbs.db',
    'build', 'dist', '*.egg-info'
]

ZIP_EXCLUSIONS = MAIN_EXCLUSION_LIST + [
    '*.zip', '*.tar', '*.gz', '*.7z', '*.rar', '*.iso'
]
#----------------------------------------------------------------------------
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

    new_path_input = smart_input(f"{Colors.OKCYAN}Enter new base directory (blank to keep current): {Colors.ENDC}")

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


def highlight_keywords(text: str) -> str:
    """Highlight action keywords in menu text for better visibility"""
    keywords = [
        'Delete', 'Copy', 'Duplicate', 'Zip', 'ZIP', 'Unzip', 'Extract',
        'Create', 'Add', 'Remove', 'Modify', 'View', 'Show', 'Display',
        'Search', 'Scan', 'Rescan', 'Edit', 'Rename', 'Move'
    ]
    
    result = text
    for keyword in keywords:
        # Highlight the keyword with WARNING color (yellow/orange) for visibility
        if keyword in result:
            result = result.replace(keyword, f"{Colors.WARNING}{keyword}{Colors.ENDC}")
    
    return result


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
        
        # Get OS information
        os_name = platform.system()
        os_release = platform.release()
        os_info = f"{os_name} {os_release}"
        
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
        print(f"{Colors.BOLD}[DIR] Folder:{Colors.ENDC} {current_dir}")
        print(f"{Colors.BOLD}Time:{Colors.ENDC} {current_time} | {Colors.BOLD}OS:{Colors.ENDC} {os_info}")
        print(f"{Colors.BOLD}Python:{Colors.ENDC} {python_ver}{disk_info}")
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
    """Display table data in a formatted way using util.format_table"""
    if not rows:
        print_warning("No data found!")
        return

    # Use the shared formatting helper
    table = format_table(rows=rows, headers=list(columns), padding=3, align=None, truncate=True)
    lines = table.splitlines()
    if not lines:
        return

    # Print header (bold) then the rest normally
    print(f"\n{Colors.BOLD}{lines[0]}{Colors.ENDC}")
    for line in lines[1:]:
        print(line)
    
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
        
        print(highlight_keywords("1. Scan/Rescan for SQLite Databases"))
        print(highlight_keywords("2. Display Database Structure"))
        print(highlight_keywords("3. View Database Statistics"))
        print("4. Get First 5 Rows")
        print("5. Get Last 5 Rows")
        print(highlight_keywords("6. Search by Column Value (with Fuzzy Search)"))
        print(highlight_keywords("7. Search Across All Columns"))
        print("8. Custom SQL Query")
        print("0. Back to Main Menu")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
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
            
            smart_input("\nPress Enter to continue...")
        
        elif choice == '2':
            if not databases:
                databases = find_sqlite_databases()
            display_database_structure(databases)
            smart_input("\nPress Enter to continue...")
        
        elif choice == '3':
            if not databases:
                print_warning("No databases scanned yet. Scanning now...")
                databases = find_sqlite_databases()
            
            if not databases:
                print_error("No databases found!")
                smart_input("\nPress Enter to continue...")
                continue
            
            # Select database
            print("\nAvailable Databases:")
            for idx, db in enumerate(databases, 1):
                print(f"  [{idx}] {db['name']}")
            
            db_choice = smart_input(f"\n{Colors.OKCYAN}Select database (1-{len(databases)}): {Colors.ENDC}")
            try:
                db_idx = int(db_choice) - 1
                selected_db = databases[db_idx]
                get_generic_database_stats(selected_db['path'], selected_db)
            except (ValueError, IndexError):
                print_error("Invalid selection!")
            
            smart_input("\nPress Enter to continue...")
        
        elif choice in ['4', '5', '6', '7', '8']:
            if not databases:
                print_warning("No databases scanned yet. Scanning now...")
                databases = find_sqlite_databases()
            
            if not databases:
                print_error("No databases found!")
                smart_input("\nPress Enter to continue...")
                continue
            
            # Select database
            print("\nAvailable Databases:")
            for idx, db in enumerate(databases, 1):
                print(f"  [{idx}] {db['name']}")
            
            db_choice = smart_input(f"\n{Colors.OKCYAN}Select database (1-{len(databases)}): {Colors.ENDC}")
            try:
                db_idx = int(db_choice) - 1
                selected_db = databases[db_idx]
            except (ValueError, IndexError):
                print_error("Invalid selection!")
                smart_input("\nPress Enter to continue...")
                continue
            
            # Select table
            print(f"\nTables in {selected_db['name']}:")
            tables = list(selected_db['tables'].keys())
            for idx, table in enumerate(tables, 1):
                print(f"  [{idx}] {table}")
            
            table_choice = smart_input(f"\n{Colors.OKCYAN}Select table (1-{len(tables)}): {Colors.ENDC}")
            try:
                table_idx = int(table_choice) - 1
                selected_table = tables[table_idx]
            except (ValueError, IndexError):
                print_error("Invalid selection!")
                smart_input("\nPress Enter to continue...")
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
                
                col_choice = smart_input(f"\n{Colors.OKCYAN}Select column (1-{len(columns_list)}): {Colors.ENDC}")
                try:
                    col_idx = int(col_choice) - 1
                    selected_column = columns_list[col_idx]
                except (ValueError, IndexError):
                    print_error("Invalid selection!")
                    smart_input("\nPress Enter to continue...")
                    continue
                
                search_value = smart_input(f"{Colors.OKCYAN}Enter search value: {Colors.ENDC}")
                use_fuzzy = smart_input(f"{Colors.OKCYAN}Use fuzzy search? (Y/n): {Colors.ENDC}").lower()
                fuzzy = use_fuzzy in ['y', 'yes', '']
                
                if fuzzy:
                    print_info("Using fuzzy search (case-insensitive, matches all terms)...")
                
                columns, rows = search_by_column(selected_db['path'], selected_table, selected_column, search_value, fuzzy)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '7':
                search_value = smart_input(f"{Colors.OKCYAN}Enter search value (searches ALL columns): {Colors.ENDC}")
                print_info(f"Searching across all columns in {selected_table}...")
                columns, rows = search_all_columns(selected_db['path'], selected_table, search_value)
                if columns:
                    display_table_data(columns, rows)
            
            elif choice == '8':
                print(f"\n{Colors.WARNING}Warning: Use SELECT queries only!{Colors.ENDC}")
                query = smart_input(f"{Colors.OKCYAN}Enter SQL query: {Colors.ENDC}")
                
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
            
            smart_input("\nPress Enter to continue...")


# ============================================================================
# SYSTEM DIAGNOSTICS
# ============================================================================

def get_system_info():
    """Get system information"""
    
    while True:
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
        
        choice = smart_input(f"\n{Colors.OKCYAN}Press Enter to refresh, or 0 to go back: {Colors.ENDC}")
        if choice == '0':
            return


def get_python_environment():
    """Get Python environment information"""
    
    while True:
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
        
        choice = smart_input(f"\n{Colors.OKCYAN}Press Enter to refresh, or 0 to go back: {Colors.ENDC}")
        if choice == '0':
            return


# ============================================================================
# ENVIRONMENT VARIABLE OPERATIONS
# ============================================================================

def view_environment_variables():
    """View all or specific environment variables"""
    
    while True:
        print_header("VIEW ENVIRONMENT VARIABLES")
        
        print(highlight_keywords("1. View all environment variables"))
        print(highlight_keywords("2. Search for specific variable"))
        print(highlight_keywords("3. View PATH variable (formatted)"))
        print("0. Back")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if choice == '0':
            return
        elif choice == '1':
            # Display all environment variables
            print(f"\n{Colors.BOLD}Current Environment Variables:{Colors.ENDC}\n")
            env_vars = sorted(os.environ.items())
            
            for key, value in env_vars:
                # Truncate very long values for display
                display_value = value if len(value) < 80 else value[:77] + "..."
                print(f"{Colors.OKBLUE}{key}{Colors.ENDC} = {display_value}")
            
            print(f"\n{Colors.OKGREEN}Total: {len(env_vars)} variables{Colors.ENDC}")
            smart_input("\nPress Enter to continue...")
            
        elif choice == '2':
            # Search for specific variable
            search_term = smart_input(f"{Colors.OKCYAN}Enter variable name (or part of it): {Colors.ENDC}")
            
            if not search_term:
                print_warning("No search term provided")
                continue
            
            print(f"\n{Colors.BOLD}Matching Environment Variables:{Colors.ENDC}\n")
            matches = [(k, v) for k, v in os.environ.items() if search_term.upper() in k.upper()]
            
            if matches:
                for key, value in sorted(matches):
                    print(f"{Colors.OKBLUE}{key}{Colors.ENDC} = {value}")
                print(f"\n{Colors.OKGREEN}Found {len(matches)} matches{Colors.ENDC}")
            else:
                print_warning(f"No variables found matching '{search_term}'")
            
            smart_input("\nPress Enter to continue...")
        
        elif choice == '3':
            # Display PATH variable formatted
            print(f"\n{Colors.BOLD}PATH Variable (each entry on new line):{Colors.ENDC}\n")
            path_var = os.environ.get('PATH', '')
        
        if not path_var:
            print_warning("PATH variable not found")
            smart_input("\nPress Enter to continue...")
            continue
        
        # Split by os-specific separator
        separator = ';' if platform.system() == 'Windows' else ':'
        paths = path_var.split(separator)
        
        for idx, path in enumerate(paths, 1):
            # Check if path exists
            exists = Path(path).exists() if path else False
            status = Colors.OKGREEN + "EXISTS" + Colors.ENDC if exists else Colors.WARNING + "MISSING" + Colors.ENDC
            print(f"{idx:3}. [{status}] {path}")
        
        print(f"\n{Colors.OKGREEN}Total: {len(paths)} paths{Colors.ENDC}")
        smart_input("\nPress Enter to continue...")


def add_environment_variable():
    """Add or modify environment variables (session only or permanent)"""
    print_header("ADD/MODIFY ENVIRONMENT VARIABLE")
    
    print_warning("IMPORTANT NOTES:")
    print_info("  - Session-only: Variable exists only for this Python process")
    print_info("  - Permanent: Variable persists across sessions (requires appropriate permissions)")
    
    current_os = platform.system()
    
    if current_os == 'Windows':
        print_info(f"  - OS Detected: {current_os} - Will use 'setx' for permanent changes")
    else:
        print_info(f"  - OS Detected: {current_os} - Will modify shell config file for permanent changes")
    
    print()
    
    var_name = smart_input(f"{Colors.OKCYAN}Enter variable name: {Colors.ENDC}")
    
    if not var_name:
        print_warning("Variable name cannot be empty")
        return
    
    # Check if variable already exists
    existing_value = os.environ.get(var_name)
    if existing_value:
        print_info(f"Variable '{var_name}' already exists with value: {existing_value}")
        overwrite = smart_input(f"{Colors.WARNING}Overwrite? (y/n): {Colors.ENDC}").lower()
        if overwrite != 'y':
            print_info("Operation cancelled")
            return
    
    var_value = smart_input(f"{Colors.OKCYAN}Enter variable value: {Colors.ENDC}")
    
    if not var_value:
        print_warning("Variable value cannot be empty")
        return
    
    print("\n1. Session-only (temporary)")
    print("2. Permanent (persists across sessions)")
    
    scope_choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
    
    if scope_choice == '1':
        # Session-only
        os.environ[var_name] = var_value
        print_success(f"Variable '{var_name}' set to '{var_value}' for this session")
        print_info("This change will be lost when the script exits")
    
    elif scope_choice == '2':
        # Permanent
        try:
            if current_os == 'Windows':
                # Use setx command on Windows
                result = os.system(f'setx {var_name} "{var_value}"')
                
                if result == 0:
                    print_success(f"Variable '{var_name}' permanently set to '{var_value}'")
                    print_info("You may need to restart applications for changes to take effect")
                    print_info("Note: Current terminal session may not reflect the change immediately")
                    # Also set for current session
                    os.environ[var_name] = var_value
                else:
                    print_error("Failed to set permanent variable. Check permissions.")
            
            else:
                # Linux/Unix - modify .bashrc or .profile
                home = Path.home()
                bashrc = home / '.bashrc'
                profile = home / '.profile'
                
                # Prefer .bashrc if it exists, otherwise .profile
                config_file = bashrc if bashrc.exists() else profile
                
                export_line = f'\nexport {var_name}="{var_value}"\n'
                
                print_info(f"Will add to: {config_file}")
                confirm = smart_input(f"{Colors.WARNING}Confirm? (y/n): {Colors.ENDC}").lower()
                
                if confirm == 'y':
                    with open(config_file, 'a') as f:
                        f.write(export_line)
                    
                    print_success(f"Added to {config_file}")
                    print_info(f"Run 'source {config_file}' to apply in current terminal")
                    print_info("Or restart your terminal")
                    # Also set for current session
                    os.environ[var_name] = var_value
                else:
                    print_info("Operation cancelled")
        
        except Exception as e:
            print_error(f"Error setting permanent variable: {str(e)}")


def modify_path_variable():
    """Add or remove entries from PATH variable"""
    print_header("MODIFY PATH VARIABLE")
    
    current_os = platform.system()
    separator = ';' if current_os == 'Windows' else ':'
    
    print(highlight_keywords("1. Add new path to PATH"))
    print(highlight_keywords("2. Remove path from PATH"))
    print(highlight_keywords("3. View current PATH"))
    print("0. Back")
    
    choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
    
    if choice == '0':
        return
    elif choice == '3':
        view_environment_variables()
        return
    elif choice == '1':
        # Add to PATH
        new_path = smart_input(f"{Colors.OKCYAN}Enter path to add: {Colors.ENDC}")
        
        if not new_path:
            print_warning("Path cannot be empty")
            return
        
        # Check if path exists
        if not Path(new_path).exists():
            print_warning(f"Warning: Path does not exist: {new_path}")
            confirm = smart_input(f"{Colors.WARNING}Continue anyway? (y/n): {Colors.ENDC}").lower()
            if confirm != 'y':
                return
        
        current_path = os.environ.get('PATH', '')
        
        # Check if already in PATH
        if new_path in current_path.split(separator):
            print_warning(f"Path already in PATH: {new_path}")
            return
        
        print("\n1. Session-only (temporary)")
        print("2. Permanent (persists across sessions)")
        
        scope_choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if scope_choice == '1':
            # Session-only
            new_path_value = f"{new_path}{separator}{current_path}"
            os.environ['PATH'] = new_path_value
            print_success(f"Added '{new_path}' to PATH for this session")
        
        elif scope_choice == '2':
            # Permanent
            try:
                if current_os == 'Windows':
                    # For Windows, we append to existing PATH
                    print_info("Adding to system PATH on Windows...")
                    print_warning("This requires administrator privileges")
                    
                    # Get current permanent PATH value
                    import subprocess
                    result = subprocess.run(
                        ['powershell', '-Command', f'[System.Environment]::GetEnvironmentVariable("PATH", "User")'],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        current_permanent_path = result.stdout.strip()
                        new_permanent_path = f"{new_path}{separator}{current_permanent_path}"
                        
                        # Set using setx
                        set_result = os.system(f'setx PATH "{new_permanent_path}"')
                        
                        if set_result == 0:
                            print_success(f"Added '{new_path}' to permanent PATH")
                            print_info("Restart applications for changes to take effect")
                            # Also set for current session
                            os.environ['PATH'] = f"{new_path}{separator}{os.environ.get('PATH', '')}"
                        else:
                            print_error("Failed to update PATH. Check permissions.")
                    else:
                        print_error("Failed to read current PATH value")
                
                else:
                    # Linux/Unix
                    home = Path.home()
                    bashrc = home / '.bashrc'
                    profile = home / '.profile'
                    
                    config_file = bashrc if bashrc.exists() else profile
                    
                    export_line = f'\nexport PATH="{new_path}{separator}$PATH"\n'
                    
                    print_info(f"Will add to: {config_file}")
                    confirm = smart_input(f"{Colors.WARNING}Confirm? (y/n): {Colors.ENDC}").lower()
                    
                    if confirm == 'y':
                        with open(config_file, 'a') as f:
                            f.write(export_line)
                        
                        print_success(f"Added to {config_file}")
                        print_info(f"Run 'source {config_file}' to apply")
                        # Also set for current session
                        os.environ['PATH'] = f"{new_path}{separator}{os.environ.get('PATH', '')}"
                    else:
                        print_info("Operation cancelled")
            
            except Exception as e:
                print_error(f"Error modifying PATH: {str(e)}")
    
    elif choice == '2':
        # Remove from PATH
        print_info("Current PATH entries:\n")
        current_path = os.environ.get('PATH', '')
        paths = current_path.split(separator)
        
        for idx, path in enumerate(paths, 1):
            print(f"{idx}. {path}")
        
        try:
            idx_to_remove = int(smart_input(f"\n{Colors.OKCYAN}Enter number to remove (0 to cancel): {Colors.ENDC}"))
            
            if idx_to_remove == 0:
                return
            
            if 1 <= idx_to_remove <= len(paths):
                path_to_remove = paths[idx_to_remove - 1]
                
                print_warning(f"Remove: {path_to_remove}")
                confirm = smart_input(f"{Colors.WARNING}Confirm? (y/n): {Colors.ENDC}").lower()
                
                if confirm == 'y':
                    paths.pop(idx_to_remove - 1)
                    new_path_value = separator.join(paths)
                    os.environ['PATH'] = new_path_value
                    
                    print_success(f"Removed from PATH (session only)")
                    print_info("To make permanent, manually edit shell config file")
                else:
                    print_info("Operation cancelled")
            else:
                print_error("Invalid selection")
        
        except ValueError:
            print_error("Invalid input")


def environment_variables_menu():
    """Environment variables management submenu"""
    while True:
        print("\n" + "="*70)
        print_header("ENVIRONMENT VARIABLES")
        
        print(highlight_keywords("1. View Environment Variables"))
        print(highlight_keywords("2. Add/Modify Environment Variable"))
        print(highlight_keywords("3. Modify PATH Variable"))
        print("0. Back to System Diagnostics")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if choice == '0':
            break
        elif choice == '1':
            view_environment_variables()
        elif choice == '2':
            add_environment_variable()
            smart_input("\nPress Enter to continue...")
        elif choice == '3':
            modify_path_variable()
            smart_input("\nPress Enter to continue...")


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
    confirm = smart_input(f"\n{Colors.FAIL}Delete all cache folders? (y/N): {Colors.ENDC}").lower()
    
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
    
    target = smart_input(f"{Colors.OKCYAN}Enter file/folder name or path to delete: {Colors.ENDC}")
    
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
    
    confirm = smart_input(f"\n{Colors.FAIL}Are you sure you want to delete this? (y/N): {Colors.ENDC}").lower()
    
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


def should_exclude_from_zip(path: Path, exclusion_list: List[str]) -> bool:
    """Check if a path should be excluded based on exclusion patterns."""
    path_parts = path.parts
    
    for exclusion in exclusion_list:
        if exclusion.startswith('*.'):
            # File extension pattern
            if path.suffix == exclusion[1:]:
                return True
        else:
            # Directory or file name pattern
            if exclusion in path_parts or path.name == exclusion:
                return True
    return False


def list_folders_and_files():
    """List all folders and files in the current directory.
    
    Returns:
        tuple: (folders_list, files_list) where each is a list of Path objects
    """
    current_dir = Path.cwd()
    
    folders = []
    files = []
    
    try:
        for item in current_dir.iterdir():
            if item.is_dir():
                folders.append(item)
            elif item.is_file():
                files.append(item)
    except Exception as e:
        print_error(f"Error listing directory contents: {str(e)}")
    
    return sorted(folders, key=lambda x: x.name.lower()), sorted(files, key=lambda x: x.name.lower())


def get_user_selection_for_zip(folders, files):
    """Display folders and files, get user selection.
    
    Returns:
        tuple: (selection_type, selected_items) where:
            selection_type: 'all', 'multiple', or 'single'
            selected_items: list of Path objects
    """
    current_dir = Path.cwd()
    
    print(f"\n{Colors.BOLD}Functions:{Colors.ENDC}")
    print(f"Enter 'a'/'A' to zip everything in current directory.")
    print(f"")
    print(f"Enter number adjacent to the directory/file name to zip that particular file/folder.")
    print(f"For multi selection enter numbers separated by spaces!")
    print(f"")
    print(f"Enter 0 to go back.")
    print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
    print()
    
    # Build combined list of all items
    all_items = folders + files
    
    if not all_items:
        print_warning("No folders or files found in current directory!")
        return None, []
    
    
    # Display folders
    if folders:
        print(f"{Colors.BOLD}Folders:{Colors.ENDC}")
        for idx, folder in enumerate(folders, start=1):
            print(f"{idx}. [DIR] {folder.name}")
    
    # Display files
    if files:
        if folders:
            print()
        print(f"{Colors.BOLD}Files:{Colors.ENDC}")
        start_idx = len(folders) + 1
        for idx, file in enumerate(files, start=start_idx):
            size = file.stat().st_size
            size_str = f"{size / 1024:.1f} KB" if size < 1024**2 else f"{size / (1024**2):.1f} MB"
            print(f"{idx}. [FILE] {file.name} ({size_str})")
    
    print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
    
    # Get user input
    choice = smart_input(f"{Colors.OKCYAN}Enter your choice (0/a/<1....n>): {Colors.ENDC}")
    
    # Handle 'a' or 'A' for all
    if choice.lower() == 'a':
        return 'all', all_items
    
    # Handle '0' to go back
    if choice == '0':
        print_info("Going back...")
        return None, []
    
    # Handle numeric selection (single or multiple)
    try:
        # Try to parse as space-separated numbers
        numbers = [int(x.strip()) for x in choice.split()]
        selected_items = []
        
        for num in numbers:
            # Convert to 0-based index (subtract 1 since items start at index 1)
            item_idx = num - 1
            if 0 <= item_idx < len(all_items):
                selected_items.append(all_items[item_idx])
            else:
                print_warning(f"Invalid index: {num}. Skipping.")
        
        if not selected_items:
            print_error("No valid items selected!")
            return None, []
        
        # Determine if single or multiple
        if len(selected_items) == 1:
            return 'single', selected_items
        else:
            return 'multiple', selected_items
    
    except ValueError:
        print_error("Invalid input! Please enter 'a', '0', or numbers (e.g., '3' or '1 3 5').")
        return None, []


def prompt_zip_mode():
    """Prompt user to select normal or smart zip mode.
    
    Returns:
        str: 'normal' or 'smart', or None if cancelled
    """
    print(f"\n{Colors.BOLD}Filter 1: (include/exclude common cache/build files):{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
    print(f"1. {Colors.OKGREEN}Normal ZIP{Colors.ENDC} (include everything)")
    print(f"2. {Colors.OKGREEN}Smart ZIP{Colors.ENDC} (exclude common cache/build files)")
    print()
    print(f"{Colors.WARNING}Smart ZIP will exclude:{Colors.ENDC}")
    
    # Display exclusions in a nice format
    exclusions_display = ', '.join(ZIP_EXCLUSIONS[:15])
    if len(ZIP_EXCLUSIONS) > 15:
        exclusions_display += f", ... and {len(ZIP_EXCLUSIONS) - 15} more"
    print(f"  {exclusions_display}")
    print(f"{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
    
    choice = smart_input(f"{Colors.OKCYAN}Enter choice (1/2): {Colors.ENDC}")
    
    if choice == '1':
        return 'normal'
    elif choice == '2':
        return 'smart'
    else:
        print_error("Invalid choice!")
        return None


def prompt_extension_filter():
    """Prompt user to filter files by extensions.
    
    Returns:
        list: List of extensions (without dots) or None for all files
    """
    print(f"\n{Colors.BOLD}Filter 2: (select specific file types):{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}Enter file extensions separated by spaces{Colors.ENDC} (e.g., py md txt)")
    print(f"{Colors.OKGREEN}Press Enter{Colors.ENDC} to include all file types (default)")
    print()
    print(f"{Colors.WARNING}Examples:{Colors.ENDC}")
    print(f"  py md      - Include only .py and .md files")
    print(f"  txt log    - Include only .txt and .log files")
    print(f"  js css html - Include only .js, .css and .html files")
    print(f"{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
    
    extensions_input = smart_input(f"{Colors.OKCYAN}Enter extensions (or press Enter for all): {Colors.ENDC}")
    
    if not extensions_input:
        # Empty input = include all files
        return None
    
    # Parse extensions (case-insensitive, remove dots if user added them)
    extensions = []
    for ext in extensions_input.split():
        ext = ext.strip().lower()
        if ext.startswith('.'):
            ext = ext[1:]  # Remove leading dot
        if ext:
            extensions.append(ext)
    
    if not extensions:
        return None
    
    print(f"\n{Colors.OKGREEN}Will include files with extensions: {', '.join('.' + e for e in extensions)}{Colors.ENDC}")
    return extensions


def collect_files_by_extension(items: List[Path], extensions: List[str], zip_mode: str) -> List[Tuple[Path, Path]]:
    """Collect files matching specific extensions from items, preserving folder structure.
    
    Args:
        items: List of Path objects (files or folders) to search
        extensions: List of extensions (without dots, lowercase) to include
        zip_mode: 'normal' or 'smart' - affects which folders to search in
    
    Returns:
        List of tuples (file_path, arcname) where arcname preserves folder structure
    """
    collected_files = []
    
    for item in items:
        if item.is_file():
            # Check if file matches extension filter
            file_ext = item.suffix.lower()[1:] if item.suffix else ''  # Remove dot and lowercase
            if file_ext in extensions:
                collected_files.append((item, item.name))
        
        elif item.is_dir():
            # Recursively search directory for matching files
            for file_path in item.rglob('*'):
                if file_path.is_file():
                    # Check if we should skip this file's parent folder (smart mode)
                    if zip_mode == 'smart' and should_exclude_from_zip(file_path, ZIP_EXCLUSIONS):
                        continue
                    
                    # Check if file matches extension filter
                    file_ext = file_path.suffix.lower()[1:] if file_path.suffix else ''
                    if file_ext in extensions:
                        # Preserve folder structure relative to parent of selected item
                        arcname = file_path.relative_to(item.parent)
                        collected_files.append((file_path, arcname))
    
    return collected_files


def create_zip_archive(items_to_zip: List[Path], zip_path: Path, mode: str = 'smart', extensions: List[str] = None):
    """Create a zip archive from the given items.
    
    Args:
        items_to_zip: List of Path objects (files or folders) to zip
        zip_path: Path where the zip file will be created
        mode: 'normal' or 'smart' (smart excludes files based on ZIP_EXCLUSIONS)
        extensions: Optional list of extensions (without dots) to filter by. None = all files
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        files_added = 0
        files_skipped = 0
        
        # If extension filter is active, collect matching files first
        if extensions:
            files_to_add = collect_files_by_extension(items_to_zip, extensions, mode)
            print_info(f"Found {len(files_to_add)} files matching extensions: {', '.join('.' + e for e in extensions)}")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path, arcname in files_to_add:
                    try:
                        zipf.write(file_path, arcname)
                        files_added += 1
                        
                        if files_added % 100 == 0:
                            print_info(f"Added {files_added} files...")
                    except Exception as e:
                        print_warning(f"Skipped {arcname}: {str(e)}")
                        files_skipped += 1
        else:
            # No extension filter - original behavior
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for item in items_to_zip:
                    if item.is_file():
                        # Single file
                        if mode == 'smart' and should_exclude_from_zip(item, ZIP_EXCLUSIONS):
                            files_skipped += 1
                            continue
                        
                        try:
                            zipf.write(item, item.name)
                            files_added += 1
                            print_info(f"Added: {item.name}")
                        except Exception as e:
                            print_warning(f"Skipped {item.name}: {str(e)}")
                            files_skipped += 1
                    
                    elif item.is_dir():
                        # Directory - recursively add all contents
                        for file_path in item.rglob('*'):
                            if file_path.is_file():
                                if mode == 'smart' and should_exclude_from_zip(file_path, ZIP_EXCLUSIONS):
                                    files_skipped += 1
                                    continue
                                
                                try:
                                    # Create archive path relative to the folder being zipped
                                    arcname = file_path.relative_to(item.parent)
                                    zipf.write(file_path, arcname)
                                    files_added += 1
                                    
                                    if files_added % 100 == 0:
                                        print_info(f"Added {files_added} files...")
                                
                                except Exception as e:
                                    print_warning(f"Skipped {file_path.relative_to(item.parent)}: {str(e)}")
                                    files_skipped += 1
        
        # Display summary
        zip_size = zip_path.stat().st_size / (1024**2)
        print(f"\n{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
        print_success(f"ZIP archive created successfully!")
        print(f"  Location: {zip_path}")
        print(f"  Files added: {files_added}")
        print(f"  Files skipped: {files_skipped}")
        print(f"  Archive size: {zip_size:.2f} MB")
        print(f"{Colors.OKCYAN}{'\u2500' * 70}{Colors.ENDC}")
        
        return True
    
    except Exception as e:
        print_error(f"Failed to create ZIP archive: {str(e)}")
        # Try to clean up partial zip
        if zip_path.exists():
            try:
                zip_path.unlink()
                print_info("Cleaned up partial ZIP file.")
            except:
                pass
        return False


def create_folder_zip():
    """Main function to create a ZIP archive of selected folders/files."""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print_header("CREATE FOLDER/FILE ZIP")
    print(f"{Colors.BOLD}Current directory:{Colors.ENDC} {Path.cwd()}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    # List folders and files
    folders, files = list_folders_and_files()
    
    if not folders and not files:
        print_error("No folders or files found in current directory!")
        return
    
    # Get user selection
    selection_type, selected_items = get_user_selection_for_zip(folders, files)
    
    if not selected_items:
        print_warning("No items selected. Operation cancelled.")
        return
    
    # Display what will be zipped
    print(f"\n{Colors.BOLD}Selected items to zip:{Colors.ENDC}")
    for item in selected_items:
        icon = "[DIR]" if item.is_dir() else "[FILE]"
        print(f"  {icon} {item.name}")
    
    # Get zip mode - only prompt if selection type is 'all' (user entered 'a')
    if selection_type == 'all':
        zip_mode = prompt_zip_mode()
        
        if not zip_mode:
            print_warning("Operation cancelled.")
            return
    else:
        # Numbered selection (single or multiple) - always use normal mode (no exclusions)
        zip_mode = 'normal'
        print_info("\nUsing Normal ZIP mode (no exclusions) for manual selection.")
    
    # Get extension filter (Filter 2)
    extensions = prompt_extension_filter()
    
    # Generate zip filename based on selection
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if selection_type == 'single':
        # Single item: use its name
        base_name = selected_items[0].stem if selected_items[0].is_file() else selected_items[0].name
        zip_filename = f"{base_name}.zip"
    else:
        # Multiple or all: use descriptive name
        zip_filename = f"selected_folders_backup_{timestamp}.zip"
    
    zip_path = Path.cwd() / zip_filename
    
    # Check if file already exists
    if zip_path.exists():
        overwrite = smart_input(f"\n{Colors.WARNING}File {zip_filename} already exists. Overwrite? (y/N): {Colors.ENDC}").lower()
        if overwrite not in ['y', 'yes']:
            print_warning("Operation cancelled.")
            return
    
    # Confirm operation
    mode_text = f"{Colors.OKGREEN}Smart ZIP{Colors.ENDC}" if zip_mode == 'smart' else f"{Colors.OKGREEN}Normal ZIP{Colors.ENDC}"
    print(f"\n{Colors.BOLD}Ready to create:{Colors.ENDC} {mode_text}")
    print(f"{Colors.BOLD}Output file:{Colors.ENDC} {zip_filename}")
    confirm = smart_input(f"\n{Colors.OKCYAN}Proceed? (Y/n): {Colors.ENDC}").lower()
    
    if confirm in ['', 'y', 'yes']:
        print(f"\n{Colors.BOLD}Creating ZIP archive...{Colors.ENDC}")
        create_zip_archive(selected_items, zip_path, zip_mode, extensions)
    else:
        print_warning("Operation cancelled.")


def show_last_modified_files():
    """Show last modified files (most recent first)"""
    
    while True:
        print_header("LAST MODIFIED FILES")
        
        # Ask user for number of entries (press Enter to use default)
        default_count = 10
        count_input = smart_input(f"{Colors.OKCYAN}How many files to show? [{default_count}] (or 0 to go back): {Colors.ENDC}")
        
        if count_input == '0':
            return
        
        try:
            count = int(count_input) if count_input else default_count
            if count <= 0:
                print_error("Count must be positive!")
                continue
        except ValueError:
            print_error("Invalid number!")
            continue
        
        # Valid count - proceed with scanning
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
                smart_input("\nPress Enter to continue...")
                continue
            
            # Sort by modification time (most recent first)
            files_with_mtime.sort(key=lambda x: x[1], reverse=True)
            
            # Display the top N files
            print(f"\n{Colors.BOLD}Top {count} most recently modified files:{Colors.ENDC}\n")
            
            # Prepare table data
            table_rows = []
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
                    
                    table_rows.append([
                        f"[{idx}]",
                        str(rel_path),
                        mod_time,
                        size_str
                    ])
                    
                except Exception as e:
                    print_warning(f"Error displaying file: {str(e)}")
                    continue
            
            # Print table
            from diagnostics_abasu_util import format_table
            headers = ["#", "File Path", "Modified", "Size"]
            print(format_table(
                table_rows, 
                headers=headers, 
                padding=2, 
                max_widths=[None, 80, None, None],
                wrap=[False, True, False, False],
                truncate=False
            ))
            
            total_files = len(files_with_mtime)
            print(f"\n{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
            print_info(f"Total files scanned: {total_files}")
            
            smart_input("\nPress Enter to continue...")
            # Loop back to ask for count again
            
        except Exception as e:
            print_error(f"Error scanning files: {str(e)}")
            smart_input("\nPress Enter to continue...")
            # Loop back to ask for count again


def view_archive():
    """View contents of a ZIP archive without extracting"""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print_header("VIEW ARCHIVE CONTENTS")
    print(f"{Colors.BOLD}Current directory:{Colors.ENDC} {Path.cwd()}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    # Find all zip files in current directory
    current_dir = Path.cwd()
    zip_files = list(current_dir.glob('*.zip'))
    
    if not zip_files:
        print_warning("No ZIP files found in current directory!")
        
        # Ask if user wants to specify a path
        custom_path = smart_input(f"\n{Colors.OKCYAN}Enter path to ZIP file (or press Enter to cancel): {Colors.ENDC}")
        if not custom_path:
            print_info("Operation cancelled.")
            return
        
        zip_path = Path(custom_path)
        if not zip_path.exists() or not zip_path.suffix.lower() == '.zip':
            print_error("Invalid ZIP file path!")
            return
        
        zip_files = [zip_path]
    
    # Display available zip files
    if len(zip_files) > 1:
        print(f"\n{Colors.BOLD}Available ZIP files:{Colors.ENDC}")
        for idx, zip_file in enumerate(zip_files, 1):
            size = zip_file.stat().st_size / (1024**2)
            print(f"{idx}. {zip_file.name} ({size:.2f} MB)")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Select ZIP file to view (1-{len(zip_files)}): {Colors.ENDC}")
        try:
            zip_idx = int(choice) - 1
            selected_zip = zip_files[zip_idx]
        except (ValueError, IndexError):
            print_error("Invalid selection!")
            return
    else:
        selected_zip = zip_files[0]
    
    # Display archive information
    print(f"\n{Colors.BOLD}Archive:{Colors.ENDC} {selected_zip.name}")
    print(f"{Colors.BOLD}Size:{Colors.ENDC} {selected_zip.stat().st_size / (1024**2):.2f} MB")
    print(f"{Colors.BOLD}Location:{Colors.ENDC} {selected_zip}")
    
    try:
        with zipfile.ZipFile(selected_zip, 'r') as zipf:
            file_list = zipf.infolist()
            
            # Calculate total uncompressed size
            total_uncompressed = sum(item.file_size for item in file_list)
            total_compressed = sum(item.compress_size for item in file_list)
            compression_ratio = (1 - total_compressed / total_uncompressed) * 100 if total_uncompressed > 0 else 0
            
            print(f"{Colors.BOLD}Total items:{Colors.ENDC} {len(file_list)}")
            print(f"{Colors.BOLD}Uncompressed size:{Colors.ENDC} {total_uncompressed / (1024**2):.2f} MB")
            print(f"{Colors.BOLD}Compression ratio:{Colors.ENDC} {compression_ratio:.1f}%")
            
            # Count directories and files
            dirs = [item for item in file_list if item.is_dir()]
            files = [item for item in file_list if not item.is_dir()]
            
            print(f"{Colors.BOLD}Directories:{Colors.ENDC} {len(dirs)}")
            print(f"{Colors.BOLD}Files:{Colors.ENDC} {len(files)}")
            
            # View options loop - allow multiple views without exiting
            while True:
                # Display view options
                print(f"\n{Colors.BOLD}View options:{Colors.ENDC}")
                print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
                print(highlight_keywords("1. View all items (detailed)"))
                print(highlight_keywords("2. View files only"))
                print(highlight_keywords("3. View directories only"))
                print(highlight_keywords("4. Search for specific file/folder"))
                print("0. Back")
                print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
                
                view_choice = smart_input(f"\n{Colors.OKCYAN}Enter choice (0-4): {Colors.ENDC}")
                
                if view_choice == '0':
                    return
                elif view_choice == '1':
                    # View all items
                    print(f"\n{Colors.BOLD}All items in archive:{Colors.ENDC}\n")
                    print(f"{Colors.BOLD}{'Name':<50} {'Size':<12} {'Compressed':<12} {'Modified'}{Colors.ENDC}")
                    print(f"{Colors.OKCYAN}{'─' * 95}{Colors.ENDC}")
                    
                    for item in file_list:
                        name = item.filename
                        if item.is_dir():
                            name = f"[DIR] {name}"
                        
                        size_str = f"{item.file_size / 1024:.1f} KB" if item.file_size < 1024**2 else f"{item.file_size / (1024**2):.1f} MB"
                        comp_str = f"{item.compress_size / 1024:.1f} KB" if item.compress_size < 1024**2 else f"{item.compress_size / (1024**2):.1f} MB"
                        modified = f"{item.date_time[0]}-{item.date_time[1]:02d}-{item.date_time[2]:02d} {item.date_time[3]:02d}:{item.date_time[4]:02d}"
                        
                        # Truncate long names
                        display_name = name if len(name) <= 48 else name[:45] + "..."
                        print(f"{display_name:<50} {size_str:<12} {comp_str:<12} {modified}")
                    
                    print(f"\n{Colors.OKGREEN}Total: {len(file_list)} items{Colors.ENDC}")
                    smart_input("\nPress Enter to continue...")
                
                elif view_choice == '2':
                    # View files only
                    print(f"\n{Colors.BOLD}Files in archive:{Colors.ENDC}\n")
                    print(f"{Colors.BOLD}{'Name':<50} {'Size':<12} {'Modified'}{Colors.ENDC}")
                    print(f"{Colors.OKCYAN}{'─' * 75}{Colors.ENDC}")
                    
                    for item in files:
                        name = item.filename
                        size_str = f"{item.file_size / 1024:.1f} KB" if item.file_size < 1024**2 else f"{item.file_size / (1024**2):.1f} MB"
                        modified = f"{item.date_time[0]}-{item.date_time[1]:02d}-{item.date_time[2]:02d} {item.date_time[3]:02d}:{item.date_time[4]:02d}"
                        
                        display_name = name if len(name) <= 48 else name[:45] + "..."
                        print(f"{display_name:<50} {size_str:<12} {modified}")
                    
                    print(f"\n{Colors.OKGREEN}Total: {len(files)} files{Colors.ENDC}")
                    smart_input("\nPress Enter to continue...")
                
                elif view_choice == '3':
                    # View directories only
                    print(f"\n{Colors.BOLD}Directories in archive:{Colors.ENDC}\n")
                    
                    for item in dirs:
                        print(f"  [DIR] {item.filename}")
                    
                    print(f"\n{Colors.OKGREEN}Total: {len(dirs)} directories{Colors.ENDC}")
                    smart_input("\nPress Enter to continue...")
                
                elif view_choice == '4':
                    # Search for specific file/folder
                    search_term = smart_input(f"\n{Colors.OKCYAN}Enter search term: {Colors.ENDC}")
                    
                    if not search_term:
                        print_warning("No search term provided.")
                        continue
                    
                    matches = [item for item in file_list if search_term.lower() in item.filename.lower()]
                    
                    if matches:
                        print(f"\n{Colors.BOLD}Found {len(matches)} match(es):{Colors.ENDC}\n")
                        print(f"{Colors.BOLD}{'Name':<50} {'Size':<12} {'Modified'}{Colors.ENDC}")
                        print(f"{Colors.OKCYAN}{'─' * 75}{Colors.ENDC}")
                        
                        for item in matches:
                            name = f"[DIR] {item.filename}" if item.is_dir() else item.filename
                            size_str = f"{item.file_size / 1024:.1f} KB" if item.file_size < 1024**2 else f"{item.file_size / (1024**2):.1f} MB"
                            modified = f"{item.date_time[0]}-{item.date_time[1]:02d}-{item.date_time[2]:02d} {item.date_time[3]:02d}:{item.date_time[4]:02d}"
                            
                            display_name = name if len(name) <= 48 else name[:45] + "..."
                            print(f"{display_name:<50} {size_str:<12} {modified}")
                    else:
                        print_warning(f"No matches found for '{search_term}'.")
                    
                    smart_input("\nPress Enter to continue...")
            
    except zipfile.BadZipFile:
        print_error("Invalid or corrupted ZIP file!")
    except Exception as e:
        print_error(f"Error reading ZIP file: {str(e)}")


def unzip_archive():
    """Extract/unzip a ZIP archive with destination options"""
    print(f"\n{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print_header("UNZIP ARCHIVE")
    print(f"{Colors.BOLD}Current directory:{Colors.ENDC} {Path.cwd()}")
    print(f"{Colors.BOLD}{'='*70}{Colors.ENDC}")
    
    # Find all zip files in current directory
    current_dir = Path.cwd()
    zip_files = list(current_dir.glob('*.zip'))
    
    if not zip_files:
        print_warning("No ZIP files found in current directory!")
        
        # Ask if user wants to specify a path
        custom_path = smart_input(f"\n{Colors.OKCYAN}Enter path to ZIP file (or press Enter to cancel): {Colors.ENDC}")
        if not custom_path:
            print_info("Operation cancelled.")
            return
        
        zip_path = Path(custom_path)
        if not zip_path.exists() or not zip_path.suffix.lower() == '.zip':
            print_error("Invalid ZIP file path!")
            return
        
        zip_files = [zip_path]
    
    # Display available zip files
    if len(zip_files) > 1:
        print(f"\n{Colors.BOLD}Available ZIP files:{Colors.ENDC}")
        for idx, zip_file in enumerate(zip_files, 1):
            size = zip_file.stat().st_size / (1024**2)
            print(f"{idx}. {zip_file.name} ({size:.2f} MB)")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Select ZIP file to extract (1-{len(zip_files)}): {Colors.ENDC}")
        try:
            zip_idx = int(choice) - 1
            selected_zip = zip_files[zip_idx]
        except (ValueError, IndexError):
            print_error("Invalid selection!")
            return
    else:
        selected_zip = zip_files[0]
    
    # Display selected file info
    print(f"\n{Colors.BOLD}Selected ZIP file:{Colors.ENDC} {selected_zip.name}")
    print(f"{Colors.BOLD}Size:{Colors.ENDC} {selected_zip.stat().st_size / (1024**2):.2f} MB")
    
    # Preview contents
    try:
        with zipfile.ZipFile(selected_zip, 'r') as zipf:
            file_list = zipf.namelist()
            print(f"{Colors.BOLD}Contains:{Colors.ENDC} {len(file_list)} items")
            
            # Show first few items
            preview_count = min(5, len(file_list))
            print(f"\n{Colors.BOLD}Preview (first {preview_count} items):{Colors.ENDC}")
            for item in file_list[:preview_count]:
                print(f"  - {item}")
            if len(file_list) > preview_count:
                print(f"  ... and {len(file_list) - preview_count} more")
    except zipfile.BadZipFile:
        print_error("Invalid or corrupted ZIP file!")
        return
    except Exception as e:
        print_error(f"Error reading ZIP file: {str(e)}")
        return
    
    # Ask for destination
    print(f"\n{Colors.BOLD}Extract destination options:{Colors.ENDC}")
    print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
    print(highlight_keywords(f"1. Extract here (current directory)"))
    print(highlight_keywords(f"2. Extract to folder named '{selected_zip.stem}' (recommended)"))
    print(highlight_keywords(f"3. Extract to custom folder (you choose name)"))
    print(f"0. Cancel")
    print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
    
    dest_choice = smart_input(f"\n{Colors.OKCYAN}Enter choice (0-3): {Colors.ENDC}")
    
    if dest_choice == '0':
        print_info("Operation cancelled.")
        return
    elif dest_choice == '1':
        # Extract to current directory
        extract_path = current_dir
        print_warning(f"Files will be extracted directly to: {extract_path}")
    elif dest_choice == '2':
        # Extract to folder named after zip file
        extract_path = current_dir / selected_zip.stem
        print_info(f"Files will be extracted to: {extract_path}")
    elif dest_choice == '3':
        # Custom folder name
        folder_name = smart_input(f"\n{Colors.OKCYAN}Enter folder name: {Colors.ENDC}")
        if not folder_name:
            print_error("Folder name cannot be empty!")
            return
        extract_path = current_dir / folder_name
        print_info(f"Files will be extracted to: {extract_path}")
    else:
        print_error("Invalid choice!")
        return
    
    # Check if destination exists
    if extract_path.exists() and extract_path != current_dir:
        print_warning(f"Destination folder already exists: {extract_path}")
        overwrite = smart_input(f"{Colors.WARNING}Continue and potentially overwrite files? (y/N): {Colors.ENDC}").lower()
        if overwrite not in ['y', 'yes']:
            print_info("Operation cancelled.")
            return
    
    # Create destination folder if needed
    if not extract_path.exists():
        try:
            extract_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created destination folder: {extract_path}")
        except Exception as e:
            print_error(f"Failed to create destination folder: {str(e)}")
            return
    
    # Confirm extraction
    print(f"\n{Colors.BOLD}Ready to extract:{Colors.ENDC}")
    print(f"  From: {selected_zip.name}")
    print(f"  To: {extract_path}")
    print(f"  Items: {len(file_list)}")
    
    confirm = smart_input(f"\n{Colors.OKCYAN}Proceed with extraction? (Y/n): {Colors.ENDC}").lower()
    
    if confirm not in ['', 'y', 'yes']:
        print_info("Operation cancelled.")
        return
    
    # Extract the archive
    print(f"\n{Colors.BOLD}Extracting...{Colors.ENDC}")
    
    try:
        extracted_count = 0
        with zipfile.ZipFile(selected_zip, 'r') as zipf:
            for member in file_list:
                try:
                    zipf.extract(member, extract_path)
                    extracted_count += 1
                    
                    # Show progress for large archives
                    if extracted_count % 50 == 0:
                        print_info(f"Extracted {extracted_count}/{len(file_list)} items...")
                except Exception as e:
                    print_warning(f"Failed to extract {member}: {str(e)}")
        
        # Display success summary
        print(f"\n{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
        print_success(f"Extraction completed successfully!")
        print(f"  Extracted: {extracted_count}/{len(file_list)} items")
        print(f"  Location: {extract_path}")
        print(f"{Colors.OKCYAN}{'─' * 70}{Colors.ENDC}")
        
    except Exception as e:
        print_error(f"Error during extraction: {str(e)}")


def manage_archive_menu():
    """Archive management submenu"""
    while True:
        print("\n" + "="*70)
        print_header("MANAGE ARCHIVE")
        
        print(highlight_keywords("1. Unzip/Extract Archive"))
        print(highlight_keywords("2. View Archive Contents (without extracting)"))
        print("0. Back to File Operations")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if choice == '0':
            break
        elif choice == '1':
            unzip_archive()
            smart_input("\nPress Enter to continue...")
        elif choice == '2':
            view_archive()
            smart_input("\nPress Enter to continue...")


def file_operations_menu():
    """File operations submenu"""
    while True:
        print("\n" + "="*70)
        print_header("FILE OPERATIONS")
        
        print(highlight_keywords("1. Delete Cache Folders (__pycache__, etc.)"))
        print(highlight_keywords("2. Delete Specific File/Folder"))
        print(highlight_keywords("3. Show Last Modified Files (Most Recent First)"))
        print(highlight_keywords("4. Create ZIP Archive (Normal/Smart)"))
        print(highlight_keywords("5. Manage Archive"))
        print("0. Back to Main Menu")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if choice == '0':
            break
        elif choice == '1':
            delete_cache_folders()
            smart_input("\nPress Enter to continue...")
        elif choice == '2':
            delete_specific_path()
            smart_input("\nPress Enter to continue...")
        elif choice == '3':
            show_last_modified_files()
        elif choice == '4':
            create_folder_zip()
            smart_input("\nPress Enter to continue...")
        elif choice == '5':
            manage_archive_menu()


def settings_menu():
    """Settings submenu"""
    while True:
        print("\n" + "="*70)
        print_header("SETTINGS")
        print(f"Current base directory: {SESSION_BASE_DIR}")

        print(highlight_keywords("1. Set Base Directory for Session"))
        print("0. Back to Main Menu")

        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")

        if choice == '0':
            break
        elif choice == '1':
            set_base_directory()
            smart_input("\nPress Enter to continue...")
        else:
            print_error("Invalid choice! Please try again.")


def system_diagnostics_menu():
    """System diagnostics submenu"""
    while True:
        print("\n" + "="*70)
        print_header("SYSTEM DIAGNOSTICS")
        
        print("1. System Information (CPU, RAM, Disk)")
        print("2. Python Environment")
        print(highlight_keywords("3. Environment Variables (View/Add/Modify)"))
        print("4. Full Diagnostic Report")
        print("0. Back to Main Menu")
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
        if choice == '0':
            break
        elif choice == '1':
            get_system_info()
        elif choice == '2':
            get_python_environment()
        elif choice == '3':
            environment_variables_menu()
        elif choice == '4':
            get_system_info()
            get_python_environment()


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
        
        choice = smart_input(f"\n{Colors.OKCYAN}Enter choice (or chain like '3,3,20'): {Colors.ENDC}")
        
        # Check if user entered a chain command (contains delimiters)
        if choice and any(sep in choice for sep in [',', 'y', ' ']) and choice != '0':
            parse_input_chain(choice)
            # Re-get first value from queue
            if INPUT_QUEUE:
                choice = smart_input(f"\n{Colors.OKCYAN}Enter choice: {Colors.ENDC}")
        
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
            
            smart_input("\nPress Enter to continue...")

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
