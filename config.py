"""
Load environment variables from config.env (preferred) or .env into os.environ
so the bot's conf() helper can pick them up.

Do NOT hardcode credentials here. Edit config.env instead.
"""
import os
from pathlib import Path


def _load_env_file(*candidates):
    """Parse a simple KEY=VALUE env file, ignoring comments and blank lines.
    Opens in binary mode so CRLF line endings are handled correctly on all
    platforms (Windows, WSL, Linux).
    """
    for path in candidates:
        p = Path(path)
        if p.is_file():
            with p.open("rb") as f:
                for raw in f:
                    # Decode and strip all whitespace including \r and \n
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    # Strip surrounding quotes
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            return  # stop at first file found


# Try config.env first, then .env
_load_env_file("config.env", ".env")
