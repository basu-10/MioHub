"""Environment bootstrapper for scripts (migrations, utilities).

Usage in scripts (place before importing config):
    import env_loader
    env_loader.load_env_from_wsgi()
    import config

Behavior:
- If required env vars are already set, it does nothing.
- Otherwise, it tries to import a WSGI file to populate os.environ.
- Windows: uses the repo-local wsgi_local.py.
- Linux: prefers the hosted WSGI at /var/www/basu001_pythonanywhere_com_wsgi.py,
  and falls back to wsgi_prod.py in the repo if present.

This avoids committing secrets while letting scripts reuse the same env as the
app servers. If none of the candidates exist, it raises a clear error so users
can set env vars manually.
"""

import importlib.util
import os
import platform
from pathlib import Path


REQUIRED_VARS = [
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "SECRET_KEY",
    "GROQ_API_KEY",
]


def _has_required_env() -> bool:
    return all(os.getenv(k) for k in REQUIRED_VARS)


def _try_load_module(module_path: Path) -> bool:
    if not module_path.exists():
        return False
    spec = importlib.util.spec_from_file_location("mio_wsgi_env", module_path)
    if not spec or not spec.loader:
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return True


def load_env_from_wsgi() -> None:
    """Populate os.environ using an appropriate WSGI file for this OS.

    Raises:
        RuntimeError: if required env vars remain unset after attempts.
    """
    if _has_required_env():
        return

    system = platform.system().lower()
    repo_root = Path(__file__).resolve().parent

    candidates = []
    if system == "windows":
        print("Windows detected: loading wsgi_local.py for env vars")
        candidates.append(repo_root / "wsgi_local.py")
    else:
        print("Linux detected: loading hosted WSGI file for env vars")
        candidates.append(Path("/var/www/basu001_pythonanywhere_com_wsgi.py"))

    for candidate in candidates:
        if _try_load_module(candidate) and _has_required_env():
            return

    missing = [k for k in REQUIRED_VARS if not os.getenv(k)]
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing) +
        ". Set them or ensure a WSGI file with these values is present."
    )
