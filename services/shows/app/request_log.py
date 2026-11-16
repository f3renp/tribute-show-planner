"""One log line per request on stdout: method, path, status and duration.

Example: GET /health 200 3.2ms

The same file is in both services. Docker (and Azure Container Apps) collect
whatever a container writes to stdout, so printing is all that is needed.
"""
import sys
import time

from flask import g, request


def log_requests(app):
    """Make the Flask app print one line for every request it answers."""

    @app.before_request
    def remember_start_time():
        # g holds values for the current request only.
        g.request_started = time.perf_counter()

    @app.after_request
    def print_request_line(response):
        duration_ms = (time.perf_counter() - g.request_started) * 1000
        line = f"{request.method} {request.path} {response.status_code} {duration_ms:.1f}ms"
        # One write call with the newline included. print() writes the text
        # and the "\n" separately, so with waitress's threads two lines
        # could end up glued together.
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        return response
