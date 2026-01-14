"""
WSGI configuration for MioHub local development.
This file is for running the application on local machine (MX Linux).

with gunicorn:
gunicorn wsgi_local:application --bind 0.0.0.0:5555 --workers 4 --reload
$ .venv/bin/gunicorn wsgi_local:application --bind 0.0.0.0:5555 --workers 4

"""

import os
import sys

# Use the prod.env file for local testing (same as production)
os.environ.setdefault("MIOHUB_ENV_FILE", "prod.env")

# Load environment variables before importing the app
import config
config.load_env_file(overwrite=True)

# Import the Flask application
from flask_app import app as application

if __name__ == '__main__':
    # For direct testing (not recommended, use gunicorn instead)
    application.run(host='0.0.0.0', port=5555, debug=True)
