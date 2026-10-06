"""Entry point: builds the Flask app and serves it with waitress.

Start it with: uv run python app.py
"""
from flask import Flask
from waitress import serve

import config
import db


def create_app():
    """Create missing tables, then build and return the Flask app."""
    db.init_db()
    app = Flask(__name__)

    @app.route("/")
    def home():
        return "Tribute Show Planner is running."

    return app


if __name__ == "__main__":
    # 0.0.0.0 accepts connections from outside the machine or container,
    # not only from localhost.
    serve(create_app(), host="0.0.0.0", port=config.PORT)
