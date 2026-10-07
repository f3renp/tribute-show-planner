"""Entry point: builds the Flask app and serves it with waitress.

Start it with: uv run python app.py
"""
from flask import Flask, redirect, url_for
from waitress import serve

import config
import db
from catalogue.routes import bp as catalogue_bp


def create_app():
    """Create missing tables, then build and return the Flask app."""
    db.init_db()
    app = Flask(__name__)
    app.register_blueprint(catalogue_bp)

    @app.route("/")
    def home():
        return redirect(url_for("catalogue.song_list"))

    return app


if __name__ == "__main__":
    # 0.0.0.0 accepts connections from outside the machine or container,
    # not only from localhost.
    serve(create_app(), host="0.0.0.0", port=config.PORT)
