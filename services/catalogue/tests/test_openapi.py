"""openapi.yaml must match the app: every route Flask serves is documented,
and nothing is documented that the app does not serve.

The document's own format is checked in CI by openapi-spec-validator.
"""
import re
from pathlib import Path

import pytest
import yaml

import main

SERVICE_DIR = Path(__file__).resolve().parent.parent

# Methods an OpenAPI path item can have, as Flask names them.
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Flask writes a path parameter as <int:song_id>, OpenAPI as {song_id}.
FLASK_PARAMETER = re.compile(r"<(?:\w+:)?(\w+)>")


def load_openapi(service_dir):
    return yaml.safe_load((service_dir / "openapi.yaml").read_text(encoding="utf-8"))


def documented_operations(document):
    """{("GET", "/api/songs/{song_id}"), ...} from the document's paths."""
    return {
        (method.upper(), path)
        for path, path_item in document["paths"].items()
        for method in path_item
        if method.upper() in HTTP_METHODS
    }


def served_operations(app):
    """The same set from the Flask app's routes. HEAD and OPTIONS are left
    out: Flask adds them to every route by itself."""
    return {
        (method, FLASK_PARAMETER.sub(r"{\1}", rule.rule))
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods & HTTP_METHODS
    }


@pytest.mark.usefixtures("demo_catalogue")
def test_every_route_is_documented_and_every_documented_path_exists():
    app = main.create_app()
    assert served_operations(app) == documented_operations(load_openapi(SERVICE_DIR))
