"""
Lazy database initialization for the Chemo Calendar API.

Key design choices:
  - DB is NOT created at import time. This avoids crashes when
    the persistent volume isn't mounted yet (Railway, Fly.io).
  - WAL mode is enabled for concurrent read access from multiple users.
  - A single RegimenBank instance is reused across requests via FastAPI
    dependency injection.
  - Startup validation checks that the DB path is writable before
    accepting traffic.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from backend.app.regimenbank import RegimenBank

logger = logging.getLogger(__name__)

_bank: Optional[RegimenBank] = None


def _resolve_db_path() -> Path:
    """Determine the database path from environment or fallback."""
    raw = os.environ.get("DB_PATH", "")
    if raw:
        return Path(raw)
    # Sensible fallback: /data if it exists (Docker volume), else local
    if Path("/data").is_dir():
        return Path("/data/regimenbank.db")
    return Path("regimenbank.db")


def get_bank() -> RegimenBank:
    """
    Return the singleton RegimenBank, creating it on first call.

    Called as a FastAPI dependency so the app doesn't crash at import
    time if the volume isn't ready yet.
    """
    global _bank
    if _bank is None:
        db_path = _resolve_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Opening database at %s", db_path)
        _bank = RegimenBank(db_path)
        _enable_wal(_bank)
    return _bank


def _enable_wal(bank: RegimenBank) -> None:
    """
    Enable WAL journal mode for better concurrent read performance.

    WAL lets multiple readers proceed without blocking each other and
    without blocking the single writer. Essential once you have 2+
    simultaneous users.
    """
    try:
        mode = bank.conn.execute("PRAGMA journal_mode=WAL").fetchone()
        logger.info("SQLite journal mode: %s", mode[0] if mode else "unknown")
    except Exception as e:
        logger.warning("Could not enable WAL mode: %s", e)


def validate_db() -> bool:
    """
    Quick smoke test: can we open the DB and run a trivial query?
    Called during startup to fail fast if the volume is broken.
    """
    try:
        bank = get_bank()
        bank.conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("Database validation failed: %s", e)
        return False


def close_bank() -> None:
    """Cleanly close the DB connection on shutdown."""
    global _bank
    if _bank is not None:
        try:
            _bank.close()
        except Exception:
            pass
        _bank = None
