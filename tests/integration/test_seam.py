"""Cross-seam integration test: the shows service calling the REAL catalogue.

It runs against the whole system started by docker compose, as the browser
sees it: real images, real SQL Server, and shows reaching the catalogue at
CATALOGUE_URL=http://catalogue:8000 on the compose network. No fake: if the
two services disagree on a URL or a JSON shape, this test fails.

Start the stack first, then run it from the repository root:

    docker compose up -d --build
    python -m pytest tests/integration -v

The second test stops the catalogue with "docker compose stop catalogue"
(the partial failure in the brief, section 3) and starts it again at the
end. Each test deletes the show it creates, so the local data is left as
it was.
"""
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Where the test reaches the services from the host: the ports compose
# publishes (the same URLs as ui/config.js).
CATALOGUE = os.environ.get("CATALOGUE_URL", "http://localhost:8001")
SHOWS = os.environ.get("SHOWS_URL", "http://localhost:8002")

# Seconds one request from the test may take before it counts as hung.
REQUEST_TIMEOUT_SECONDS = 30

# Seconds to wait for a service to report healthy after starting.
STARTUP_DEADLINE_SECONDS = 180


def call(method, url, body=None):
    """Send one request and return (status, decoded JSON body or None).

    urlopen raises HTTPError for 4xx and 5xx; their status and body are
    returned the same way, since the test checks those answers too.
    """
    data = None if body is None else json.dumps(body).encode()
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    return status, json.loads(raw) if raw else None


def wait_until_healthy(base_url):
    """Poll GET /health until it answers 200, or fail after the deadline."""
    deadline = time.monotonic() + STARTUP_DEADLINE_SECONDS
    while time.monotonic() < deadline:
        try:
            if call("GET", f"{base_url}/health")[0] == 200:
                return
        except OSError:
            pass  # not listening yet: connection refused or reset
        time.sleep(2)
    pytest.fail(f"{base_url}/health did not answer 200 within {STARTUP_DEADLINE_SECONDS} s")


def compose(*args):
    """Run a docker compose command on this repository's stack."""
    subprocess.run(["docker", "compose", *args], cwd=REPO_ROOT, check=True)


@pytest.fixture
def show_id():
    """A new show in the real shows database, deleted after the test."""
    wait_until_healthy(CATALOGUE)
    wait_until_healthy(SHOWS)
    status, show = call(
        "POST",
        f"{SHOWS}/api/shows",
        {
            "name": "Integration test show",
            "venue": "CI",
            "show_date": "2026-12-31",
            "max_minutes": 90,
        },
    )
    assert status == 201
    yield show["id"]
    call("DELETE", f"{SHOWS}/api/shows/{show['id']}")


def first_active_song():
    """A song the catalogue says can be added to a setlist."""
    status, songs = call("GET", f"{CATALOGUE}/api/songs/active")
    assert status == 200 and songs, "the demo catalogue should have active songs"
    return songs[0]


def test_the_overview_has_the_real_catalogue_song_and_the_checks_ran(show_id):
    song = first_active_song()

    status, overview = call("POST", f"{SHOWS}/api/shows/{show_id}/songs", {"song_id": song["id"]})

    assert status == 201
    assert overview["catalogue_available"] is True
    [item] = overview["items"]
    # Shows got the song from GET /api/songs?ids= across the seam. Its
    # details must be exactly what the catalogue answers there, plus the
    # duration as text that shows adds.
    status, [from_catalogue] = call("GET", f"{CATALOGUE}/api/songs?ids={song['id']}")
    assert status == 200
    assert {k: v for k, v in item["song"].items() if k != "duration"} == from_catalogue
    # The checks ran on the real details: the running time is the song's.
    assert overview["total_seconds"] == from_catalogue["duration_seconds"]
    assert overview["over_limit"] is False
    assert isinstance(overview["problems"], list)
    # The songs to choose from come from GET /api/songs/active.
    assert song["id"] in [choice["id"] for choice in overview["songs"]]


def test_with_the_catalogue_stopped_the_show_is_degraded_not_broken(show_id):
    song = first_active_song()
    assert call("POST", f"{SHOWS}/api/shows/{show_id}/songs", {"song_id": song["id"]})[0] == 201

    compose("stop", "catalogue")
    try:
        started = time.monotonic()
        status, overview = call("GET", f"{SHOWS}/api/shows/{show_id}")
        seconds = time.monotonic() - started

        # Degraded: the setlist from shows' own database, no song details,
        # checks skipped (null, not "no problems"), no songs to choose.
        assert status == 200
        assert overview["catalogue_available"] is False
        [item] = overview["items"]
        assert item["song_id"] == song["id"] and item["song"] is None
        assert overview["total_seconds"] is None and overview["problems"] is None
        assert overview["songs"] == []
        # Not hung: well inside the test's own timeout.
        assert seconds < 15, f"the degraded overview took {seconds:.1f} s"

        # Adding a song cannot be checked, so it is refused and not saved.
        status, answer = call("POST", f"{SHOWS}/api/shows/{show_id}/songs", {"song_id": song["id"]})
        assert status == 503
        assert answer["errors"][0].startswith("Catalogue service unavailable")
        assert len(call("GET", f"{SHOWS}/api/shows/{show_id}")[1]["items"]) == 1

        # Shows' own health does not depend on the catalogue.
        assert call("GET", f"{SHOWS}/health")[0] == 200
    finally:
        compose("start", "catalogue")
        wait_until_healthy(CATALOGUE)
