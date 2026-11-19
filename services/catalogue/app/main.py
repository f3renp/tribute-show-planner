"""Entry point of the catalogue service: builds the Flask app and serves it
with waitress.

Start it from services/catalogue with: python app/main.py
"""
import json

from flask import Flask
from waitress import serve
from werkzeug.exceptions import HTTPException

import config
import migrate
import seed
from catalogue.api import bp as api_bp
from cors import allow_ui_origin
from health import add_health_route
from request_log import log_requests


def create_app():
    """Apply pending migrations, add the demo catalogue if it is empty, then
    build and return the Flask app.

    Seeding runs after the migrations, so the tables it fills exist.
    """
    migrate.apply_migrations()
    seed.seed_demo_catalogue()
    app = Flask(__name__)
    log_requests(app)
    allow_ui_origin(app)
    app.register_blueprint(api_bp)
    add_health_route(app)

    @app.errorhandler(HTTPException)
    def error_as_json(error):
        """Every HTTP error (abort(404), an unknown path, a wrong method, an
        unexpected exception turned into a 500) as {"errors": [message]}
        instead of Flask's HTML page. The 500 message is generic: the
        details stay in the server log, never in the answer."""
        # get_response() keeps the error's own headers, e.g. Allow on a 405.
        response = error.get_response()
        response.data = json.dumps({"errors": [error.description]})
        response.content_type = "application/json"
        return response

    return app


if __name__ == "__main__":
    # 0.0.0.0 accepts connections from outside the machine or container,
    # not only from localhost.
    serve(create_app(), host="0.0.0.0", port=config.PORT)
