"""
WSGI configuration for MioHub production deployment.
This file exists on PythonAnywhere at /var/www/basu001_pythonanywhere_com_wsgi.py
and is used to load environment variables for production deployment.
"""

import os
import sys

# Update this path to the absolute project root on the target host
PROJECT_HOME = '/home/basu001/mysite/MioHub'
if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

# Point to the production env file under ~/.local/share/miohub.
# Override via MIOHUB_ENV_FILE / MIOHUB_ENV_DIR if needed.
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

# Load environment variables before importing the app (ensures config.require_env succeeds)
import config

# Force reload with overwrite in case the host provided conflicting values
config.load_env_file(overwrite=True)

# Expose the WSGI application object
from flask_app import app as application  # noqa: E402
