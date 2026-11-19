"""Tests for shows/catalogue_client.py.

urlopen is replaced by a fake that records the URL it was asked for and
answers with a fixed JSON body, so no test needs the catalogue running.
"""
import io
import json
from urllib.error import HTTPError, URLError

import pytest

import config
from shows import catalogue_client


@pytest.fixture
def fake_catalogue_api(monkeypatch):
    """Make urlopen answer with calls["body"] and record each URL in calls["urls"]."""
    calls = {"urls": [], "timeouts": [], "body": []}

    def fake_urlopen(url, timeout):
        calls["urls"].append(url)
        calls["timeouts"].append(timeout)
        return io.BytesIO(json.dumps(calls["body"]).encode())

    monkeypatch.setattr(catalogue_client, "urlopen", fake_urlopen)
    monkeypatch.setattr(config, "CATALOGUE_URL", "http://catalogue:8000/")
    return calls


def test_songs_by_ids_asks_once_and_keys_the_result_by_id(fake_catalogue_api):
    fake_catalogue_api["body"] = [{"id": 7, "title": "Bad"}, {"id": 3, "title": "Ben"}]
    songs = catalogue_client.get_songs_by_ids([7, 3, 7])
    assert songs == {7: {"id": 7, "title": "Bad"}, 3: {"id": 3, "title": "Ben"}}
    assert fake_catalogue_api["urls"] == ["http://catalogue:8000/api/songs?ids=3%2C7"]


def test_songs_by_ids_with_no_ids_makes_no_request(fake_catalogue_api):
    assert catalogue_client.get_songs_by_ids([]) == {}
    assert fake_catalogue_api["urls"] == []


def test_active_songs_come_from_the_active_endpoint(fake_catalogue_api):
    fake_catalogue_api["body"] = [{"id": 1, "title": "Bad", "active": 1}]
    assert catalogue_client.list_active_songs() == [{"id": 1, "title": "Bad", "active": 1}]
    assert fake_catalogue_api["urls"] == ["http://catalogue:8000/api/songs/active"]


def test_every_call_uses_the_timeout_from_config(fake_catalogue_api, monkeypatch):
    monkeypatch.setattr(config, "CATALOGUE_TIMEOUT", 1.5)
    catalogue_client.list_active_songs()
    assert fake_catalogue_api["timeouts"] == [1.5]


@pytest.mark.parametrize(
    "error",
    [
        URLError("connection refused"),
        TimeoutError("timed out"),
        HTTPError("http://catalogue:8000/api/songs/active", 503, "Unavailable", {}, None),
        ConnectionResetError("connection reset"),
    ],
)
def test_failed_calls_raise_catalogue_unavailable(monkeypatch, error):
    def failing_urlopen(url, timeout):
        raise error

    monkeypatch.setattr(catalogue_client, "urlopen", failing_urlopen)
    with pytest.raises(catalogue_client.CatalogueUnavailable):
        catalogue_client.list_active_songs()


def test_a_body_that_is_not_json_raises_catalogue_unavailable(monkeypatch):
    def html_urlopen(url, timeout):
        return io.BytesIO(b"<html>Bad gateway</html>")

    monkeypatch.setattr(catalogue_client, "urlopen", html_urlopen)
    with pytest.raises(catalogue_client.CatalogueUnavailable):
        catalogue_client.get_songs_by_ids([1])
