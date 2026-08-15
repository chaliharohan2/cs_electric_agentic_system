"""sqlite-vec load helper."""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def try_load_sqlite_vec(connection: sqlite3.Connection) -> bool:
    """Load sqlite-vec on ``connection``. Return False on any failure."""
    try:
        import sqlite_vec
    except ImportError:
        logger.warning("sqlite-vec package is not installed; using FTS5 lexical search")
        return False
    try:
        connection.enable_load_extension(True)
        sqlite_vec.load(connection)
        version = connection.execute("SELECT vec_version()").fetchone()
        logger.info("sqlite-vec loaded: %s", version)
        return True
    except Exception as exc:  # noqa: BLE001 — load failure must never raise
        logger.warning("sqlite-vec failed to load (%s); using FTS5 lexical search", exc)
        return False
