#!/usr/bin/env python3
"""
seed_from_sqlite.py — one-shot migration from SQLite → Postgres.

Run this ONCE from your Codespace after setting DATABASE_URL:

    DATABASE_URL="postgresql://..." python backend/seed_from_sqlite.py

It reads every regimen + therapy from your local SQLite DB and upserts
them into Postgres.  Safe to re-run (upserts are idempotent).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── resolve SQLite path ───────────────────────────────────────────────────────
# Try the env var first, then the default repo location.
sqlite_path_str = os.environ.get("SQLITE_DB", "backend/regimenbank.db")
sqlite_path = Path(sqlite_path_str)

if not sqlite_path.exists():
    print(f"ERROR: SQLite DB not found at {sqlite_path}")
    print("Set SQLITE_DB=<path> or run from the repo root.")
    sys.exit(1)

# ── check DATABASE_URL ────────────────────────────────────────────────────────
database_url = os.environ.get("DATABASE_URL", "")
if not database_url:
    print("ERROR: DATABASE_URL is not set.")
    print('Export it first:  export DATABASE_URL="postgresql://..."')
    sys.exit(1)

# ── import after env checks so errors are clear ───────────────────────────────
import sqlite3
import psycopg

print(f"Reading from SQLite:  {sqlite_path}")
print(f"Writing to Postgres:  {database_url[:40]}...")

# ── read from SQLite ──────────────────────────────────────────────────────────
sq = sqlite3.connect(sqlite_path)
sq.row_factory = sqlite3.Row

regimens = sq.execute(
    "SELECT id, name, disease_state, on_study, notes FROM regimens ORDER BY id"
).fetchall()

therapies_by_regimen: dict[int, list] = {}
for t in sq.execute(
    "SELECT regimen_id, name, route, dose, frequency, duration, total_doses "
    "FROM therapies ORDER BY id"
).fetchall():
    therapies_by_regimen.setdefault(t["regimen_id"], []).append(t)

sq.close()
print(f"Found {len(regimens)} regimens in SQLite.")

# ── write to Postgres ─────────────────────────────────────────────────────────
inserted = 0
skipped = 0

with psycopg.connect(database_url) as pg:
    # Ensure tables exist (mirrors database.py)
    pg.execute("""
        CREATE TABLE IF NOT EXISTS regimens (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL UNIQUE,
            disease_state TEXT,
            on_study      BOOLEAN NOT NULL DEFAULT FALSE,
            notes         TEXT,
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    pg.execute("""
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
    pg.execute("""
        CREATE TABLE IF NOT EXISTS regimen_groups (
            singleton INTEGER PRIMARY KEY DEFAULT 1
                          CHECK (singleton = 1),
            data      JSONB NOT NULL DEFAULT '{}'
        )
    """)

    for reg in regimens:
        row = pg.execute(
            """
            INSERT INTO regimens (name, disease_state, on_study, notes, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (name) DO UPDATE SET
                disease_state = EXCLUDED.disease_state,
                on_study      = EXCLUDED.on_study,
                notes         = EXCLUDED.notes,
                updated_at    = NOW()
            RETURNING id
            """,
            (reg["name"], reg["disease_state"], bool(reg["on_study"]), reg["notes"]),
        ).fetchone()
        pg_reg_id = row[0]

        # Replace therapies
        pg.execute("DELETE FROM therapies WHERE regimen_id = %s", (pg_reg_id,))
        for t in therapies_by_regimen.get(reg["id"], []):
            pg.execute(
                """
                INSERT INTO therapies
                    (regimen_id, name, route, dose, frequency, duration, total_doses)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    pg_reg_id,
                    t["name"],
                    t["route"],
                    t["dose"],
                    t["frequency"],
                    t["duration"],
                    t["total_doses"],
                ),
            )
        print(f"  ✓  {reg['name']}")
        inserted += 1

    pg.commit()

print(f"\nDone. {inserted} regimens migrated to Postgres.")
