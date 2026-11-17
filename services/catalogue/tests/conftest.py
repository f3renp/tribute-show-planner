"""Shared test setup. pytest loads this file before the tests in tests/.

The database tests use their own database, catalogue_test, on the SQL
Server from docker compose. Start it first, from the repository root:

    docker compose up -d sqlserver db-init

db/init.sql creates catalogue_test next to catalogue, so the tests never
touch the real local data.
"""
import os

import pytest

import config
import db
import migrate

# Default: the LOCAL-ONLY password from docker-compose.yml, on 127.0.0.1.
# CI sets TEST_DATABASE_URL with the random password it generates.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mssql://catalogue_app:LocalOnly_Catalogue_2026!@127.0.0.1:1433/catalogue_test",
)

# Every table the migrations (and test_migrate.py) can create, children
# before parents: songs references outfits, so it must be dropped first.
TABLES = ["songs", "outfits", "schema_migrations", "rollback_check"]


def drop_all_tables():
    """Empty the test database completely. Refuses any non-test database."""
    database_name = db.parse_database_url(config.DATABASE_URL)["database"]
    if not database_name.endswith("_test"):
        raise RuntimeError(f"Refusing to drop tables in {database_name!r}")
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def database(monkeypatch):
    """Give one test an empty catalogue_test with the current schema.

    Every table is dropped and the migrations run again from 001, so each
    test starts from nothing (ids start at 1 again) and the migrations are
    exercised on every run. monkeypatch puts the settings back afterwards.
    """
    monkeypatch.setattr(config, "DATABASE_URL", TEST_DATABASE_URL)
    # Fail at once, not after a minute of retries, if SQL Server is not up.
    monkeypatch.setattr(config, "DB_CONNECT_ATTEMPTS", 1)
    drop_all_tables()
    migrate.apply_migrations()
