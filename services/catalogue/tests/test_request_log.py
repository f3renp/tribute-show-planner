"""Tests for request_log.py: one line per request on stdout.

capsys is a pytest fixture that captures what the code prints, so the test
can read it back. The same file is in both services.
"""
import re

import pytest

import main

# e.g. "GET /health 200 3.2ms"
LOG_LINE = re.compile(r"^(GET|POST) (\S+) (\d{3}) \d+\.\dms$")

# demo_catalogue: create_app() finds a full catalogue and skips the slow seed.
pytestmark = pytest.mark.usefixtures("demo_catalogue")


def printed_lines(capsys):
    """The lines printed since the last call, without empty ones."""
    return [line for line in capsys.readouterr().out.splitlines() if line]


def test_each_request_prints_one_line_with_method_path_status_and_duration(capsys):
    client = main.create_app().test_client()
    printed_lines(capsys)  # forget anything printed while starting the app
    client.get("/health")
    client.get("/no-such-page")
    lines = printed_lines(capsys)
    assert len(lines) == 2
    first, second = (LOG_LINE.match(line) for line in lines)
    assert first.group(1, 2, 3) == ("GET", "/health", "200")
    assert second.group(1, 2, 3) == ("GET", "/no-such-page", "404")


def test_the_query_string_is_not_logged(capsys):
    client = main.create_app().test_client()
    printed_lines(capsys)
    client.get("/health?secret=1")
    assert LOG_LINE.match(printed_lines(capsys)[0]).group(2) == "/health"
