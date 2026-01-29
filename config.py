"""
Configuration module for the Flask application.
Secrets and connection details live in .env files under ~/.local/share/miohub.
At import time, the env loader reads that file, sanitizes values, and injects
them into os.environ before the rest of the configuration is resolved.
"""

import os
from pathlib import Path


def require_env(key: str, default: str | None = None) -> str:
    """Fetch an environment variable or fail fast with a clear message."""
    value = os.getenv(key, default)
    if value in (None, ""):
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _env(key: str, default: str) -> str:
    """Backward-compatible helper for optional values with safe defaults."""
    value = os.getenv(key)
    return default if value in (None, "") else value


# =============================================================================
# ENV FILE HANDLING
# =============================================================================

ENV_DIR = Path(os.getenv("MIOHUB_ENV_DIR", Path.home() / ".local/share/miohub"))
DEFAULT_ENV_FILE = os.getenv("MIOHUB_ENV_FILE", ".env")


def _strip_quotes(value: str) -> str:
    """Remove symmetrical single/double quotes around a value."""
    if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
        return value[1:-1]
    return value


def load_env_file(env_file: str | os.PathLike | None = None, *, overwrite: bool = False) -> Path | None:
    """
    Load environment variables from a file under ~/.local/share/miohub.

    Args:
        env_file: File name or absolute path. Defaults to DEFAULT_ENV_FILE.
        overwrite: When True, values from the file replace existing os.environ.

    Returns:
        Path to the loaded file, or None if no file was found.
    """
    target = Path(env_file) if env_file else Path(DEFAULT_ENV_FILE)
    if not target.is_absolute():
        target = ENV_DIR / target

    if not target.exists():
        return None

    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())

        if not key:
            continue

        if overwrite or key not in os.environ:
            os.environ[key] = value

    return target


# Load env file before resolving required values. Idempotent on repeated imports.
_LOADED_ENV_PATH = load_env_file()

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# For PythonAnywhere deployment, use these values:
# DB_NAME = "basu001$default"
# DB_USER = "basu001"
# DB_PASSWORD = "sijofghdfbu134698"
# DB_PORT = "3306"
# DB_HOST = "basu001.mysql.pythonanywhere-services.com"

# For local development: values must be injected by wsgi_* (no repo defaults)
DB_NAME = require_env("DB_NAME")
DB_USER = require_env("DB_USER")
DB_PASSWORD = require_env("DB_PASSWORD")
DB_PORT = require_env("DB_PORT")
DB_HOST = require_env("DB_HOST")


# =============================================================================
# FLASK CONFIGURATION
# =============================================================================

# Secret key for Flask sessions (must be consistent for persistent login)
# Generate a new one with: python -c "import secrets; print(secrets.token_hex(24))"
SECRET_KEY = require_env("SECRET_KEY")


# =============================================================================
# MAIN CHAT - LLM PROVIDER CONFIGURATION (Groq)
# =============================================================================

# Provider for main chat (using Groq)
PROVIDER = _env("PROVIDER", "groq")

# Groq API Configuration
GROQ_API_KEY = require_env("GROQ_API_KEY") if PROVIDER.lower() == "groq" else _env("GROQ_API_KEY", "")

# Default model for main chat (Groq)
DEFAULT_CHAT_MODEL = "llama-3.3-70b-versatile"

# Available models for main chat (Groq models)
AVAILABLE_CHAT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "gemma-7b-it",
]

# Memory context template for main chat
CHAT_MEMORY_TEMPLATE = "Context/summaries from memory:\n{memory_items}"

# How to format each memory item in context
CHAT_MEMORY_ITEM_FORMAT = "- {item}"


# Fireworks Configuration (uncomment to use)
# FIREWORKS_API_KEY = "your_key_here"

# Together Configuration (uncomment to use)
# TOGETHER_API_KEY = "your_key_here"


# =============================================================================
# AI CONFIGURATION
# =============================================================================

# Delimiter used in AI responses
AI_DELIMITER = "\n\n— AI —\n"

# Maximum input characters for AI processing
MAX_INPUT_CHARS = 8000



# =============================================================================
# SUMMARIZATION CONFIGURATION
# =============================================================================

# OpenRouter Configuration (used for summarization)
OPENROUTER_API_KEY = _env("OPENROUTER_API_KEY", "")
OR_SITE_URL = _env("OR_SITE_URL", "http://localhost:5555")  # Your site URL for OpenRouter attribution
OR_APP_NAME = _env("OR_APP_NAME", "MioChat Memory Summarizer")  # Your app name shown in OpenRouter dashboard


# Legacy compatibility: older code expects an LLM_MODEL setting.
LLM_MODEL = _env("LLM_MODEL", DEFAULT_CHAT_MODEL)

