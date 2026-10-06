"""Settings for the app, read from environment variables with defaults.

Nothing else in the app reads os.environ, so this file lists every
setting that can be changed without editing code.
"""
import os

# Port the web server listens on.
PORT = int(os.environ.get("PORT", "8000"))

# Folder that holds the SQLite database file.
DATA_DIR = os.environ.get("DATA_DIR", "data")

# Full path of the database file inside DATA_DIR.
DATABASE_PATH = os.path.join(DATA_DIR, "tribute.db")
