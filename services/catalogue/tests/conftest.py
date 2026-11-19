"""Shared test setup. pytest loads this file before the tests in tests/.

The database tests use their own database, catalogue_test, on the SQL
Server from docker compose. Start it first, from the repository root:

    docker compose up -d sqlserver db-init

db/init.sql creates catalogue_test next to catalogue, so the tests never
touch the real local data.

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
import seed
from catalogue import service

# Default: the LOCAL-ONLY password from docker-compose.yml, on 127.0.0.1.
# CI sets TEST_DATABASE_URL with the random password it generates.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mssql://catalogue_app:LocalOnly_Catalogue_2026!@127.0.0.1:1433/catalogue_test",
)

# Every table the migrations (and test_migrate.py) can create, children
# before parents: songs references outfits, so it must be dropped first.
TABLES = ["songs", "outfits", "schema_migrations", "rollback_check"]

# The tables that hold data, children before parents (same reason).
# schema_migrations is kept: the schema stays, so its record must stay too.
DATA_TABLES = ["songs", "outfits"]

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
    """Point the app at catalogue_test for one test. monkeypatch puts the
    settings back afterwards."""
    monkeypatch.setattr(config, "DATABASE_URL", TEST_DATABASE_URL)
    # Fail at once, not after a minute of retries, if SQL Server is not up.
    monkeypatch.setattr(config, "DB_CONNECT_ATTEMPTS", 1)


@pytest.fixture
def database(monkeypatch):
    """Give one test an empty catalogue_test with the current schema.

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
    """Give one test a catalogue_test rebuilt from nothing: every table
    dropped and the migrations run again from 001. For the migration tests,
    which need a truly new database and may leave the schema changed."""
    global schema_is_current
    use_test_database(monkeypatch)
    rebuild_schema()
    yield
    # The test may have applied a temporary migration: rebuild next time.
    schema_is_current = False


def insert_demo_catalogue():
    """Insert the demo outfits and songs from seed.py on one connection.

    seed.seed_demo_catalogue() saves them through catalogue.service, which
    opens ~100 connections (~5 s); this takes a fraction of a second. It
    gives the same rows with the same ids (test_seed.py checks that), so a
    test can still find "Billie Jean" and create_app() skips its own seed.
    """
    connection = db.get_connection()
    try:
        cursor = connection.cursor()
        for name, change_seconds in seed.DEMO_OUTFITS:
            cursor.execute(
                "INSERT INTO outfits (name, change_seconds) VALUES (%s, %s)",
                (name, change_seconds),
            )
        for title, album, year, duration, energy, kind, outfit_name in seed.DEMO_SONGS:
            cursor.execute(
                "INSERT INTO songs (title, album, year, duration_seconds, energy, kind, outfit_id) "
                "SELECT %s, %s, %s, %s, %s, %s, id FROM outfits WHERE name = %s",
                (title, album, year, service.parse_duration(duration), energy, kind, outfit_name),
            )
        for title, album in seed.RETIRED_DEMO_SONGS:
            cursor.execute(
                "UPDATE songs SET active = 0 WHERE title = %s AND album = %s",
                (title, album),
            )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def demo_catalogue(database):
    """An empty catalogue_test (the database fixture) with the demo
    catalogue in it."""
    insert_demo_catalogue()
