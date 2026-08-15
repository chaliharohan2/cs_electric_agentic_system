"""Catalogue backend selection."""

from __future__ import annotations

import os

from .fixtures import FixturesBackend
from .protocol import CatalogBackend
from .sqlite import SqliteBackend


def get_backend() -> CatalogBackend:
    name = os.getenv("CS_BACKEND", "sqlite").lower()
    if name == "fixtures":
        return FixturesBackend()
    if name == "sqlite":
        return SqliteBackend()
    raise ValueError("CS_BACKEND must be 'sqlite' or 'fixtures'")


__all__ = [
    "CatalogBackend",
    "FixturesBackend",
    "SqliteBackend",
    "get_backend",
]
