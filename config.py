"""
Configuration module for the Flask application.
Store all configuration values as Python constants.

To customize for your environment:
1. Edit the values below directly
2. For production, consider using environment variables with os.getenv()
"""

import os


def _first_nonempty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


try:
    import config_local as _config_local  # type: ignore
except Exception:
    _config_local = None


def _get_local(name: str) -> str:
    if _config_local is None:
        return ""
    return str(getattr(_config_local, name, "") or "")


def _get_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# For PythonAnywhere deployment, use these values:
# DB_NAME = "basu001$default"
# DB_USER = "basu001"
# DB_PASSWORD = "your_pythonanywhere_db_password"
# DB_PORT = "3306"
# DB_HOST = "basu001.mysql.pythonanywhere-services.com"

# For local development:
DB_NAME = "wordpadplusplus"
DB_USER = "root"
DB_PASSWORD = _first_nonempty(
    _get_env("MIOHUB_DB_PASSWORD", "DB_PASSWORD"),
    _get_local("DB_PASSWORD"),
    "root",
)
DB_PORT = "3306"
DB_HOST = "localhost"


# =============================================================================
# FLASK CONFIGURATION
# =============================================================================

# Secret key for Flask sessions (must be consistent for persistent login)
# Generate a new one with: python -c "import secrets; print(secrets.token_hex(24))"
SECRET_KEY = _first_nonempty(
    _get_env("MIOHUB_SECRET_KEY", "SECRET_KEY"),
    _get_local("SECRET_KEY"),
    "",
)


# =============================================================================
# MAIN CHAT - LLM PROVIDER CONFIGURATION (Groq)
# =============================================================================

# Provider for main chat (currently using Groq)
PROVIDER = "groq"

# Groq API Configuration
GROQ_API_KEY = _first_nonempty(
    _get_env("GROQ_API_KEY", "MIOHUB_GROQ_API_KEY"),
    _get_local("GROQ_API_KEY"),
    "",
)

# Default model for main chat (Groq)
DEFAULT_CHAT_MODEL = "llama-3.3-70b-versatile"

# Backward-compat alias used by some older code paths.
LLM_MODEL = DEFAULT_CHAT_MODEL

# Available models for main chat (Groq models)
AVAILABLE_CHAT_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-guard-4-12b",
    "llama3-8b-8192",
    "llama3-70b-8192",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it"
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
OPENROUTER_API_KEY = _first_nonempty(
    _get_env("OPENROUTER_API_KEY", "MIOHUB_OPENROUTER_API_KEY"),
    _get_local("OPENROUTER_API_KEY"),
    "",
)
OR_SITE_URL = "http://localhost:5555"  # Your site URL for OpenRouter attribution
OR_APP_NAME = "MioChat Memory Summarizer"  # Your app name shown in OpenRouter dashboard

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
