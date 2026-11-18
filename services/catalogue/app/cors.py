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

CORS stops another site from reading our answers, not from sending us
requests: a hostile page can still auto-submit an HTML form (a "simple"
POST, with no preflight). So a request that changes data and comes from a
page on another origin is refused with 403 before it runs (cross-site
request forgery). Requests with no Origin header, like curl or the shows
service calling the catalogue, are not from a browser page and pass.

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


# Methods that only read. Every other method may change data.
READ_ONLY_METHODS = ("GET", "HEAD", "OPTIONS")


def allow_ui_origin(app):
    """Refuse changes from other origins, and add the CORS headers to every
    response of app, for allowed origins only."""

    @app.before_request
    def refuse_changes_from_other_origins():
        # Returning None lets the request run; returning a response stops it.
        origin = request.headers.get("Origin")
        if request.method in READ_ONLY_METHODS or origin is None:
            return None
        if origin in config.CORS_ORIGINS:
            return None
        return {"errors": [f"Origin {origin} may not change data here."]}, 403

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
