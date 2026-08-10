"""Application factory for the CS Electric support system."""
from __future__ import annotations

from flask import Flask, jsonify

from config import get_config
from .extensions import db


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)

    from .routes import api

    app.register_blueprint(api)

    # Import models so they are registered with SQLAlchemy metadata.
    from . import models  # noqa: F401

    @app.get("/")
    def index():
        return jsonify(
            {
                "service": "CS Electric Client Support Agent",
                "status": "running",
                "endpoints": [
                    "GET /health",
                    "POST /api/tickets",
                    "GET /api/tickets",
                    "GET /api/tickets/<id>",
                    "POST /api/tickets/<id>/messages",
                    "PATCH /api/tickets/<id>",
                ],
            }
        )

    return app
