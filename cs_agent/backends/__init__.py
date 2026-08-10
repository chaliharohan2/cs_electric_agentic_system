"""Catalogue backend selection."""

from __future__ import annotations

import os

from .fixtures import FixturesBackend
from .postgres import PostgresBackend
from .protocol import CatalogBackend


def get_backend() -> CatalogBackend:
    name = os.getenv("CS_BACKEND", "fixtures").lower()
    if name == "fixtures":
        return FixturesBackend()
    if name == "postgres":
        return PostgresBackend()
    raise ValueError("CS_BACKEND must be 'fixtures' or 'postgres'")


__all__ = ["CatalogBackend", "FixturesBackend", "PostgresBackend", "get_backend"]
