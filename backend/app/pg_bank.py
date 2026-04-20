"""
pg_bank.py — Postgres-backed regimen store.
Implements the same public interface as the SQLite RegimenBank.
"""
from __future__ import annotations

import os
import logging
from dataclasses import replace
from typing import List, Optional

from psycopg_pool import ConnectionPool

from .regimenbank import Chemotherapy, Regimen, RegimenVariant, parse_day_spec

logger = logging.getLogger(__name__)

class PgBank:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    # ── read ──────────────────────────────────────────────────────────────────

    def list_regimens(self) -> List[str]:
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT name FROM regimens ORDER BY name").fetchall()
        return [r[0] for r in rows]

    def get_regimen(self, name: str) -> Optional[Regimen]:
        name = name.strip()
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT id, name, disease_state, notes, on_study "
                "FROM regimens WHERE name = %s", (name,)
            ).fetchone()
            if not row:
                return None
            reg_id, rname, disease_state, notes, on_study = row

            # 1. Fetch Base Therapies (variant_id IS NULL)
            t_rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses "
                "FROM therapies WHERE regimen_id = %s AND variant_id IS NULL ORDER BY id",
                (reg_id,)
            ).fetchall()
            base_therapies = [
                Chemotherapy(name=r[0], route=r[1], dose=r[2] or "", frequency=r[3], duration=r[4] or "", total_doses=r[5])
                for r in t_rows
            ]

            # 2. Fetch Variants and their Therapies
            v_rows = conn.execute(
                "SELECT id, label FROM regimen_variants WHERE regimen_id = %s ORDER BY sort_order, id",
                (reg_id,)
            ).fetchall()
            
            variants = []
            for vr in v_rows:
                vt_rows = conn.execute(
                    "SELECT name, route, dose, frequency, duration, total_doses "
                    "FROM therapies WHERE variant_id = %s ORDER BY id",
                    (vr[0],)
                ).fetchall()
                vt_therapies = [
                    Chemotherapy(name=tr[0], route=tr[1], dose=tr[2] or "", frequency=tr[3], duration=tr[4] or "", total_doses=tr[5])
                    for tr in vt_rows
                ]
                variants.append(RegimenVariant(label=vr[1], therapies=vt_therapies))

        return Regimen(
            name=rname,
            disease_state=disease_state,
            on_study=bool(on_study),
            notes=notes,
            therapies=base_therapies,
            variants=variants
        )

    def get_all_regimens(self) -> List[Regimen]:
        """Fetch all regimens, base therapies, and variants highly efficiently."""
        with self.pool.connection() as conn:
            reg_rows = conn.execute("SELECT id, name, disease_state, notes, on_study FROM regimens ORDER BY name").fetchall()
            if not reg_rows:
                return []

            var_rows = conn.execute("SELECT id, regimen_id, label FROM regimen_variants ORDER BY sort_order, id").fetchall()
            ther_rows = conn.execute("SELECT regimen_id, variant_id, name, route, dose, frequency, duration, total_doses FROM therapies ORDER BY id").fetchall()

        from collections import defaultdict
        
        v_map = defaultdict(list)
        for vr in var_rows:
            v_map[vr[1]].append({"id": vr[0], "label": vr[2], "therapies": []})

        t_base_map = defaultdict(list)
        t_var_map = defaultdict(list)

        for tr in ther_rows:
            t_obj = Chemotherapy(name=tr[2], route=tr[3], dose=tr[4] or "", frequency=tr[5], duration=tr[6] or "", total_doses=tr[7])
            if tr[1] is None:
                t_base_map[tr[0]].append(t_obj)
            else:
                t_var_map[tr[1]].append(t_obj)

        results = []
        for rr in reg_rows:
            reg_id = rr[0]
            variants = []
            for v in v_map[reg_id]:
                variants.append(RegimenVariant(label=v["label"], therapies=t_var_map[v["id"]]))
            
            results.append(Regimen(
                name=rr[1], disease_state=rr[2], on_study=bool(rr[4]), notes=rr[3],
                therapies=t_base_map[reg_id], variants=variants
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

            # Clear old data
            conn.execute("DELETE FROM therapies WHERE regimen_id = %s", (reg_id,))
            conn.execute("DELETE FROM regimen_variants WHERE regimen_id = %s", (reg_id,))

            # Insert Base Therapies
            for t in reg.therapies:
                try: auto_doses = len(parse_day_spec(t.duration))
                except Exception: auto_doses = None
                td = t.total_doses if t.total_doses is not None else auto_doses

                conn.execute(
                    "INSERT INTO therapies (regimen_id, variant_id, name, route, dose, frequency, duration, total_doses) "
                    "VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)",
                    (reg_id, t.name, t.route, t.dose, t.frequency, t.duration, td)
                )

            # Insert Variants
            for i, v in enumerate(reg.variants):
                v_row = conn.execute(
                    "INSERT INTO regimen_variants (regimen_id, label, sort_order) VALUES (%s, %s, %s) RETURNING id",
                    (reg_id, v.label, i)
                ).fetchone()
                vid = v_row[0]

                for t in v.therapies:
                    try: auto_doses = len(parse_day_spec(t.duration))
                    except Exception: auto_doses = None
                    td = t.total_doses if t.total_doses is not None else auto_doses

                    conn.execute(
                        "INSERT INTO therapies (regimen_id, variant_id, name, route, dose, frequency, duration, total_doses) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (reg_id, vid, t.name, t.route, t.dose, t.frequency, t.duration, td)
                    )

    def delete_regimen(self, name: str) -> bool:
        with self.pool.connection() as conn:
            result = conn.execute("DELETE FROM regimens WHERE name = %s", (name.strip(),))
        return result.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

    # ── cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        try: self.pool.close()
        except Exception: pass

_bank_instance: Optional[PgBank] = None

def validate_db() -> bool:
    global _bank_instance
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is missing.")
        return False
    try:
        pool = ConnectionPool(db_url)
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        _bank_instance = PgBank(pool)
        return True
    except Exception as e:
        logger.error(f"Database validation failed: {e}")
        return False

def get_bank() -> PgBank:
    global _bank_instance
    if _bank_instance is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url: raise RuntimeError("DATABASE_URL environment variable is missing.")
        _bank_instance = PgBank(ConnectionPool(db_url))
    return _bank_instance

def close_bank() -> None:
    global _bank_instance
    if _bank_instance is not None:
        _bank_instance.close()
        _bank_instance = None