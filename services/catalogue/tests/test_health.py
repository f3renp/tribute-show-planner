"""Tests for health.py: GET /health is 200 only when the service can read
and write its own database, 503 otherwise, and it answers quickly."""
import pymssql
import pytest

import config
import db
import health
import main


@pytest.fixture
def client(demo_catalogue, monkeypatch):
    monkeypatch.setattr(config, "GIT_SHA", "abc1234")
    return main.create_app().test_client()


def refuse_connections(monkeypatch):
    """Make every connection attempt fail, as when SQL Server is stopped.
    Returns the list of login_timeout values the attempts were made with."""
    attempts = []

    def refuse(**settings):
        attempts.append(settings["login_timeout"])
        raise pymssql.OperationalError(20009, b"Unable to connect: server is unavailable")

    monkeypatch.setattr(db.pymssql, "connect", refuse)
    return attempts


def test_health_is_200_with_db_ok_and_the_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "abc1234"}


def test_the_test_write_leaves_nothing_behind(client):
    # If the first check had saved its row, the second would fail on the
    # primary key of schema_migrations.
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    rows = db.fetch_all("SELECT version FROM schema_migrations")
    assert [row["version"] for row in rows] == ["001_init"]


def test_health_is_503_when_the_database_cannot_be_reached(client, monkeypatch, capsys):
    refuse_connections(monkeypatch)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "db": "error", "version": "abc1234"}
    assert "health: cannot connect to the database (OperationalError)" in capsys.readouterr().out


def test_health_is_503_when_it_can_read_but_not_write(client, monkeypatch, capsys):
    # A real write that fails on the real database: the table does not exist.
    monkeypatch.setattr(health, "WRITE_SQL", "INSERT INTO no_such_table (id) VALUES (1)")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.get_json()["db"] == "error"
    assert "health: database read or write failed" in capsys.readouterr().out


def test_health_tries_once_with_the_short_timeout_and_never_waits(client, monkeypatch):
    monkeypatch.setattr(config, "DB_CONNECT_ATTEMPTS", 8)
    attempts = refuse_connections(monkeypatch)
    waits = []
    monkeypatch.setattr(db.time, "sleep", waits.append)
    assert client.get("/health").status_code == 503
    assert attempts == [config.HEALTH_DB_TIMEOUT_SECONDS]
    assert waits == []


def test_a_bad_database_url_is_503_and_its_password_is_not_logged(client, monkeypatch, capsys):
    monkeypatch.setattr(config, "DATABASE_URL", "postgres://app:secret@host/db")
    assert client.get("/health").status_code == 503
    assert "secret" not in capsys.readouterr().out
