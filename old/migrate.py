#!/usr/bin/env python3
import json
import sqlite3
import sys
import time
from pathlib import Path


def init_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    # --- Tables ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS regimens (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            disease_state TEXT,
            on_study      INTEGER NOT NULL DEFAULT 0,  -- 0 = off protocol, 1 = on study
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
            total_doses INTEGER,
            FOREIGN KEY (regimen_id) REFERENCES regimens(id) ON DELETE CASCADE
        )
    """)

    # --- Lightweight migrations for older DBs ---

    # Ensure on_study exists on regimens
    try:
        cur.execute("ALTER TABLE regimens ADD COLUMN on_study INTEGER NOT NULL DEFAULT 0")
    except Exception:
        # column already exists or other harmless error
        pass

    # Ensure total_doses exists on therapies
    try:
        cur.execute("ALTER TABLE therapies ADD COLUMN total_doses INTEGER")
    except Exception:
        # column already exists or other harmless error
        pass

    # --- Indexes ---
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

            # off protocol by default if not present
            on_study_val = rec.get("on_study", False)
            # handle bool/int/str gracefully
            on_study = 1 if bool(on_study_val) else 0

            # upsert regimen
            cur = conn.execute("SELECT id FROM regimens WHERE name = ?", (name,))
            row = cur.fetchone()
            if row:
                reg_id = row["id"]
                conn.execute(
                    "UPDATE regimens "
                    "SET disease_state = ?, notes = ?, on_study = ?, updated_at = ? "
                    "WHERE id = ?",
                    (disease_state, notes, on_study, now, reg_id),
                )
                conn.execute("DELETE FROM therapies WHERE regimen_id = ?", (reg_id,))
            else:
                conn.execute(
                    "INSERT INTO regimens(name, disease_state, notes, on_study, updated_at) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (name, disease_state, notes, on_study, now),
                )
                reg_id = conn.execute(
                    "SELECT id FROM regimens WHERE name = ?",
                    (name,),
                ).fetchone()["id"]

            # insert therapies
            for t in therapies:
                if not isinstance(t, dict):
                    continue

                total_doses = t.get("total_doses")  # may be None for older JSON

                conn.execute(
                    "INSERT INTO therapies("
                    "regimen_id, name, route, dose, frequency, duration, total_doses"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (
                        reg_id,
                        t.get("name", ""),
                        t.get("route", ""),
                        t.get("dose", ""),
                        t.get("frequency", ""),
                        t.get("duration", ""),
                        total_doses,
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
