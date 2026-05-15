from __future__ import annotations

import os

from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Set it to your Neon (or other Postgres) connection string."
    )

# Open=False so we call pool.open() explicitly in the FastAPI lifespan handler.
pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)


def init_db() -> None:
    """Open the pool and create tables if they don't exist."""
    pool.open()
    with pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regimens (
                id            SERIAL PRIMARY KEY,
                name          TEXT NOT NULL UNIQUE,
                disease_state TEXT,
                on_study      BOOLEAN NOT NULL DEFAULT FALSE,
                notes         TEXT,
                created_by    TEXT,
                updated_by    TEXT,
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE regimens ADD COLUMN IF NOT EXISTS created_by TEXT")
        conn.execute("ALTER TABLE regimens ADD COLUMN IF NOT EXISTS updated_by TEXT")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS therapies (
                id          SERIAL PRIMARY KEY,
                regimen_id  INTEGER NOT NULL
                                REFERENCES regimens(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                route       TEXT NOT NULL,
                dose        TEXT NOT NULL,
                frequency   TEXT NOT NULL,
                duration    TEXT NOT NULL,
                total_doses INTEGER,
                options     JSONB NOT NULL DEFAULT '[]'
            )
        """)
        conn.execute("""
            ALTER TABLE therapies ADD COLUMN IF NOT EXISTS options JSONB NOT NULL DEFAULT '[]'
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                username      TEXT NOT NULL UNIQUE,
                display_name  TEXT,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regimen_changes (
                id            SERIAL PRIMARY KEY,
                regimen_id    INTEGER,
                regimen_name  TEXT NOT NULL,
                action        TEXT NOT NULL,
                username      TEXT NOT NULL,
                timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                diff          JSONB NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_regimen_changes_name ON regimen_changes(regimen_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_regimen_changes_user ON regimen_changes(username)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_regimen_changes_ts ON regimen_changes(timestamp DESC)")
        # Single-row table for the groups JSON blob.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regimen_groups (
                singleton INTEGER PRIMARY KEY DEFAULT 1
                              CHECK (singleton = 1),
                data      JSONB NOT NULL DEFAULT '{}'
            )
        """)
