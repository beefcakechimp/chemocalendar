#!/usr/bin/env python3
"""
Legacy CLI tools for managing chemotherapy regimens via a local SQLite database.

This module is NOT imported by or used by the web application.
The web application uses app/pg_bank.py (PostgreSQL) for all data access.

Usage (from the backend/ directory):
    python calendar_cli.py list
    python calendar_cli.py show --name "Regimen Name"
    python calendar_cli.py delete --name "Regimen Name"
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.regimenbank import Chemotherapy, Regimen, TherapyOption, parse_day_spec

SCHEMA_VERSION = 3
DEFAULT_DB = Path(__file__).resolve().parent / "app" / "regimenbank.db"


def _supports_ansi() -> bool:
    return sys.stdout.isatty() and (
        os.name != "nt" or "WT_SESSION" in os.environ or "TERM" in os.environ
    )


def _italic(s: str) -> str:
    return f"\x1b[3m{s}\x1b[0m" if _supports_ansi() else s


class RegimenBank:
    def __init__(self, db_path: Path):
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
                for o in json.loads(raw_opts)
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
                total_doses = t.total_doses if t.total_doses is not None else len(parse_day_spec(t.duration))
                opts_json = json.dumps([{"dose": o.dose, "duration": o.duration, "total_doses": o.total_doses} for o in t.options])
                self.conn.execute(
                    "INSERT INTO therapies(regimen_id, name, route, dose, frequency, duration, total_doses, options) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (reg_id, t.name, t.route, t.dose, t.frequency, t.duration, total_doses, opts_json),
                )

    def delete_regimen(self, name: str) -> bool:
        with self.conn:
            cur = self.conn.execute("DELETE FROM regimens WHERE name = ?", (name.strip(),))
            return cur.rowcount > 0

    def save_as(self, reg: Regimen, new_name: str) -> None:
        r2 = replace(reg, name=new_name)
        self.upsert_regimen(r2)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def _list_regimens(bank: RegimenBank) -> None:
    names = bank.list_regimens()
    print("(no regimens)" if not names else "\n".join(names))


def _show_regimen(bank: RegimenBank, name: str) -> int:
    reg = bank.get_regimen(name)
    if not reg:
        print(f"Regimen '{name}' not found.")
        return 1
    print(f"\nRegimen: {reg.name}")
    if reg.disease_state:
        print(f"Disease State: {reg.disease_state}")
    if reg.notes:
        print(f"Notes: {reg.notes}")
    if not reg.therapies:
        print("Therapies: (none)")
    else:
        print("Therapies:")
        for i, t in enumerate(reg.therapies, 1):
            line = f"  {i}. {_italic(t.name)} | {t.route} | {t.dose} | {t.frequency} | {t.duration}"
            print(line)
    print("")
    return 0


def _delete_regimen(bank: RegimenBank, name: str) -> int:
    ok = bank.delete_regimen(name)
    print("Deleted." if ok else f"Regimen '{name}' not found.")
    return 0 if ok else 1


def main(argv: List[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="SQLite-backed chemotherapy regimen CLI (legacy)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to SQLite DB")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all regimen names")

    sp = sub.add_parser("show", help="Show a regimen's details")
    sp.add_argument("--name", required=True)

    sp = sub.add_parser("delete", help="Delete a regimen")
    sp.add_argument("--name", required=True)

    args = p.parse_args(argv)
    bank = RegimenBank(args.db)

    try:
        if args.cmd == "list":
            _list_regimens(bank)
            return 0
        if args.cmd == "show":
            return _show_regimen(bank, args.name)
        if args.cmd == "delete":
            return _delete_regimen(bank, args.name)
    finally:
        bank.close()

    print("Unknown command.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
