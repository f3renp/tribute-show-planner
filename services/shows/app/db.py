"""Connections to this service's SQL Server database, and small helpers to
run SQL. Only this file talks to pymssql.

SQL uses pymssql's markers: %s for a value from a tuple, %(name)s for a
value from a dict. pymssql fills them in safely (no SQL injection).
"""
import sys
import time
from urllib.parse import unquote, urlsplit

import pymssql

import config

# Wait before the next attempt: 1 s, then twice as long each time, at most 15 s.
FIRST_RETRY_DELAY_SECONDS = 1
MAX_RETRY_DELAY_SECONDS = 15


def log(message):
    """Print one line to stdout, where Docker and Azure collect the logs."""
    sys.stdout.write(message + "\n")
    sys.stdout.flush()


def parse_database_url(url):
    """Split mssql://user:password@host:port/database into connect() arguments.

    The error message never repeats the URL, because it holds the password.
    User and password may be URL-encoded (%40 for @).
    """
    parts = urlsplit(url)
    database = parts.path.lstrip("/")
    if parts.scheme != "mssql" or not parts.hostname or not database:
        raise ValueError(
            "DATABASE_URL must be set and look like "
            "mssql://user:password@host:1433/database"
        )
    return {
        "server": parts.hostname,
        "port": parts.port or 1433,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": database,
    }


def retry_delay(attempt):
    """Seconds to wait after failed attempt number `attempt` (1, 2, 3, ...)."""
    return min(FIRST_RETRY_DELAY_SECONDS * 2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS)


def error_code(error):
    """The SQL Server or driver error number, e.g. 40613 (database paused)."""
    return error.args[0] if error.args else "unknown"


def get_connection(attempts=None, login_timeout=None):
    """Open a connection, retrying with backoff while the server refuses it.

    SQL Server may still be starting (docker compose) or the Azure database
    may be resuming from auto-pause (error 40613). Both refuse connections
    for a while and then work. After the last attempt the error is raised.

    attempts and login_timeout default to the settings in config.py;
    /health passes 1 and a short timeout so it answers quickly.
    """
    if attempts is None:
        attempts = config.DB_CONNECT_ATTEMPTS
    if login_timeout is None:
        login_timeout = config.DB_LOGIN_TIMEOUT_SECONDS
    settings = parse_database_url(config.DATABASE_URL)
    for attempt in range(1, attempts + 1):
        try:
            return pymssql.connect(**settings, login_timeout=login_timeout)
        except pymssql.OperationalError as error:
            if attempt == attempts:
                raise
            delay = retry_delay(attempt)
            log(
                f"database not reachable (error {error_code(error)}, attempt "
                f"{attempt}/{attempts}), retrying in {delay}s"
            )
            time.sleep(delay)


def fetch_all(sql, params=None):
    """Run a SELECT and return every row as a dict."""
    connection = get_connection()
    try:
        cursor = connection.cursor(as_dict=True)
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        connection.close()


def fetch_one(sql, params=None):
    """Run a SELECT and return the first row as a dict, or None."""
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Run an UPDATE, DELETE or DDL statement and save it."""
    connection = get_connection()
    try:
        connection.cursor().execute(sql, params)
        connection.commit()
    finally:
        connection.close()


def insert(sql, params=None):
    """Run an INSERT that ends in OUTPUT INSERTED.id, save it, return the id."""
    connection = get_connection()
    try:
        cursor = connection.cursor(as_dict=True)
        cursor.execute(sql, params)
        new_id = cursor.fetchone()["id"]
        connection.commit()
    finally:
        connection.close()
    return new_id
