from __future__ import annotations
import os
import json
import logging
from dataclasses import replace
from typing import List, Optional
from psycopg_pool import ConnectionPool
from .regimenbank import Chemotherapy, Regimen, TherapyOption, parse_day_spec

logger = logging.getLogger(__name__)

class PgBank:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def list_regimens(self) -> List[str]:
        with self.pool.connection() as conn:
            return [r[0] for r in conn.execute("SELECT name FROM regimens ORDER BY name").fetchall()]

    def get_regimen(self, name: str) -> Optional[Regimen]:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT id, name, disease_state, notes, on_study FROM regimens WHERE name = %s", (name.strip(),)).fetchone()
            if not row: return None
            reg_id, rname, disease_state, notes, on_study = row

            therapy_rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses, options FROM therapies WHERE regimen_id = %s ORDER BY id",
                (reg_id,)
            ).fetchall()

        therapies = []
        for tr in therapy_rows:
            t_opts = tr[6]
            parsed_opts = []
            if t_opts:
                opt_list = json.loads(t_opts) if isinstance(t_opts, str) else t_opts
                for opt in opt_list:
                    parsed_opts.append(TherapyOption(dose=opt.get("dose", ""), duration=opt.get("duration", ""), total_doses=opt.get("total_doses")))
            
            therapies.append(Chemotherapy(name=tr[0], route=tr[1], dose=tr[2] or "", frequency=tr[3], duration=tr[4] or "", total_doses=tr[5], options=parsed_opts))

        return Regimen(name=rname, disease_state=disease_state, on_study=bool(on_study), notes=notes, therapies=therapies)

    def get_all_regimens(self) -> List[Regimen]:
        with self.pool.connection() as conn:
            reg_rows = conn.execute("SELECT id, name, disease_state, notes, on_study FROM regimens ORDER BY name").fetchall()
            if not reg_rows: return []
            therapy_rows = conn.execute("SELECT regimen_id, name, route, dose, frequency, duration, total_doses, options FROM therapies ORDER BY id").fetchall()

        from collections import defaultdict
        t_map = defaultdict(list)
        for tr in therapy_rows:
            t_opts = tr[7]
            parsed_opts = []
            if t_opts:
                opt_list = json.loads(t_opts) if isinstance(t_opts, str) else t_opts
                for opt in opt_list:
                    parsed_opts.append(TherapyOption(dose=opt.get("dose", ""), duration=opt.get("duration", ""), total_doses=opt.get("total_doses")))
            t_map[tr[0]].append(Chemotherapy(name=tr[1], route=tr[2], dose=tr[3] or "", frequency=tr[4], duration=tr[5] or "", total_doses=tr[6], options=parsed_opts))

        return [Regimen(name=r[1], disease_state=r[2], on_study=bool(r[4]), notes=r[3], therapies=t_map.get(r[0], [])) for r in reg_rows]

    def upsert_regimen(self, reg: Regimen) -> None:
        with self.pool.connection() as conn:
            reg_id = conn.execute(
                "INSERT INTO regimens (name, disease_state, on_study, notes, updated_at) VALUES (%s, %s, %s, %s, NOW()) "
                "ON CONFLICT (name) DO UPDATE SET disease_state = EXCLUDED.disease_state, on_study = EXCLUDED.on_study, notes = EXCLUDED.notes, updated_at = NOW() RETURNING id",
                (reg.name, reg.disease_state, reg.on_study, reg.notes)
            ).fetchone()[0]

            conn.execute("DELETE FROM therapies WHERE regimen_id = %s", (reg_id,))
            for t in reg.therapies:
                try: auto_doses = len(parse_day_spec(t.duration))
                except Exception: auto_doses = None
                total_doses = t.total_doses if t.total_doses is not None else auto_doses

                opts_json = json.dumps([{"dose": o.dose, "duration": o.duration, "total_doses": o.total_doses} for o in t.options])

                conn.execute(
                    "INSERT INTO therapies (regimen_id, name, route, dose, frequency, duration, total_doses, options) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                    (reg_id, t.name, t.route, t.dose, t.frequency, t.duration, total_doses, opts_json)
                )

    def delete_regimen(self, name: str) -> bool:
        with self.pool.connection() as conn: return conn.execute("DELETE FROM regimens WHERE name = %s", (name.strip(),)).rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

    def close(self) -> None:
        try: self.pool.close()
        except Exception: pass

_bank_instance: Optional[PgBank] = None
def validate_db() -> bool:
    global _bank_instance
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: return False
    try:
        pool = ConnectionPool(db_url)
        with pool.connection() as conn: conn.execute("SELECT 1")
        _bank_instance = PgBank(pool)
        return True
    except Exception: return False

def get_bank() -> PgBank:
    global _bank_instance
    if _bank_instance is None: _bank_instance = PgBank(ConnectionPool(os.environ["DATABASE_URL"]))
    return _bank_instance

def close_bank() -> None:
    global _bank_instance
    if _bank_instance: _bank_instance.close(); _bank_instance = None