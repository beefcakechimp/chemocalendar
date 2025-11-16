#!/usr/bin/env python3
import json
import sqlite3
import sys
import time
from pathlib import Path


def init_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS regimens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            disease_state TEXT,
            notes         TEXT,
            updated_at    TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS therapies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            regimen_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            route       TEXT NOT NULL,
            dose        TEXT NOT NULL,
            frequency   TEXT NOT NULL,
            duration    TEXT NOT NULL,
            FOREIGN KEY (regimen_id) REFERENCES regimens(id) ON DELETE CASCADE
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_regimens_name ON regimens(name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_therapies_regimen ON therapies(regimen_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_therapies_name ON therapies(name)")
    conn.commit()


def migrate(json_path: Path, db_path: Path) -> None:
    if not json_path.exists():
        print(f"JSON file not found: {json_path}")
        sys.exit(1)

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        print("JSON root is not an object; aborting.")
        sys.exit(1)

    regimens = raw.get("regimens", {})
    if not isinstance(regimens, dict):
        print("JSON 'regimens' is not an object; aborting.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_schema(conn)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with conn:
        count = 0
        for name, rec in regimens.items():
            if not isinstance(rec, dict):
                continue
            disease_state = rec.get("disease_state")
            notes = rec.get("notes")
            therapies = rec.get("therapies", []) or []

            # upsert regimen
            cur = conn.execute("SELECT id FROM regimens WHERE name = ?", (name,))
            row = cur.fetchone()
            if row:
                reg_id = row["id"]
                conn.execute(
                    "UPDATE regimens SET disease_state = ?, notes = ?, updated_at = ? "
                    "WHERE id = ?",
                    (disease_state, notes, now, reg_id),
                )
                conn.execute("DELETE FROM therapies WHERE regimen_id = ?", (reg_id,))
            else:
                conn.execute(
                    "INSERT INTO regimens(name, disease_state, notes, updated_at) "
                    "VALUES(?, ?, ?, ?)",
                    (name, disease_state, notes, now),
                )
                reg_id = conn.execute(
                    "SELECT id FROM regimens WHERE name = ?",
                    (name,),
                ).fetchone()["id"]

            # insert therapies
            for t in therapies:
                if not isinstance(t, dict):
                    continue
                conn.execute(
                    "INSERT INTO therapies(regimen_id, name, route, dose, frequency, duration) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (
                        reg_id,
                        t.get("name", ""),
                        t.get("route", ""),
                        t.get("dose", ""),
                        t.get("frequency", ""),
                        t.get("duration", ""),
                    ),
                )
            count += 1

    conn.close()
    print(f"Migrated {count} regimens from {json_path} → {db_path}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: migrate.py <regimenbank.json> <regimenbank.db>")
        return 1
    json_path = Path(argv[0])
    db_path = Path(argv[1])
    migrate(json_path, db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
