"""Shared test setup. pytest loads this file before the tests in tests/.

The database tests use their own database, shows_test, on the SQL Server
from docker compose. Start it first, from the repository root:

    docker compose up -d sqlserver db-init

db/init.sql creates shows_test next to shows, so the tests never touch the
real local data. No test calls the real catalogue: the catalogue fixtures
below replace it.
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


def drop_all_tables():
    """Empty the test database completely. Refuses any non-test database."""
    database_name = db.parse_database_url(config.DATABASE_URL)["database"]
    if not database_name.endswith("_test"):
        raise RuntimeError(f"Refusing to drop tables in {database_name!r}")
    for table in TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def database(monkeypatch):
    """Give one test an empty shows_test with the current schema.

    Every table is dropped and the migrations run again from 001, so each
    test starts from nothing (ids start at 1 again) and the migrations are
    exercised on every run. monkeypatch puts the settings back afterwards.
    """
    monkeypatch.setattr(config, "DATABASE_URL", TEST_DATABASE_URL)
    # Fail at once, not after a minute of retries, if SQL Server is not up.
    monkeypatch.setattr(config, "DB_CONNECT_ATTEMPTS", 1)
    drop_all_tables()
    migrate.apply_migrations()


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
def catalogue_down(monkeypatch):
    """A fake catalogue that is stopped: both catalogue_client functions
    raise CatalogueUnavailable, as the real ones do when the call fails."""

    def unavailable(*args):
        raise catalogue_client.CatalogueUnavailable("catalogue is down (test)")

    monkeypatch.setattr(catalogue_client, "get_songs_by_ids", unavailable)
    monkeypatch.setattr(catalogue_client, "list_active_songs", unavailable)
