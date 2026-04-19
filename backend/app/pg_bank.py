"""
pg_bank.py — Postgres-backed regimen store with variant support.

Public API:
    list_regimens()            -> List[str]
    get_regimen(name)          -> Optional[Regimen]
    upsert_regimen(reg)        -> None
    delete_regimen(name)       -> bool
    save_as(reg, new_name)     -> None
    get_groups()               -> dict
    save_groups(groups)        -> None
    close()                    -> None
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import replace
from typing import List, Optional

from psycopg_pool import ConnectionPool

from .regimenbank import Chemotherapy, Regimen, RegimenVariant, parse_day_spec

logger = logging.getLogger(__name__)


class PgBank:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    # ── schema ────────────────────────────────────────────────────────────────

    def ensure_schema(self) -> None:
        """Create all tables if they don't exist and run lightweight migrations."""
        with self.pool.connection() as conn:
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

            # Variants table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS regimen_variants (
                    id         SERIAL PRIMARY KEY,
                    regimen_id INTEGER NOT NULL
                                   REFERENCES regimens(id) ON DELETE CASCADE,
                    label      TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS therapies (
                    id          SERIAL PRIMARY KEY,
                    regimen_id  INTEGER NOT NULL
                                    REFERENCES regimens(id) ON DELETE CASCADE,
                    variant_id  INTEGER
                                    REFERENCES regimen_variants(id) ON DELETE CASCADE,
                    name        TEXT NOT NULL,
                    route       TEXT NOT NULL,
                    dose        TEXT NOT NULL,
                    frequency   TEXT NOT NULL,
                    duration    TEXT NOT NULL,
                    total_doses INTEGER
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS regimen_groups (
                    singleton INTEGER PRIMARY KEY DEFAULT 1
                                  CHECK (singleton = 1),
                    data      JSONB NOT NULL DEFAULT '{}'
                )
            """)

            # Migration: add variant_id column if it doesn't exist on older DBs
            conn.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='therapies' AND column_name='variant_id'
                    ) THEN
                        ALTER TABLE therapies
                            ADD COLUMN variant_id INTEGER
                                REFERENCES regimen_variants(id) ON DELETE CASCADE;
                    END IF;
                END
                $$;
            """)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _fetch_therapies(self, conn, *, regimen_id: int, variant_id: Optional[int]) -> List[Chemotherapy]:
        if variant_id is None:
            rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses "
                "FROM therapies WHERE regimen_id = %s AND variant_id IS NULL ORDER BY id",
                (regimen_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses "
                "FROM therapies WHERE variant_id = %s ORDER BY id",
                (variant_id,),
            ).fetchall()
        return [Chemotherapy(*r) for r in rows]

    def _insert_therapies(self, conn, therapies: List[Chemotherapy], *, regimen_id: int, variant_id: Optional[int]) -> None:
        for t in therapies:
            total_doses = (
                t.total_doses
                if t.total_doses is not None
                else len(parse_day_spec(t.duration))
            )
            conn.execute(
                """
                INSERT INTO therapies
                    (regimen_id, variant_id, name, route, dose, frequency, duration, total_doses)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (regimen_id, variant_id, t.name, t.route, t.dose, t.frequency, t.duration, total_doses),
            )

    # ── read ──────────────────────────────────────────────────────────────────

    def list_regimens(self) -> List[str]:
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT name FROM regimens ORDER BY name"
            ).fetchall()
        return [r[0] for r in rows]

    def get_regimen(self, name: str) -> Optional[Regimen]:
        name = name.strip()
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT id, name, disease_state, notes, on_study "
                "FROM regimens WHERE name = %s",
                (name,),
            ).fetchone()
            if not row:
                return None
            reg_id, rname, disease_state, notes, on_study = row

            base_therapies = self._fetch_therapies(conn, regimen_id=reg_id, variant_id=None)

            variant_rows = conn.execute(
                "SELECT id, label FROM regimen_variants "
                "WHERE regimen_id = %s ORDER BY sort_order, id",
                (reg_id,),
            ).fetchall()

            variants = [
                RegimenVariant(
                    label=vr[1],
                    therapies=self._fetch_therapies(conn, regimen_id=reg_id, variant_id=vr[0]),
                )
                for vr in variant_rows
            ]

        return Regimen(
            name=rname,
            disease_state=disease_state,
            on_study=bool(on_study),
            notes=notes,
            therapies=base_therapies,
            variants=variants,
        )

    # ── write ─────────────────────────────────────────────────────────────────

    def upsert_regimen(self, reg: Regimen) -> None:
        with self.pool.connection() as conn:
            row = conn.execute(
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
                (reg.name, reg.disease_state, reg.on_study, reg.notes),
            ).fetchone()
            reg_id = row[0]

            # Full replace: delete all therapies and variants, then re-insert
            conn.execute("DELETE FROM therapies WHERE regimen_id = %s", (reg_id,))
            conn.execute("DELETE FROM regimen_variants WHERE regimen_id = %s", (reg_id,))

            # Base therapies (variant_id = NULL)
            self._insert_therapies(conn, reg.therapies, regimen_id=reg_id, variant_id=None)

            # Variants
            for sort_order, v in enumerate(reg.variants):
                variant_row = conn.execute(
                    """
                    INSERT INTO regimen_variants (regimen_id, label, sort_order)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (reg_id, v.label, sort_order),
                ).fetchone()
                variant_id = variant_row[0]
                self._insert_therapies(conn, v.therapies, regimen_id=reg_id, variant_id=variant_id)

    def delete_regimen(self, name: str) -> bool:
        with self.pool.connection() as conn:
            result = conn.execute(
                "DELETE FROM regimens WHERE name = %s", (name.strip(),)
            )
        return result.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

    # ── groups ────────────────────────────────────────────────────────────────

    def get_groups(self) -> dict:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT data FROM regimen_groups WHERE singleton = 1"
            ).fetchone()
        if not row:
            return {}
        data = row[0]
        return json.loads(data) if isinstance(data, str) else data

    def save_groups(self, groups: dict) -> None:
        with self.pool.connection() as conn:
            conn.execute(
                """
                INSERT INTO regimen_groups (singleton, data) VALUES (1, %s)
                ON CONFLICT (singleton) DO UPDATE SET data = EXCLUDED.data
                """,
                (json.dumps(groups),),
            )

    # ── cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self.pool.close()
        except Exception:
            pass


# ── Global Lifecycle Management ──────────────────────────────────────────────

_bank_instance: Optional[PgBank] = None


def validate_db() -> bool:
    """Initialize the connection pool, ensure schema, verify DB connectivity."""
    global _bank_instance
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        logger.error("DATABASE_URL environment variable is missing.")
        return False

    try:
        pool = ConnectionPool(db_url)
        bank = PgBank(pool)
        bank.ensure_schema()
        # Verify connectivity
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        _bank_instance = bank
        return True
    except Exception as e:
        logger.error(f"Database validation failed: {e}")
        return False


def get_bank() -> PgBank:
    """Dependency injected into FastAPI routes to access the DB."""
    global _bank_instance
    if _bank_instance is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is missing.")
        pool = ConnectionPool(db_url)
        bank = PgBank(pool)
        bank.ensure_schema()
        _bank_instance = bank
    return _bank_instance


def close_bank() -> None:
    """Close the database connection pool safely."""
    global _bank_instance
    if _bank_instance is not None:
        _bank_instance.close()
        _bank_instance = None
