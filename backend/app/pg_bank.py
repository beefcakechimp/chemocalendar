"""
pg_bank.py — Postgres-backed regimen store.

Implements the same public interface as the SQLite RegimenBank so all
existing API routes keep working with zero changes.

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

from .regimenbank import Chemotherapy, Regimen, parse_day_spec

logger = logging.getLogger(__name__)


class PgBank:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

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

            therapy_rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses "
                "FROM therapies WHERE regimen_id = %s ORDER BY id",
                (reg_id,),
            ).fetchall()

        therapies = [
            Chemotherapy(
                name=tr[0],
                route=tr[1],
                dose=tr[2],
                frequency=tr[3],
                duration=tr[4],
                total_doses=tr[5],
            )
            for tr in therapy_rows
        ]
        return Regimen(
            name=rname,
            disease_state=disease_state,
            on_study=bool(on_study),
            notes=notes,
            therapies=therapies,
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

            # Full replace of therapies
            conn.execute(
                "DELETE FROM therapies WHERE regimen_id = %s", (reg_id,)
            )
            for t in reg.therapies:
                total_doses = (
                    t.total_doses
                    if t.total_doses is not None
                    else len(parse_day_spec(t.duration))
                )
                conn.execute(
                    """
                    INSERT INTO therapies
                        (regimen_id, name, route, dose, frequency, duration, total_doses)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        reg_id,
                        t.name,
                        t.route,
                        t.dose,
                        t.frequency,
                        t.duration,
                        total_doses,
                    ),
                )

    def delete_regimen(self, name: str) -> bool:
        with self.pool.connection() as conn:
            result = conn.execute(
                "DELETE FROM regimens WHERE name = %s", (name.strip(),)
            )
        return result.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

    # ── groups ────────────────────────────────────────────────────────────────

    def get_all_regimens(self) -> List[Regimen]:
        """Fetch all regimens with their therapies in a highly efficient double-query."""
        with self.pool.connection() as conn:
            reg_rows = conn.execute(
                "SELECT id, name, disease_state, notes, on_study FROM regimens ORDER BY name"
            ).fetchall()

            if not reg_rows:
                return []

            therapy_rows = conn.execute(
                "SELECT regimen_id, name, route, dose, frequency, duration, total_doses "
                "FROM therapies ORDER BY id"
            ).fetchall()

        from collections import defaultdict
        t_map = defaultdict(list)
        for tr in therapy_rows:
            t_map[tr[0]].append(
                Chemotherapy(
                    name=tr[1], route=tr[2], dose=tr[3], frequency=tr[4], duration=tr[5], total_doses=tr[6]
                )
            )

        results = []
        for row in reg_rows:
            results.append(Regimen(
                name=row[1],
                disease_state=row[2],
                on_study=bool(row[4]),
                notes=row[3],
                therapies=t_map.get(row[0], [])
            ))
        return results


    # ── cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        try:
            self.pool.close()
        except Exception:
            pass

# ── Global Lifecycle Management ──────────────────────────────────────────────

_bank_instance: Optional[PgBank] = None

def validate_db() -> bool:
    """Initialize the connection pool and verify DB connectivity."""
    global _bank_instance
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        logger.error("DATABASE_URL environment variable is missing.")
        return False
        
    try:
        pool = ConnectionPool(db_url)
        # Verify connectivity by making a simple query
        with pool.connection() as conn:
            conn.execute("SELECT 1")
            
        _bank_instance = PgBank(pool)
        return True
    except Exception as e:
        logger.error(f"Database validation failed: {e}")
        return False

def get_bank() -> PgBank:
    """Dependency injected into FastAPI routes to access the DB."""
    global _bank_instance
    if _bank_instance is None:
        # Fallback in case validate_db wasn't called (e.g., in some test environments)
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL environment variable is missing.")
        pool = ConnectionPool(db_url)
        _bank_instance = PgBank(pool)
    return _bank_instance

def close_bank() -> None:
    """Close the database connection pool safely."""
    global _bank_instance
    if _bank_instance is not None:
        _bank_instance.close()
        _bank_instance = None