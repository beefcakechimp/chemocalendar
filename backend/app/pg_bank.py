from __future__ import annotations
import os
import json
import logging
from dataclasses import replace
from typing import Any, Dict, List, Optional
from psycopg_pool import ConnectionPool
from .regimenbank import Chemotherapy, Regimen, TherapyOption, parse_day_spec

logger = logging.getLogger(__name__)


def _regimen_snapshot(reg: Regimen) -> Dict[str, Any]:
    return {
        "name": reg.name,
        "disease_state": reg.disease_state,
        "on_study": reg.on_study,
        "notes": reg.notes,
        "therapies": [
            {
                "name": t.name, "route": t.route, "dose": t.dose, "frequency": t.frequency,
                "duration": t.duration, "total_doses": t.total_doses,
                "options": [
                    {"dose": o.dose, "duration": o.duration, "total_doses": o.total_doses}
                    for o in (t.options or [])
                ],
            }
            for t in (reg.therapies or [])
        ],
    }


def _compute_diff(before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if before is None and after is not None:
        return {"before": None, "after": after, "fields_changed": list(after.keys())}
    if after is None and before is not None:
        return {"before": before, "after": None, "fields_changed": list(before.keys())}
    if before is None or after is None:
        return {"before": before, "after": after, "fields_changed": []}
    changed: List[str] = []
    for k in ("name", "disease_state", "on_study", "notes"):
        if before.get(k) != after.get(k):
            changed.append(k)
    if (before.get("therapies") or []) != (after.get("therapies") or []):
        changed.append("therapies")
    return {"before": before, "after": after, "fields_changed": changed}


class PgBank:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def list_regimens(self) -> List[str]:
        with self.pool.connection() as conn:
            return [r[0] for r in conn.execute("SELECT name FROM regimens ORDER BY name").fetchall()]

    def _hydrate_therapies(self, therapy_rows) -> List[Chemotherapy]:
        therapies = []
        for tr in therapy_rows:
            t_opts = tr[6]
            parsed_opts = []
            if t_opts:
                opt_list = json.loads(t_opts) if isinstance(t_opts, str) else t_opts
                for opt in opt_list:
                    parsed_opts.append(TherapyOption(dose=opt.get("dose", ""), duration=opt.get("duration", ""), total_doses=opt.get("total_doses")))
            therapies.append(Chemotherapy(name=tr[0], route=tr[1], dose=tr[2] or "", frequency=tr[3], duration=tr[4] or "", total_doses=tr[5], options=parsed_opts))
        return therapies

    def get_regimen(self, name: str) -> Optional[Regimen]:
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT id, name, disease_state, notes, on_study, created_by, updated_by FROM regimens WHERE name = %s",
                (name.strip(),)
            ).fetchone()
            if not row: return None
            reg_id, rname, disease_state, notes, on_study, created_by, updated_by = row
            therapy_rows = conn.execute(
                "SELECT name, route, dose, frequency, duration, total_doses, options FROM therapies WHERE regimen_id = %s ORDER BY id",
                (reg_id,)
            ).fetchall()

        reg = Regimen(name=rname, disease_state=disease_state, on_study=bool(on_study), notes=notes, therapies=self._hydrate_therapies(therapy_rows))
        setattr(reg, "created_by", created_by)
        setattr(reg, "updated_by", updated_by)
        return reg

    def get_all_regimens(self) -> List[Regimen]:
        with self.pool.connection() as conn:
            reg_rows = conn.execute(
                "SELECT id, name, disease_state, notes, on_study, created_by, updated_by FROM regimens ORDER BY name"
            ).fetchall()
            if not reg_rows: return []
            therapy_rows = conn.execute(
                "SELECT regimen_id, name, route, dose, frequency, duration, total_doses, options FROM therapies ORDER BY id"
            ).fetchall()

        from collections import defaultdict
        t_map: Dict[int, List[Chemotherapy]] = defaultdict(list)
        for tr in therapy_rows:
            t_opts = tr[7]
            parsed_opts = []
            if t_opts:
                opt_list = json.loads(t_opts) if isinstance(t_opts, str) else t_opts
                for opt in opt_list:
                    parsed_opts.append(TherapyOption(dose=opt.get("dose", ""), duration=opt.get("duration", ""), total_doses=opt.get("total_doses")))
            t_map[tr[0]].append(Chemotherapy(name=tr[1], route=tr[2], dose=tr[3] or "", frequency=tr[4], duration=tr[5] or "", total_doses=tr[6], options=parsed_opts))

        results = []
        for r in reg_rows:
            reg = Regimen(name=r[1], disease_state=r[2], on_study=bool(r[4]), notes=r[3], therapies=t_map.get(r[0], []))
            setattr(reg, "created_by", r[5])
            setattr(reg, "updated_by", r[6])
            results.append(reg)
        return results

    def upsert_regimen(self, reg: Regimen, username: str = "anonymous") -> Dict[str, Any]:
        before = self.get_regimen(reg.name)
        before_snap = _regimen_snapshot(before) if before else None
        action = "update" if before else "create"
        after_snap = _regimen_snapshot(reg)

        with self.pool.connection() as conn:
            if before:
                reg_id = conn.execute(
                    "UPDATE regimens SET disease_state = %s, on_study = %s, notes = %s, updated_by = %s, updated_at = NOW() WHERE name = %s RETURNING id",
                    (reg.disease_state, reg.on_study, reg.notes, username, reg.name)
                ).fetchone()[0]
            else:
                reg_id = conn.execute(
                    "INSERT INTO regimens (name, disease_state, on_study, notes, created_by, updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id",
                    (reg.name, reg.disease_state, reg.on_study, reg.notes, username, username)
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

            diff = _compute_diff(before_snap, after_snap)
            if action == "create" or diff["fields_changed"]:
                conn.execute(
                    "INSERT INTO regimen_changes (regimen_id, regimen_name, action, username, diff) VALUES (%s, %s, %s, %s, %s::jsonb)",
                    (reg_id, reg.name, action, username, json.dumps(diff))
                )
        return {"action": action, "fields_changed": diff["fields_changed"]}

    def delete_regimen(self, name: str, username: str = "anonymous") -> bool:
        before = self.get_regimen(name)
        if not before: return False
        before_snap = _regimen_snapshot(before)
        with self.pool.connection() as conn:
            row = conn.execute("DELETE FROM regimens WHERE name = %s RETURNING id", (name.strip(),)).fetchone()
            if not row: return False
            reg_id = row[0]
            diff = _compute_diff(before_snap, None)
            conn.execute(
                "INSERT INTO regimen_changes (regimen_id, regimen_name, action, username, diff) VALUES (%s, %s, %s, %s, %s::jsonb)",
                (reg_id, name.strip(), "delete", username, json.dumps(diff))
            )
        return True

    def save_as(self, reg: Regimen, new_name: str, username: str = "anonymous") -> None:
        self.upsert_regimen(replace(reg, name=new_name), username=username)

    # Users
    def list_users(self) -> List[Dict[str, Any]]:
        with self.pool.connection() as conn:
            rows = conn.execute("SELECT username, display_name, created_at FROM users ORDER BY username").fetchall()
        return [{"username": r[0], "display_name": r[1], "created_at": r[2].isoformat() if r[2] else None} for r in rows]

    def create_user(self, username: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        u = username.strip().lower()
        if not u: raise ValueError("username required")
        with self.pool.connection() as conn:
            row = conn.execute(
                "INSERT INTO users (username, display_name) VALUES (%s, %s) "
                "ON CONFLICT (username) DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, users.display_name) "
                "RETURNING username, display_name, created_at",
                (u, display_name)
            ).fetchone()
        return {"username": row[0], "display_name": row[1], "created_at": row[2].isoformat() if row[2] else None}

    # Audit log
    def get_audit_log(self, regimen_name: Optional[str] = None, username: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if regimen_name:
            clauses.append("regimen_name = %s")
            params.append(regimen_name.strip())
        if username:
            clauses.append("username = %s")
            params.append(username.strip())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(max(1, min(1000, limit)))
        with self.pool.connection() as conn:
            rows = conn.execute(
                f"SELECT id, regimen_id, regimen_name, action, username, timestamp, diff FROM regimen_changes{where} ORDER BY timestamp DESC LIMIT %s",
                params
            ).fetchall()
        out = []
        for r in rows:
            diff = r[6]
            if isinstance(diff, str):
                try: diff = json.loads(diff)
                except Exception: diff = {}
            out.append({
                "id": r[0],
                "regimen_id": r[1],
                "regimen_name": r[2],
                "action": r[3],
                "username": r[4],
                "timestamp": r[5].isoformat() if r[5] else None,
                "diff": diff or {},
            })
        return out

    def close(self) -> None:
        try: self.pool.close()
        except Exception: pass


_bank_instance: Optional[PgBank] = None


def _ensure_schema(pool: ConnectionPool) -> None:
    with pool.connection() as conn:
        conn.execute("ALTER TABLE therapies ADD COLUMN IF NOT EXISTS options JSONB NOT NULL DEFAULT '[]'")
        conn.execute("ALTER TABLE regimens ADD COLUMN IF NOT EXISTS created_by TEXT")
        conn.execute("ALTER TABLE regimens ADD COLUMN IF NOT EXISTS updated_by TEXT")
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


def validate_db() -> bool:
    global _bank_instance
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: return False
    try:
        pool = ConnectionPool(db_url)
        with pool.connection() as conn: conn.execute("SELECT 1")
        _ensure_schema(pool)
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
