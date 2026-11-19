"""Tests for db.py that need no database: reading DATABASE_URL and the
connection retries (pymssql.connect is replaced by a fake)."""
import pymssql
import pytest

import config
import db


def test_parse_database_url_gives_the_connect_arguments():
    settings = db.parse_database_url("mssql://app:p%40ss!@sqlserver:1433/catalogue")
    assert settings == {
        "server": "sqlserver",
        "port": 1433,
        "user": "app",
        "password": "p@ss!",
        "database": "catalogue",
    }


def test_parse_database_url_uses_port_1433_by_default():
    assert db.parse_database_url("mssql://app:pw@localhost/catalogue")["port"] == 1433


@pytest.mark.parametrize(
    "url",
    ["", "postgres://app:secret@host/db", "mssql://app:secret@host", "mssql://app:secret@/db"],
)
def test_a_bad_database_url_is_refused_without_showing_the_password(url):
    with pytest.raises(ValueError) as error:
        db.parse_database_url(url)
    assert "secret" not in str(error.value)


def test_retry_delay_doubles_up_to_15_seconds():
    assert [db.retry_delay(n) for n in range(1, 8)] == [1, 2, 4, 8, 15, 15, 15]


@pytest.fixture
def fake_connect(monkeypatch):
    """Replace pymssql.connect and time.sleep. Returns (state, sleeps).

    A test sets state["failures"] to how many attempts should fail with
    error 40613 (Azure: database is resuming from pause). sleeps collects
    every wait, so no test really sleeps.
    """
    sleeps = []
    state = {"failures": 0, "calls": 0}

    def connect(**settings):
        state["calls"] += 1
        state["login_timeout"] = settings["login_timeout"]
        if state["calls"] <= state["failures"]:
            raise pymssql.OperationalError(40613, b"Database is not currently available.")
        return "connection"

    monkeypatch.setattr(config, "DATABASE_URL", "mssql://app:pw@host:1433/catalogue")
    monkeypatch.setattr(db.pymssql, "connect", connect)
    monkeypatch.setattr(db.time, "sleep", sleeps.append)
    return state, sleeps


def test_get_connection_retries_with_backoff_until_it_connects(fake_connect, capsys):
    state, sleeps = fake_connect
    state["failures"] = 2
    assert db.get_connection(attempts=5) == "connection"
    assert sleeps == [1, 2]
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "database not reachable (error 40613, attempt 1/5), retrying in 1s"


def test_get_connection_raises_after_the_last_attempt(fake_connect):
    state, sleeps = fake_connect
    state["failures"] = 99
    with pytest.raises(pymssql.OperationalError):
        db.get_connection(attempts=3)
    assert sleeps == [1, 2]
    assert state["calls"] == 3


def test_get_connection_uses_the_login_timeout_from_config(fake_connect, monkeypatch):
    state, _ = fake_connect
    monkeypatch.setattr(config, "DB_LOGIN_TIMEOUT_SECONDS", 10)
    db.get_connection(attempts=1)
    assert state["login_timeout"] == 10


def test_get_connection_can_be_given_a_shorter_login_timeout(fake_connect):
    state, _ = fake_connect
    db.get_connection(attempts=1, login_timeout=2)
    assert state["login_timeout"] == 2
