"""GET /health: is this service able to read and write its own database?

200 {"status": "ok", "db": "ok", "version": GIT_SHA} when it can,
503 {"status": "error", "db": "error", "version": GIT_SHA} when it cannot.

It checks only this service's own state: it never calls the other service.
The same file is in both services (services share no code).
"""
import config
import db

# The read and the write use schema_migrations: every migrated database of
# either service has it, and it has no foreign keys. The INSERT is rolled
# back, so the test row is never saved and nothing is left behind.
READ_SQL = "SELECT COUNT(*) FROM schema_migrations"
WRITE_SQL = "INSERT INTO schema_migrations (version) VALUES (N'health_check')"


def database_is_ok():
    """True if a connection, a read and a write all work, without saving
    anything. One attempt with a short timeout: a health check must answer
    quickly, not wait a minute of retries."""
    try:
        connection = db.get_connection(
            attempts=1, login_timeout=config.HEALTH_DB_TIMEOUT_SECONDS
        )
    # Any failure (server down, wrong password, bad DATABASE_URL) means
    # unhealthy, never a 500. Only the error's type is logged: the message
    # of a bad DATABASE_URL must not end up in the logs.
    except Exception as error:
        db.log(f"health: cannot connect to the database ({type(error).__name__})")
        return False
    try:
        cursor = connection.cursor()
        cursor.execute(READ_SQL)
        cursor.fetchone()
        cursor.execute(WRITE_SQL)
        # Undo the test row: the write worked, but it is never saved.
        connection.rollback()
        return True
    except Exception as error:
        db.log(f"health: database read or write failed ({type(error).__name__})")
        return False
    finally:
        # Closing a connection that still has an open transaction makes
        # SQL Server roll it back too, so a failed write is not saved either.
        connection.close()


def health_answer():
    """The /health body and status code."""
    if database_is_ok():
        return {"status": "ok", "db": "ok", "version": config.GIT_SHA}, 200
    return {"status": "error", "db": "error", "version": config.GIT_SHA}, 503


def add_health_route(app):
    """Register GET /health on the Flask app."""

    @app.route("/health")
    def health():
        return health_answer()
