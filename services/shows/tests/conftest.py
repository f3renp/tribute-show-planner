"""Shared test setup. pytest loads this file before the tests in tests/.

The database tests use their own database, shows_test, on the SQL Server
from docker compose. Start it first, from the repository root:

    docker compose up -d sqlserver db-init

db/init.sql creates shows_test next to shows, so the tests never touch the
real local data. No test calls the real catalogue: the catalogue fixtures
below replace it.

Speed: opening a connection costs ~100 ms, a query on an open one ~4 ms.
So the schema is built once per test run, and between tests the tables
are emptied on a single connection instead of being dropped and migrated
again.
"""
import os

import pytest

import config
import db
import migrate
from shows import catalogue_client

# Default: the LOCAL-ONLY password from docker-compose.yml, on 127.0.0.1.
# CI sets TEST_DATABASE_URL with the random password it generates.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mssql://shows_app:LocalOnly_Shows_2026!@127.0.0.1:1433/shows_test",
)

# Every table the migrations (and test_migrate.py) can create, children
# before parents: setlist_items references shows, so it must be dropped first.
TABLES = ["setlist_items", "shows", "schema_migrations", "rollback_check"]

# The tables that hold data, children before parents (same reason).
# schema_migrations is kept: the schema stays, so its record must stay too.
DATA_TABLES = ["setlist_items", "shows"]

# Tables whose IDENTITY has handed out at least one id. Only these are
# reseeded: on a table that never had a row, RESEED 0 would make the next
# id 0 instead of 1.
USED_IDENTITY_TABLES = """
SELECT OBJECT_NAME(object_id) AS name
FROM sys.identity_columns
WHERE last_value IS NOT NULL
"""

# False until the first database test has built the schema in this run.
# fresh_database sets it back to False, because its tests may change the
# schema (a temporary 002 migration).
schema_is_current = False


def refuse_unless_test_database():
    """Raise unless DATABASE_URL points at a database named ..._test."""
    database_name = db.parse_database_url(config.DATABASE_URL)["database"]
    if not database_name.endswith("_test"):
        raise RuntimeError(f"Refusing to clean the database {database_name!r}")


def drop_all_tables():
    """Empty the test database completely. Refuses any non-test database."""
    refuse_unless_test_database()
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")


def rebuild_schema():
    """Drop every table and run the migrations from 001."""
    drop_all_tables()
    migrate.apply_migrations()


def empty_tables():
    """Delete every row and make the ids start at 1 again, on one
    connection. Refuses any non-test database."""
    refuse_unless_test_database()
    connection = db.get_connection()
    try:
        cursor = connection.cursor()
        for table in DATA_TABLES:
            cursor.execute(f"DELETE FROM {table}")
        cursor.execute(USED_IDENTITY_TABLES)
        used_tables = [row[0] for row in cursor.fetchall()]
        for table in DATA_TABLES:
            if table in used_tables:
                # The next id is RESEED value + 1, so 1.
                cursor.execute(f"DBCC CHECKIDENT ('{table}', RESEED, 0)")
        connection.commit()
    finally:
        connection.close()


def use_test_database(monkeypatch):
    """Point the app at shows_test for one test. monkeypatch puts the
    settings back afterwards."""
    monkeypatch.setattr(config, "DATABASE_URL", TEST_DATABASE_URL)
    # Fail at once, not after a minute of retries, if SQL Server is not up.
    monkeypatch.setattr(config, "DB_CONNECT_ATTEMPTS", 1)


@pytest.fixture
def database(monkeypatch):
    """Give one test an empty shows_test with the current schema.

    The first test of the run builds the schema; every later one only
    empties the tables. Either way the test starts with no rows and ids
    that start at 1.
    """
    global schema_is_current
    use_test_database(monkeypatch)
    if schema_is_current:
        empty_tables()
    else:
        rebuild_schema()
        schema_is_current = True


@pytest.fixture
def fresh_database(monkeypatch):
    """Give one test a shows_test rebuilt from nothing: every table dropped
    and the migrations run again from 001. For the migration tests, which
    need a truly new database and may leave the schema changed."""
    global schema_is_current
    use_test_database(monkeypatch)
    rebuild_schema()
    yield
    # The test may have applied a temporary migration: rebuild next time.
    schema_is_current = False


@pytest.fixture
def catalogue(monkeypatch):
    """A fake catalogue service: a dict {song_id: song} the test fills in.

    The two catalogue_client functions are replaced so they read this dict
    instead of calling the catalogue over HTTP. They return the same shapes
    as the real API, so the show builder code under test does not know the
    difference.
    """
    songs = {}

    def get_songs_by_ids(song_ids):
        return {song_id: dict(songs[song_id]) for song_id in song_ids if song_id in songs}

    def list_active_songs():
        return [dict(song) for song in songs.values() if song["active"]]

    monkeypatch.setattr(catalogue_client, "get_songs_by_ids", get_songs_by_ids)
    monkeypatch.setattr(catalogue_client, "list_active_songs", list_active_songs)
    return songs


@pytest.fixture
def catalogue_down(catalogue, monkeypatch):
    """A fake catalogue that is stopped: both catalogue_client functions
    raise CatalogueUnavailable, as the real ones do when the call fails.

    It depends on catalogue so that it is always set up after it, and wins,
    even in a test whose client fixture also asks for catalogue."""

    def unavailable(*args):
        raise catalogue_client.CatalogueUnavailable("catalogue is down (test)")

    monkeypatch.setattr(catalogue_client, "get_songs_by_ids", unavailable)
    monkeypatch.setattr(catalogue_client, "list_active_songs", unavailable)
