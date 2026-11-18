"""Settings for the catalogue service, read from environment variables with
defaults.

Nothing else in the service reads os.environ, so this file lists every
setting that can be changed without editing code.
"""
import os

# Port the web server listens on.
PORT = int(os.environ.get("PORT", "8000"))

# Connection string of the catalogue database, for example
# mssql://catalogue_app:PASSWORD@sqlserver:1433/catalogue
# It contains a password, so it has no default and must be set.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# How many times to try to connect before giving up. With the waits in
# db.retry_delay (1, 2, 4, 8, 15, 15, 15 s), 8 attempts wait about a minute:
# long enough for SQL Server to start, or for Azure SQL to resume from pause.
DB_CONNECT_ATTEMPTS = int(os.environ.get("DB_CONNECT_ATTEMPTS", "8"))

# Seconds one connection attempt may take before it counts as failed.
DB_LOGIN_TIMEOUT_SECONDS = int(os.environ.get("DB_LOGIN_TIMEOUT_SECONDS", "10"))

# Folder with the numbered migration files: services/catalogue/migrations,
# next to app/ (the Dockerfile keeps the same layout).
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations"
)

# Address of the shows service as the browser sees it, for the "Shows" link
# in the page header. This is a browser link, not a service-to-service call.
SHOWS_PUBLIC_URL = os.environ.get("SHOWS_PUBLIC_URL", "http://localhost:8002")
