"""
WSGI configuration for MioHub local development.
This file is for running the application on local machine (MX Linux).

run only with gunicorn from terminal, e.g.:
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

#debugging \\
if __name__ == "__main__":
    application.run(debug=True)