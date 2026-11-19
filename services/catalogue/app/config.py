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

# Seconds /health waits for the database to accept a login (one attempt, no
# retries), so a health check answers within the Docker HEALTHCHECK's time
# limit. The host name lookup before the login is not included.
HEALTH_DB_TIMEOUT_SECONDS = int(os.environ.get("HEALTH_DB_TIMEOUT_SECONDS", "2"))

# Commit the running code was built from, shown by /health. The Dockerfile
# sets it from the GIT_SHA build argument, which CI fills with the commit
# SHA; "dev" means a local build or a run outside Docker.
GIT_SHA = os.environ.get("GIT_SHA", "dev")

# Folder with the numbered migration files: services/catalogue/migrations,
# next to app/ (the Dockerfile keeps the same layout).
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations"
)

# Origins (scheme://host:port, no trailing slash) whose pages may call this
# API from the browser, separated by commas. The default is the UI served
# by nginx in docker compose. On Azure the pipeline sets the Storage static
# website's origin. Empty means no browser page may call it (cors.py).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:8080").split(",")
    if origin.strip()
]
