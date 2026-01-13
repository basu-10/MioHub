# flask
from flask import Flask, session
import os
from datetime import timedelta

# helper
import config

# custom
from extensions import db, login_manager

#values
basedir = os.path.abspath(os.path.dirname(__file__))# this files location

# configs
DB_NAME = config.DB_NAME
DB_USER = config.DB_USER
DB_PASSWORD = config.DB_PASSWORD
DB_PORT = config.DB_PORT
DB_HOST = config.DB_HOST

app = Flask(__name__)
app.secret_key = config.SECRET_KEY or os.urandom(24)  # Use fixed secret key for persistent sessions
app.permanent_session_lifetime = timedelta(days=30)  # Session lasts 30 days
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Database connection pool settings for better reliability
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Verify connections before use
    'pool_recycle': 300,    # Recycle connections every 5 minutes
    'pool_timeout': 20,     # Wait 20 seconds for connection
    'max_overflow': 0,      # Don't create extra connections beyond pool size
}

# Set maximum content length to 1000MB for large file uploads and whiteboard data
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 1000MB in bytes

# Additional configurations to handle large requests
app.config['MAX_FORM_MEMORY_SIZE'] = 1000 * 1024 * 1024  # 1000MB
app.config['WTF_CSRF_TIME_LIMIT'] = None  # Disable CSRF time limit for large uploads

from blueprints import bps
for bp in bps:
    print(f"registering: {bp}")
    app.register_blueprint(bp)

# Diagnostic logging for API configuration (startup check)
import sys
api_key = config.GROQ_API_KEY if hasattr(config, 'GROQ_API_KEY') else '[NOT FOUND]'
key_preview = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 and api_key != '[NOT FOUND]' else api_key
print("="*60, flush=True)
print(f"[STARTUP] Flask app initialized", flush=True)
print(f"[STARTUP] Provider: {getattr(config, 'PROVIDER', '[NOT SET]')}", flush=True)
print(f"[STARTUP] GROQ_API_KEY: {key_preview}", flush=True)
print(f"[STARTUP] Python: {sys.version}", flush=True)
print("="*60, flush=True)

# code starts
@app.context_processor
def inject_current_folder():
    return {
        'current_folder_id': session.get('current_folder_id')
    }

db.init_app(app)

login_manager.init_app(app)
login_manager.login_view = "p2_bp.login"

if __name__ == "__main__":
    # For development: increase threaded mode and request handler limits
    app.run(debug=True, host='0.0.0.0', port=5555, threaded=True)