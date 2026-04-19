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
    get_all_regimens()         -> List[Regimen]
    close()                    -> None
"""
from __future__ import annotations

import os
import logging
from dataclasses import replace
from typing import List, Optional

from psycopg_pool import ConnectionPool

# Make sure TherapyOption is added to your regimenbank.py models!
from .regimenbank import Chemotherapy, Regimen, TherapyOption, parse_day_spec

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
                (name,)
            ).fetchone()
            
            if not row: 
                return None
            reg_id, rname, disease_state, notes, on_study = row

            rows = conn.execute("""
                SELECT t.id, t.name, t.route, t.frequency, o.dose, o.duration, o.total_doses
                FROM therapies t LEFT JOIN therapy_options o ON t.id = o.therapy_id
                WHERE t.regimen_id = %s ORDER BY t.id, o.id
            """, (reg_id,)).fetchall()

        t_dict = {}
        for r in rows:
            t_id, t_name, t_route, t_freq, o_dose, o_dur, o_td = r
            if t_id not in t_dict:
                t_dict[t_id] = {"name": t_name, "route": t_route, "frequency": t_freq, "options": []}
            if o_dose is not None:
                t_dict[t_id]["options"].append(TherapyOption(dose=o_dose, duration=o_dur, total_doses=o_td))

        therapies = []
        for t in t_dict.values():
            opts = t["options"]
            therapies.append(Chemotherapy(
                name=t["name"], 
                route=t["route"], 
                frequency=t["frequency"], 
                options=opts,
                # Keep flat fields populated with the first option so calendar generator doesn't break
                dose=opts[0].dose if opts else "", 
                duration=opts[0].duration if opts else "", 
                total_doses=opts[0].total_doses if opts else None
            ))

        return Regimen(
            name=rname, 
            disease_state=disease_state, 
            on_study=bool(on_study), 
            notes=notes, 
            therapies=therapies
        )

    def get_all_regimens(self) -> List[Regimen]:
        """Fetch all regimens with their therapy options in a highly efficient double-query."""
        with self.pool.connection() as conn:
            reg_rows = conn.execute(
                "SELECT id, name, disease_state, notes, on_study FROM regimens ORDER BY name"
            ).fetchall()
            
            if not reg_rows: 
                return []

            rows = conn.execute("""
                SELECT t.regimen_id, t.id, t.name, t.route, t.frequency, o.dose, o.duration, o.total_doses
                FROM therapies t LEFT JOIN therapy_options o ON t.id = o.therapy_id ORDER BY t.regimen_id, t.id, o.id
            """).fetchall()

        t_dict = {}
        for r in rows:
            reg_id, t_id, t_name, t_route, t_freq, o_dose, o_dur, o_td = r
            if t_id not in t_dict:
                t_dict[t_id] = {"reg_id": reg_id, "name": t_name, "route": t_route, "frequency": t_freq, "options": []}
            if o_dose is not None:
                t_dict[t_id]["options"].append(TherapyOption(dose=o_dose, duration=o_dur, total_doses=o_td))

        from collections import defaultdict
        r_map = defaultdict(list)
        for t in t_dict.values():
            opts = t["options"]
            r_map[t["reg_id"]].append(Chemotherapy(
                name=t["name"], 
                route=t["route"], 
                frequency=t["frequency"], 
                options=opts,
                dose=opts[0].dose if opts else "", 
                duration=opts[0].duration if opts else "", 
                total_doses=opts[0].total_doses if opts else None
            ))

        results = []
        for r in reg_rows:
            results.append(Regimen(
                name=r[1], 
                disease_state=r[2], 
                on_study=bool(r[4]), 
                notes=r[3], 
                therapies=r_map.get(r[0], [])
            ))
        return results

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

            # Clear old therapies (CASCADE will handle clearing the therapy_options table)
            conn.execute("DELETE FROM therapies WHERE regimen_id = %s", (reg_id,))
            
            for t in reg.therapies:
                t_row = conn.execute(
                    "INSERT INTO therapies (regimen_id, name, route, frequency) VALUES (%s, %s, %s, %s) RETURNING id",
                    (reg_id, t.name, t.route, t.frequency)
                ).fetchone()
                t_id = t_row[0]

                # Fallback in case of an old flat API request missing the options list
                opts_to_save = t.options if t.options else [TherapyOption(dose=t.dose, duration=t.duration, total_doses=t.total_doses)]

                for opt in opts_to_save:
                    try:
                        auto_doses = len(parse_day_spec(opt.duration))
                    except Exception:
                        auto_doses = None
                    final_td = opt.total_doses if opt.total_doses is not None else auto_doses

                    conn.execute(
                        "INSERT INTO therapy_options (therapy_id, dose, duration, total_doses) VALUES (%s, %s, %s, %s)",
                        (t_id, opt.dose, opt.duration, final_td)
                    )

    def delete_regimen(self, name: str) -> bool:
        with self.pool.connection() as conn:
            result = conn.execute(
                "DELETE FROM regimens WHERE name = %s", (name.strip(),)
            )
        return result.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

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