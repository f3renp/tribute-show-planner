"""CORS: lets the static UI, served from another origin, call this API from
the browser.

The browser blocks a page from reading the answer of a request to another
origin (scheme + host + port) unless the answer says that origin is
allowed. For a POST or PUT with a JSON body, the browser first sends a
"preflight": an OPTIONS request asking which methods and headers are
allowed. Flask already answers OPTIONS on every route (200, with an Allow
header); the hook below adds the CORS headers to that answer and to the
real request that follows.

Only the origins in config.CORS_ORIGINS get the headers. Any other origin
gets none, so the browser refuses to give the page the answer.
CORS is a browser rule, not access control: curl or another service can
still call the API (shows does, server to server).

Configured here in the code, never on the Container Apps ingress.
"""
from flask import request

import config

# Everything the UI sends: GET to read, POST and PUT with a JSON body,
# DELETE to remove an outfit.
ALLOWED_METHODS = "GET, POST, PUT, DELETE"

# Content-Type: application/json is not a "simple" header, so the browser
# asks for it in the preflight.
ALLOWED_HEADERS = "Content-Type"

# How long the browser may reuse a preflight answer before asking again.
PREFLIGHT_MAX_AGE_SECONDS = "600"


def allow_ui_origin(app):
    """Add the CORS headers to every response of app, for allowed origins only."""

    @app.after_request
    def add_cors_headers(response):
        # The answer depends on the Origin header, so a cache must not give
        # one origin's answer to another.
        response.vary.add("Origin")
        origin = request.headers.get("Origin")
        if origin not in config.CORS_ORIGINS:
            return response
        response.headers["Access-Control-Allow-Origin"] = origin
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
            response.headers["Access-Control-Allow-Headers"] = ALLOWED_HEADERS
            response.headers["Access-Control-Max-Age"] = PREFLIGHT_MAX_AGE_SECONDS
        return response
