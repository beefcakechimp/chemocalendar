#!/usr/bin/env python3
"""
calendar_cli.py — SQLite-backed RegimenBank and terminal utilities (legacy CLI).

This module is NOT imported by the FastAPI web application.  It exists solely to
preserve the original command-line / SQLite workflow for local development or
one-off data entry.  All production traffic goes through pg_bank.PgBank.

Usage (from repo root):
    python -m backend.app.calendar_cli list
    python -m backend.app.calendar_cli show --name "AZA+VEN"
"""
from __future__ import annotations

import argparse
import json as _json
import os
import re
import sqlite3
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from .regimenbank import (
    Chemotherapy,
    Regimen,
    TherapyOption,
    _doses_per_day,
    parse_day_spec,
)

# ─── Config ───────────────────────────────────────────────────────────────────
SCHEMA_VERSION = 3
DEFAULT_DB = Path(__file__).resolve().parent / "regimenbank.db"
ROUTES = ["IV", "PO", "SQ", "IM", "IT"]


# ─── Terminal helpers ──────────────────────────────────────────────────────────
def _supports_ansi() -> bool:
    return sys.stdout.isatty() and (
        os.name != "nt" or "WT_SESSION" in os.environ or "TERM" in os.environ
    )


def _italic(s: str) -> str:
    return f"\x1b[3m{s}\x1b[0m" if _supports_ansi() else s


# ─── SQLite-backed Regimen Bank ────────────────────────────────────────────────
class RegimenBank:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS regimens (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                disease_state TEXT, on_study INTEGER NOT NULL DEFAULT 0,
                notes TEXT, updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS therapies (
                id INTEGER PRIMARY KEY AUTOINCREMENT, regimen_id INTEGER NOT NULL,
                name TEXT NOT NULL, route TEXT NOT NULL, dose TEXT NOT NULL,
                frequency TEXT NOT NULL, duration TEXT NOT NULL, total_doses INTEGER,
                options TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (regimen_id) REFERENCES regimens(id) ON DELETE CASCADE
            )
        """)
        cur.execute("PRAGMA table_info(regimens)")
        rcols = [row["name"] for row in cur.fetchall()]
        if "on_study" not in rcols:
            cur.execute("ALTER TABLE regimens ADD COLUMN on_study INTEGER NOT NULL DEFAULT 0")
        cur.execute("PRAGMA table_info(therapies)")
        cols = [row["name"] for row in cur.fetchall()]
        if "total_doses" not in cols:
            cur.execute("ALTER TABLE therapies ADD COLUMN total_doses INTEGER")
        if "options" not in cols:
            cur.execute("ALTER TABLE therapies ADD COLUMN options TEXT NOT NULL DEFAULT '[]'")
        self.conn.commit()

    def list_regimens(self) -> List[str]:
        cur = self.conn.execute("SELECT name FROM regimens ORDER BY name COLLATE NOCASE")
        return [row["name"] for row in cur.fetchall()]

    def get_regimen(self, name: str) -> Optional[Regimen]:
        name = name.strip()
        cur = self.conn.execute(
            "SELECT id, name, disease_state, notes, on_study FROM regimens WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        if not row:
            return None

        reg_id = row["id"]
        cur_t = self.conn.execute(
            "SELECT name, route, dose, frequency, duration, total_doses, options FROM therapies WHERE regimen_id = ? ORDER BY id",
            (reg_id,)
        )
        therapies = []
        for trow in cur_t.fetchall():
            raw_opts = trow["options"] or "[]"
            parsed_opts = [
                TherapyOption(dose=o.get("dose", ""), duration=o.get("duration", ""), total_doses=o.get("total_doses"))
                for o in _json.loads(raw_opts)
            ]
            therapies.append(Chemotherapy(trow["name"], trow["route"], trow["dose"], trow["frequency"], trow["duration"], trow["total_doses"], parsed_opts))

        return Regimen(
            name=row["name"], disease_state=row["disease_state"], on_study=bool(row["on_study"]),
            notes=row["notes"], therapies=therapies,
        )

    def upsert_regimen(self, reg: Regimen) -> None:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.conn:
            cur = self.conn.execute("SELECT id FROM regimens WHERE name = ?", (reg.name,))
            row = cur.fetchone()
            if row:
                reg_id = row["id"]
                self.conn.execute(
                    "UPDATE regimens SET disease_state = ?, notes = ?, on_study = ?, updated_at = ? WHERE id = ?",
                    (reg.disease_state, reg.notes, int(reg.on_study), now, reg_id),
                )
                self.conn.execute("DELETE FROM therapies WHERE regimen_id = ?", (reg_id,))
            else:
                self.conn.execute(
                    "INSERT INTO regimens(name, disease_state, notes, on_study, updated_at) VALUES(?, ?, ?, ?, ?)",
                    (reg.name, reg.disease_state, reg.notes, int(reg.on_study), now),
                )
                reg_id = self.conn.execute("SELECT id FROM regimens WHERE name = ?", (reg.name,)).fetchone()["id"]

            for t in reg.therapies:
                total_doses = t.total_doses if t.total_doses is not None else len(parse_day_spec(t.duration)) * _doses_per_day(t.frequency)
                opts_json = _json.dumps([{"dose": o.dose, "duration": o.duration, "total_doses": o.total_doses} for o in t.options])
                self.conn.execute(
                    "INSERT INTO therapies(regimen_id, name, route, dose, frequency, duration, total_doses, options) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (reg_id, t.name, t.route, t.dose, t.frequency, t.duration, total_doses, opts_json),
                )

    def delete_regimen(self, name: str) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM regimens WHERE name = ?", (name.strip(),))
            return cur.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        self.upsert_regimen(replace(reg, name=new_name))

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


# ─── Minimal CLI ───────────────────────────────────────────────────────────────
def _cli() -> None:
    parser = argparse.ArgumentParser(prog="calendar_cli", description="ChemoCalendar SQLite CLI")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List all regimen names")

    p_show = sub.add_parser("show", help="Show a regimen")
    p_show.add_argument("--name", required=True)

    p_del = sub.add_parser("delete", help="Delete a regimen")
    p_del.add_argument("--name", required=True)

    p_db = parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to SQLite database")

    args = parser.parse_args()
    db = RegimenBank(Path(args.db if hasattr(args, "db") and args.db else DEFAULT_DB))

    if args.cmd == "list":
        for name in db.list_regimens():
            print(name)
    elif args.cmd == "show":
        reg = db.get_regimen(args.name)
        if reg:
            print(_json.dumps(reg.to_dict(), indent=2))
        else:
            print(f"Not found: {args.name}", file=sys.stderr)
            sys.exit(1)
    elif args.cmd == "delete":
        ok = db.delete_regimen(args.name)
        print("Deleted." if ok else "Not found.")
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
