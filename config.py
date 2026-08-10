"""Application configuration.

Configuration is environment-driven so the same code runs unchanged across
local development, CI, and Cloud Agent environments.
"""
from __future__ import annotations

import os


def _database_url(default: str) -> str:
    """Return a normalized SQLAlchemy database URL.

    Accepts the common ``postgres://`` scheme emitted by some platforms and
    rewrites it to the ``postgresql+psycopg2://`` form SQLAlchemy expects.
    """
    url = os.environ.get("DATABASE_URL", default)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _database_url(
        "postgresql+psycopg2://cselectric:cselectric@127.0.0.1:5432/cs_electric"
    )


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://cselectric:cselectric@127.0.0.1:5432/cs_electric_test",
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = _database_url(
        "postgresql+psycopg2://cselectric:cselectric@127.0.0.1:5432/cs_electric"
    )


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    name = name or os.environ.get("APP_ENV", "development")
    return CONFIG_MAP.get(name, DevelopmentConfig)
