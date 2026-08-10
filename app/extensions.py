"""Shared Flask extensions.

Kept in a dedicated module so the SQLAlchemy instance can be imported by
models and the app factory without creating circular imports.
"""
from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
