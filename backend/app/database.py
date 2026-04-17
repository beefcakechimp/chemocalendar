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
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
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
                total_doses INTEGER
            )
        """)
        # Single-row table for the groups JSON blob.
        # The singleton=1 constraint enforces at most one row.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regimen_groups (
                singleton INTEGER PRIMARY KEY DEFAULT 1
                              CHECK (singleton = 1),
                data      JSONB NOT NULL DEFAULT '{}'
            )
        """)
