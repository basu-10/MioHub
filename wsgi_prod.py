"""
WSGI configuration for MioHub production deployment.
This file exists on PythonAnywhere at /var/www/basu001_pythonanywhere_com_wsgi.py
and is used to load environment variables for production deployment.
"""

import os
import sys
import traceback
from datetime import datetime

# Set up error logging to a file that we can check
ERROR_LOG = '/home/basu001/mysite/wsgi_errors.log'

def log_error(message):
    """Write error messages to a log file for debugging."""
    try:
        with open(ERROR_LOG, 'a') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n{'='*80}\n")
            f.write(f"[{timestamp}] {message}\n")
            f.write(f"{'='*80}\n")
    except Exception as e:
        # If we can't write to log, at least print to stderr
        print(f"WSGI ERROR (logging failed): {e}", file=sys.stderr)
        print(f"Original message: {message}", file=sys.stderr)

try:
    log_error("WSGI initialization started")
    
    # Update this path to the absolute project root on the target host
    PROJECT_HOME = '/home/basu001/mysite/MioHub'
    log_error(f"PROJECT_HOME set to: {PROJECT_HOME}")
    log_error(f"PROJECT_HOME exists: {os.path.exists(PROJECT_HOME)}")
    
    if PROJECT_HOME not in sys.path:
        sys.path.insert(0, PROJECT_HOME)
        log_error(f"Added PROJECT_HOME to sys.path")
    
    log_error(f"Current sys.path: {sys.path[:3]}")  # Log first 3 entries
    log_error(f"Current working directory: {os.getcwd()}")
    
    # Point to the production env file under ~/.local/share/miohub.
    # Override via MIOHUB_ENV_FILE / MIOHUB_ENV_DIR if needed.
    os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")
    log_error(f"MIOHUB_ENV_FILE set to: {os.environ.get('MIOHUB_ENV_FILE')}")
    
    # Load environment variables before importing the app (ensures config.require_env succeeds)
    log_error("Attempting to import config module")
    import config
    log_error("Config module imported successfully")
    
    # Force reload with overwrite in case the host provided conflicting values
    log_error("Attempting to load env file")
    env_path = config.load_env_file(overwrite=True)
    log_error(f"Env file loaded from: {env_path}")
    
    # Expose the WSGI application object
    log_error("Attempting to import flask_app")
    from flask_app import app as application  # noqa: E402
    log_error("Flask application imported successfully")
    log_error("WSGI initialization completed successfully")
    
except Exception as e:
    error_msg = f"FATAL ERROR during WSGI initialization:\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
    log_error(error_msg)
    
    # Also print to stderr for immediate visibility
    print(error_msg, file=sys.stderr)
    
    # Re-raise the exception so PythonAnywhere shows it
    raise
