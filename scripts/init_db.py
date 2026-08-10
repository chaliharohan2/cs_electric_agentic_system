"""Create database tables for the configured environment.

Idempotent: SQLAlchemy's ``create_all`` only creates tables that do not exist.
Usage:
    python -m scripts.init_db
"""
from __future__ import annotations

from app import create_app
from app.extensions import db


def main() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        print(f"Tables ready on {app.config['SQLALCHEMY_DATABASE_URI']}")


if __name__ == "__main__":
    main()
