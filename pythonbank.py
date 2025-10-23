#!/usr/bin/env python3
"""
regimenbank.py — minimal, efficient JSON-backed library for chemotherapy regimens.

- Stores data in regimenbank.json (or a custom path via --db).
- Defines Chemotherapy and Regimen classes (dataclasses).
- CRUD via simple CLI subcommands with optional interactive prompts.
- Atomic writes, schema-versioned JSON, no external dependencies.

Examples:
  # Create a regimen (prompts for missing fields)
  python regimenbank.py add-regimen --name "AZA-VEN" --disease "AML"

  # Add chemotherapy items
  python regimenbank.py add-chemo --regimen "AZA-VEN" \
      --name "Azacitidine" --route "IV" --dose "75 mg/m^2" \
      --frequency "Days 1–7 q28d" --duration "7 days"

  python regimenbank.py add-chemo --regimen "AZA-VEN" \
      --name "Venetoclax" --route "PO" --dose "400 mg" \
      --frequency "Days 1–28 q28d" --duration "28 days"

  # Show, list, update, remove
  python regimenbank.py show --name "AZA-VEN"
  python regimenbank.py list
  python regimenbank.py update-chemo --regimen "AZA-VEN" --chemo "Venetoclax" --dose "200 mg"
  python regimenbank.py remove-chemo --regimen "AZA-VEN" --chemo "Azacitidine"
  python regimenbank.py delete-regimen --name "AZA-VEN"
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List
import argparse
import json
import sys
import tempfile
import time


SCHEMA_VERSION = 1
DEFAULT_DB = Path("regimenbank.json")


# -------- Data Models --------

@dataclass
class Chemotherapy:
    name: str
    route: str
    dose: str
    frequency: str
    duration: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Chemotherapy":
        return Chemotherapy(
            name=d["name"],
            route=d["route"],
            dose=d["dose"],
            frequency=d["frequency"],
            duration=d["duration"],
        )


@dataclass
class Regimen:
    name: str
    disease_state: Optional[str] = None
    therapies: List[Chemotherapy] = field(default_factory=list)

    @staticmethod
    def from_dict(name: str, d: Dict[str, Any]) -> "Regimen":
        therapies = [Chemotherapy.from_dict(x) for x in d.get("therapies", [])]
        return Regimen(name=name, disease_state=d.get("disease_state"), therapies=therapies)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "disease_state": self.disease_state,
            "therapies": [asdict(t) for t in self.therapies],
        }

    def upsert_chemo(self, chemo: Chemotherapy) -> None:
        for i, existing in enumerate(self.therapies):
            if existing.name.strip().lower() == chemo.name.strip().lower():
                self.therapies[i] = chemo
                return
        self.therapies.append(chemo)

    def remove_chemo(self, chemo_name: str) -> bool:
        key = chemo_name.strip().lower()
        before = len(self.therapies)
        self.therapies = [c for c in self.therapies if c.name.strip().lower() != key]
        return len(self.therapies) != before


# -------- Storage Layer --------

class RegimenBank:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.data = {"_meta": {"version": SCHEMA_VERSION, "updated_at": None}, "regimens": {}}
        self._load()

    def _load(self) -> None:
        if self.db_path.exists():
            try:
                with self.db_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Light schema handling
                if not isinstance(raw, dict) or "regimens" not in raw:
                    raise ValueError("Invalid regimenbank file structure.")
                self.data = raw
            except Exception as exc:
                sys.exit(f"Failed to read {self.db_path}: {exc}")

    def _save(self) -> None:
        self.data["_meta"]["version"] = SCHEMA_VERSION
        self.data["_meta"]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        tmp_dir = self.db_path.parent if self.db_path.parent.exists() else Path(".")
        with tempfile.NamedTemporaryFile("w", delete=False, dir=tmp_dir, suffix=".tmp", encoding="utf-8") as tf:
            json.dump(self.data, tf, indent=2, ensure_ascii=False)
            tf.flush()
            tmp_name = tf.name
        Path(tmp_name).replace(self.db_path)

    # ---- CRUD for regimens ----

    def list_regimens(self) -> List[str]:
        return sorted(self.data.get("regimens", {}).keys())

    def get_regimen(self, name: str) -> Optional[Regimen]:
        key = name.strip()
        rec = self.data.get("regimens", {}).get(key)
        if not rec:
            return None
        return Regimen.from_dict(key, rec)

    def upsert_regimen(self, regimen: Regimen) -> None:
        self.data.setdefault("regimens", {})[regimen.name] = regimen.to_dict()
        self._save()

    def delete_regimen(self, name: str) -> bool:
        key = name.strip()
        if key in self.data.get("regimens", {}):
            del self.data["regimens"][key]
            self._save()
            return True
        return False

    # ---- Chemotherapy item ops ----

    def add_or_update_chemo(self, regimen_name: str, chemo: Chemotherapy) -> None:
        reg = self.get_regimen(regimen_name)
        if not reg:
            # Create regimen on the fly if it doesn't exist
            reg = Regimen(name=regimen_name)
        reg.upsert_chemo(chemo)
        self.upsert_regimen(reg)

    def remove_chemo(self, regimen_name: str, chemo_name: str) -> bool:
        reg = self.get_regimen(regimen_name)
        if not reg:
            return False
        changed = reg.remove_chemo(chemo_name)
        if changed:
            self.upsert_regimen(reg)
        return changed


# -------- Utilities --------

def prompt_if_missing(value: Optional[str], prompt_text: str, required: bool = True) -> str:
    if value:
        return value
    while True:
        v = input(f"{prompt_text}: ").strip()
        if v or not required:
            return v


def pretty_print_regimen(reg: Regimen) -> None:
    print(f"\nRegimen: {reg.name}")
    if reg.disease_state:
        print(f"Disease State: {reg.disease_state}")
    if not reg.therapies:
        print("Therapies: (none)")
        return
    print("Therapies:")
    for i, t in enumerate(reg.therapies, 1):
        print(f"  {i}. {t.name} | Route: {t.route} | Dose: {t.dose} | Freq: {t.frequency} | Duration: {t.duration}")
    print("")


# -------- CLI --------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JSON-backed chemotherapy regimen bank")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to regimenbank JSON file (default: regimenbank.json)")

    sub = p.add_subparsers(dest="cmd", required=True)

    # list
    sub.add_parser("list", help="List regimen names")

    # show
    sp = sub.add_parser("show", help="Show a regimen")
    sp.add_argument("--name", required=True, help="Regimen name")

    # add-regimen
    sp = sub.add_parser("add-regimen", help="Create or update a regimen (no therapies added by default)")
    sp.add_argument("--name", help="Regimen name (required)")
    sp.add_argument("--disease", help="Disease state (optional)")

    # delete-regimen
    sp = sub.add_parser("delete-regimen", help="Delete a regimen")
    sp.add_argument("--name", required=True, help="Regimen name")

    # add-chemo (creates regimen on the fly if needed)
    sp = sub.add_parser("add-chemo", help="Add or update a chemotherapy item inside a regimen")
    sp.add_argument("--regimen", help="Regimen name (required)")
    sp.add_argument("--name", help="Chemotherapy name (required)")
    sp.add_argument("--route", help="Route")
    sp.add_argument("--dose", help="Dose")
    sp.add_argument("--frequency", help="Frequency")
    sp.add_argument("--duration", help="Duration")

    # update-chemo (same as add-chemo but makes intent explicit)
    sp = sub.add_parser("update-chemo", help="Update fields of an existing chemotherapy item (or add if missing)")
    sp.add_argument("--regimen", help="Regimen name (required)")
    sp.add_argument("--chemo", help="Existing chemotherapy name (required)")
    sp.add_argument("--name", help="New chemotherapy name (optional, to rename)")
    sp.add_argument("--route", help="Route")
    sp.add_argument("--dose", help="Dose")
    sp.add_argument("--frequency", help="Frequency")
    sp.add_argument("--duration", help="Duration")

    # remove-chemo
    sp = sub.add_parser("remove-chemo", help="Remove a chemotherapy item from a regimen")
    sp.add_argument("--regimen", required=True, help="Regimen name")
    sp.add_argument("--chemo", required=True, help="Chemotherapy name to remove")

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    bank = RegimenBank(args.db)

    if args.cmd == "list":
        names = bank.list_regimens()
        if not names:
            print("(no regimens)")
        else:
            print("\n".join(names))
        return 0

    if args.cmd == "show":
        reg = bank.get_regimen(args.name)
        if not reg:
            print(f"Regimen '{args.name}' not found.")
            return 1
        pretty_print_regimen(reg)
        return 0

    if args.cmd == "add-regimen":
        name = prompt_if_missing(args.name, "Regimen name", required=True)
        disease = args.disease if args.disease is not None else prompt_if_missing(None, "Disease state (optional)", required=False)
        reg = bank.get_regimen(name) or Regimen(name=name)
        if disease:
            reg.disease_state = disease
        bank.upsert_regimen(reg)
        print(f"Saved regimen '{name}'.")
        return 0

    if args.cmd == "delete-regimen":
        ok = bank.delete_regimen(args.name)
        print("Deleted." if ok else f"Regimen '{args.name}' not found.")
        return 0 if ok else 1

    if args.cmd == "add-chemo":
        regimen_name = prompt_if_missing(args.regimen, "Regimen name", required=True)
        cname = prompt_if_missing(args.name, "Chemotherapy name", required=True)
        route = prompt_if_missing(args.route, "Route", required=True)
        dose = prompt_if_missing(args.dose, "Dose", required=True)
        freq = prompt_if_missing(args.frequency, "Frequency", required=True)
        dur = prompt_if_missing(args.duration, "Duration", required=True)

        bank.add_or_update_chemo(regimen_name, Chemotherapy(cname, route, dose, freq, dur))
        print(f"Added/updated chemo '{cname}' in regimen '{regimen_name}'.")
        return 0

    if args.cmd == "update-chemo":
        regimen_name = prompt_if_missing(args.regimen, "Regimen name", required=True)
        existing_name = prompt_if_missing(args.chemo, "Existing chemotherapy name", required=True)

        reg = bank.get_regimen(regimen_name)
        if not reg:
            print(f"Regimen '{regimen_name}' not found (use add-chemo to create on the fly).")
            return 1

        # Find existing chemo
        target = None
        for c in reg.therapies:
            if c.name.strip().lower() == existing_name.strip().lower():
                target = c
                break
        if not target:
            print(f"Chemotherapy '{existing_name}' not found in '{regimen_name}' (use add-chemo to create).")
            return 1

        # Apply updates with prompts for any explicitly provided empty-but-required fields
        new_name = args.name or target.name
        route = args.route or target.route
        dose = args.dose or target.dose
        freq = args.frequency or target.frequency
        dur = args.duration or target.duration

        updated = Chemotherapy(new_name, route, dose, freq, dur)
        reg.upsert_chemo(updated)
        bank.upsert_regimen(reg)
        print(f"Updated chemotherapy '{existing_name}' in regimen '{regimen_name}'.")
        return 0

    if args.cmd == "remove-chemo":
        ok = bank.remove_chemo(args.regimen, args.chemo)
        print("Removed." if ok else f"Chemotherapy '{args.chemo}' not found in regimen '{args.regimen}'.")
        return 0 if ok else 1

    print("Unknown command.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