# Model to use for memory summarization (OpenRouter format)
SUMMARIZATION_MODEL = "meta-llama/llama-3.1-8b-instruct"

# System prompt for summarization
SUMMARIZATION_SYSTEM_PROMPT = "You are a text summarizer. Create a concise summary that preserves all key facts and information. Remove redundancy and verbosity while keeping essential details. Output ONLY the summary, no preamble."

# Summarization temperature (0.0-1.0, lower = more deterministic)
SUMMARIZATION_TEMPERATURE = 0.1

# Maximum tokens for summary output
SUMMARIZATION_MAX_TOKENS = 300

# Minimum character count required to summarize
SUMMARIZATION_MIN_CHARS = 150

# API timeout for summarization requests (seconds)
SUMMARIZATION_TIMEOUT = 60

# Auto-summarization thresholds
SUMMARY_WORD_THRESHOLD = 500  # Stage 1: Auto-summarize files above this word count
META_SUMMARY_THRESHOLD = 500  # Stage 2: Meta-summarize if total context exceeds this
SUMMARY_TARGET_WORDS = 300    # Target summary length


# =============================================================================
# DOCUMENT PARSING CONFIGURATION (Chat Attachments - Phase 2)
# =============================================================================

# Tesseract OCR executable path (required for image text extraction)
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# After installation, update this path to match your installation location
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Maximum file size for text file parsing (MB)
MAX_TEXT_FILE_SIZE_MB = 10

# Maximum characters for document summarization
MAX_SUMMARY_INPUT_CHARS = 50000


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_database_uri():
    """
    Construct and return the database URI.
    
    Returns:
        str: SQLAlchemy database URI
    """
    return f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_api_key_for_provider(provider=None):
    """
    Get the API key for the specified provider.
    
    Args:
        provider: Provider name (defaults to PROVIDER constant)
        
    Returns:
        str: API key for the provider
    """
    if provider is None:
        provider = PROVIDER
    
    provider = provider.lower()
    
    if provider == 'groq':
        return GROQ_API_KEY
    elif provider == 'openrouter':
        return globals().get('OPENROUTER_API_KEY', '')
    elif provider == 'fireworks':
        return globals().get('FIREWORKS_API_KEY', '')
    elif provider == 'together':
        return globals().get('TOGETHER_API_KEY', '')
    else:
        return ''


# =============================================================================
# LEGACY COMPATIBILITY (for gradual migration)
# =============================================================================

class ConfigCompat:
    """
    Compatibility class that mimics the old ConfigLoader interface.
    This allows existing code to work without changes.
    """
    
    def get_db_name(self):
        return DB_NAME
    
    def get_db_user(self):
        return DB_USER
    
    def get_db_password(self):
        return DB_PASSWORD
    
    def get_db_port(self):
        return DB_PORT
    
    def get_db_host(self):
        return DB_HOST
    
    def get_secret_key(self):
        return SECRET_KEY
    
    def get_groq_api_key(self):
        return GROQ_API_KEY
    
    def get_provider(self):
        return PROVIDER
    
    def get_llm_model(self):
        return LLM_MODEL
    
    def get_ai_delimiter(self):
        return AI_DELIMITER
    
    def get_max_input_chars(self):
        return MAX_INPUT_CHARS
    
    def get(self, key, default=None):
        """
        Get configuration value using dot notation (for backward compatibility).
        
        Args:
            key: Configuration key (e.g., 'database.name', 'flask.secret_key')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        mapping = {
            'database.name': DB_NAME,
            'database.user': DB_USER,
            'database.password': DB_PASSWORD,
            'database.port': DB_PORT,
            'database.host': DB_HOST,
            'flask.secret_key': SECRET_KEY,
            'groq_api_key': GROQ_API_KEY,
            'provider': PROVIDER,
            'llm_model': LLM_MODEL,
            'ai.delimiter': AI_DELIMITER,
            'ai.max_input_chars': MAX_INPUT_CHARS,
        }
        return mapping.get(key, default)
    
    def get_database_config(self):
        return {
            'name': DB_NAME,
            'user': DB_USER,
            'password': DB_PASSWORD,
            'port': DB_PORT,
            'host': DB_HOST
        }
    
    def get_flask_config(self):
        return {
            'secret_key': SECRET_KEY
        }
    
    def get_ai_config(self):
        return {
            'delimiter': AI_DELIMITER,
            'max_input_chars': MAX_INPUT_CHARS
        }


def get_config():
    """
    Get configuration instance (for backward compatibility).
    
    Returns:
        ConfigCompat: Configuration object with legacy interface
    """
    return ConfigCompat()
