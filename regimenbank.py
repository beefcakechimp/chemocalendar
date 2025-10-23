#!/usr/bin/env python3
"""
regimenbank.py — JSON-backed chemotherapy regimen bank with variants + calendar (no deps).

Features
- Robust JSON storage in regimenbank.json (atomic writes; auto-fix keys).
- Interactive Regimen Wizard: pick/add regimen, add/edit agents (per-instance durations).
- Calendar Wizard: pick regimen, enter start date (many formats), cycle length, print/save week-grid.
- Flexible date parser: YYYY-MM-DD, M/D/YY, M/D/YYYY, 'today'/'t', '+N'.
- Venetoclax duration accepts index or actual number of days.

Usage (in Codespace terminal):
  python regimenbank.py wizard     # Part 1: manage regimens/agents via dropdowns
  python regimenbank.py calendar   # Part 2: make calendar via dropdown + prompts
  python regimenbank.py list
  python regimenbank.py show --name "AZA/VEN 70 mg"
  python regimenbank.py delete-regimen --name "AZA/VEN 70 mg"
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import argparse
import calendar
import datetime as dt
import json
import sys
import tempfile
import time
import re

SCHEMA_VERSION = 2
DEFAULT_DB = Path("regimenbank.json")

# ---------------- Models ----------------

@dataclass
class Chemotherapy:
    name: str
    route: str
    dose: str
    frequency: str  # e.g., "Days 1–7", "Days 1-21", "Days 1,8,15"
    duration: str   # free text like "7 days", "21 days" (stored per instance)

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
    name: str                    # e.g., "AZA/VEN 70 mg"
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
        key = chemo.name.strip().lower()
        for i, existing in enumerate(self.therapies):
            if existing.name.strip().lower() == key:
                self.therapies[i] = chemo
                return
        self.therapies.append(chemo)

    def remove_chemo(self, chemo_name: str) -> bool:
        key = chemo_name.strip().lower()
        before = len(self.therapies)
        self.therapies = [c for c in self.therapies if c.name.strip().lower() != key]
        return len(self.therapies) != before

# ---------------- Storage ----------------

class RegimenBank:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        # Start with a safe default structure
        self.data = {"_meta": {"version": SCHEMA_VERSION, "updated_at": None}, "regimens": {}}
        if self.db_path.exists():
            try:
                with self.db_path.open("r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    if "_meta" not in raw or not isinstance(raw["_meta"], dict):
                        raw["_meta"] = {"version": SCHEMA_VERSION, "updated_at": None}
                    if "regimens" not in raw or not isinstance(raw["regimens"], dict):
                        raw["regimens"] = {}
                    self.data = raw
                # else: keep defaults
            except Exception:
                # Corrupt/unreadable: keep defaults, don't crash
                pass

    def _save(self) -> None:
        # Ensure keys exist before write (idempotent)
        if "_meta" not in self.data or not isinstance(self.data["_meta"], dict):
            self.data["_meta"] = {"version": SCHEMA_VERSION, "updated_at": None}
        if "regimens" not in self.data or not isinstance(self.data["regimens"], dict):
            self.data["regimens"] = {}

        self.data["_meta"]["version"] = SCHEMA_VERSION
        self.data["_meta"]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        tmp_dir = self.db_path.parent if self.db_path.parent.exists() else Path(".")
        with tempfile.NamedTemporaryFile("w", delete=False, dir=tmp_dir, suffix=".tmp", encoding="utf-8") as tf:
            json.dump(self.data, tf, indent=2, ensure_ascii=False)
            tf.flush()
            tmp_name = tf.name
        Path(tmp_name).replace(self.db_path)

    # Regimen ops
    def list_regimens(self) -> List[str]:
        return sorted(self.data.get("regimens", {}).keys())

    def get_regimen(self, name: str) -> Optional[Regimen]:
        rec = self.data.get("regimens", {}).get(name.strip())
        return Regimen.from_dict(name.strip(), rec) if rec else None

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

# ---------------- Helpers (dropdown-like + parsing) ----------------

def choose_from(prompt: str, options: List[str], allow_new: bool = False) -> Tuple[str, bool]:
    """
    Present a numbered list. Returns (value, is_new).
    If allow_new=True, user may type 'n' to add a new name.
    """
    print(f"\n{prompt}")
    if not options:
        if allow_new:
            val = input("No options yet. Enter a new name: ").strip()
            return val, True
        raise SystemExit("No options available.")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    if allow_new:
        print("  n. <Add new>")
    while True:
        sel = input("Choose number" + (" or 'n' to add new: " if allow_new else ": ")).strip()
        if allow_new and sel.lower() == "n":
            val = input("Enter new name: ").strip()
            if val:
                return val, True
        if sel.isdigit():
            idx = int(sel)
            if 1 <= idx <= len(options):
                return options[idx - 1], False
        print("Invalid selection. Try again.")

def prompt_required(label: str, prefill: Optional[str] = None) -> str:
    while True:
        v = input(f"{label}{f' [{prefill}]' if prefill else ''}: ").strip()
        if not v and prefill:
            return prefill
        if v:
            return v
        print("Required. Please enter a value.")

def prompt_optional(label: str, prefill: Optional[str] = None) -> Optional[str]:
    v = input(f"{label}{f' [{prefill}]' if prefill else ''} (optional): ").strip()
    return v or prefill

def parse_frequency_days(freq: str) -> List[int]:
    """
    Parse simple patterns like:
      "Days 1–7", "Days 1-21", "Days 1,8,15", "Days 1–7, 15"
    Returns sorted unique day numbers.
    """
    s = freq.replace("–", "-")
    s = s.lower().strip()
    m = re.search(r"days\s+(.+)", s)
    if not m:
        return []
    part = m.group(1)
    days: List[int] = []
    # support tokens like "1-7", "1", "8", "15", with commas/spaces
    for token in re.split(r"[,\s]+", part):
        if not token:
            continue
        if "-" in token:
            try:
                a, b = token.split("-", 1)
                a, b = int(a), int(b)
                if a <= b:
                    days.extend(range(a, b + 1))
            except ValueError:
                continue
        else:
            try:
                days.append(int(token))
            except ValueError:
                continue
    # unique + sorted
    return sorted(set(days))

def read_date(prompt: str, default: Optional[dt.date] = None) -> dt.date:
    """
    Accepts:
      YYYY-MM-DD
      M/D/YY or M/D/YYYY  (e.g., 10/23/25 or 1/1/2025)
      'today' or 't'
      '+N'  → N days from today
    """
    while True:
        hint = f" [{default.strftime('%m/%d/%y')}]" if default else ""
        s = input(f"{prompt}{hint}: ").strip().lower()
        if not s and default:
            return default
        if s in ("t", "today"):
            return dt.date.today()
        if s.startswith("+") and s[1:].isdigit():
            return dt.date.today() + dt.timedelta(days=int(s[1:]))

        # Try multiple date patterns
        for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        print("Enter date as YYYY-MM-DD, M/D/YY, M/D/YYYY, 'today', or +N (e.g., +7).")

# ---------------- Regimen Wizard (Part 1) ----------------

def wizard(bank: RegimenBank) -> None:
    print("\n=== Regimen Wizard ===")
    # Choose or create regimen (variant names encouraged)
    reg_names = bank.list_regimens()
    reg_name, is_new = choose_from("Select a regimen or add a new one:", reg_names, allow_new=True)
    reg = bank.get_regimen(reg_name) if not is_new else Regimen(name=reg_name)

    # Optional disease state
    reg.disease_state = prompt_optional("Disease state", reg.disease_state)

    # If user picked a new AZA/VEN variant, optionally scaffold common agents
    if is_new and "ven" in reg_name.lower():
        quick = input("Scaffold AZA/VEN agents now? [y/N]: ").strip().lower() == "y"
        if quick:
            # Azacitidine (you can edit later)
            aza = Chemotherapy(
                name="Azacitidine",
                route="IV",
                dose=prompt_required("Azacitidine dose (e.g., 75 mg/m^2)"),
                frequency="Days 1–7",
                duration="7 days",
            )
            # Venetoclax: dose + duration per instance
            ven_dose = prompt_required("Venetoclax dose (e.g., 70 mg / 100 mg / 400 mg)")

            # Offer common durations like a dropdown, but accept actual day count too
            common_durs = ["7", "14", "18", "21", "28"]
            print("\nVenetoclax duration days:")
            for i, d in enumerate(common_durs, 1):
                print(f"  {i}. {d}")
            print("  n. Other")

            while True:
                sel = input("Choose duration number, actual day count (e.g., 21), or 'n': ").strip().lower()
                # Accept numeric day count directly
                if sel.isdigit():
                    val = int(sel)
                    if 1 <= val <= 365:
                        ven_days = val
                        break
                # Accept menu index
                if sel.isdigit() and 1 <= int(sel) <= len(common_durs):
                    ven_days = int(common_durs[int(sel) - 1])
                    break
                if sel == "n":
                    ven_days = int(prompt_required("Enter Venetoclax duration days (integer)"))
                    break
                print("Invalid selection.")

            ven = Chemotherapy(
                name="Venetoclax",
                route="PO",
                dose=ven_dose,
                frequency=f"Days 1–{ven_days}",
                duration=f"{ven_days} days",
            )
            reg.upsert_chemo(aza)
            reg.upsert_chemo(ven)

    # General edit loop
    while True:
        print("\nCurrent therapies:")
        if not reg.therapies:
            print("  (none yet)")
        else:
            for i, t in enumerate(reg.therapies, 1):
                print(f"  {i}. {t.name} | {t.route} | {t.dose} | {t.frequency} | {t.duration}")

        print("\nActions:")
        print("  1. Add a new agent")
        print("  2. Edit an existing agent")
        print("  3. Remove an agent")
        print("  4. Save and finish")
        choice = input("Select action [1-4]: ").strip()

        if choice == "1":
            name = prompt_required("Agent name")
            # route dropdown
            routes = ["IV", "PO", "SC", "IM", "IT", "IP", "Intra-arterial"]
            print("\nRoute options:")
            for i, r in enumerate(routes, 1):
                print(f"  {i}. {r}")
            print("  n. Other")
            while True:
                rs = input("Choose route or 'n': ").strip().lower()
                if rs.isdigit() and 1 <= int(rs) <= len(routes):
                    route = routes[int(rs) - 1]; break
                if rs == "n":
                    route = prompt_required("Route"); break
                print("Invalid selection.")
            dose = prompt_required("Dose (e.g., 75 mg/m^2)")
            freq = prompt_required("Frequency (e.g., Days 1–7 or Days 1,8,15)")
            dur  = prompt_required("Duration (e.g., 7 days)")
            reg.upsert_chemo(Chemotherapy(name, route, dose, freq, dur))

        elif choice == "2":
            if not reg.therapies:
                print("No agents to edit."); continue
            idx = input("Enter agent number to edit: ").strip()
            if not (idx.isdigit() and 1 <= int(idx) <= len(reg.therapies)):
                print("Invalid number."); continue
            i = int(idx) - 1
            t = reg.therapies[i]
            t.name = prompt_required("Agent name", t.name)
            t.route = prompt_required("Route", t.route)
            t.dose = prompt_required("Dose", t.dose)
            t.frequency = prompt_required("Frequency", t.frequency)
            t.duration = prompt_required("Duration", t.duration)
            reg.therapies[i] = t

        elif choice == "3":
            if not reg.therapies:
                print("No agents to remove."); continue
            idx = input("Enter agent number to remove: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(reg.therapies):
                removed = reg.therapies.pop(int(idx) - 1)
                print(f"Removed {removed.name}.")
            else:
                print("Invalid number.")

        elif choice == "4":
            # Save and exit
            bank.upsert_regimen(reg)
            print(f"\nSaved regimen '{reg.name}'.")
            return
        else:
            print("Choose 1–4.")

# ---------------- Calendar (Part 2) ----------------

def make_calendar(reg: Regimen, start: dt.date, cycle_length: int) -> str:
    """
    Returns a string calendar laid out in weeks (Sun–Sat),
    starting on the week of 'start' date, covering 'cycle_length' (or max needed) days.
    """
    # Compute dosing map by day number for each agent
    agent_days: Dict[str, List[int]] = {}
    max_day = cycle_length
    for t in reg.therapies:
        days = parse_frequency_days(t.frequency)
        agent_days[t.name] = [d for d in days if 1 <= d <= cycle_length]
        if days:
            max_day = max(max_day, max(days))

    # Build a day->labels mapping
    day_labels: Dict[int, List[str]] = {d: [] for d in range(1, max_day + 1)}
    for t in reg.therapies:
        for d in agent_days.get(t.name, []):
            day_labels.setdefault(d, []).append(t.name)

    # Sunday of the week containing 'start'
    first_week_sun = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    last_date_needed = start + dt.timedelta(days=max_day - 1)
    # Saturday of the last needed week
    last_week_sat = last_date_needed + dt.timedelta(days=(5 - last_date_needed.weekday()) % 7 + 1)

    # Build rows week by week
    out = []
    months = calendar.month_name[first_week_sun.month]
    if first_week_sun.month != last_week_sat.month or first_week_sun.year != last_week_sat.year:
        months += f" - {calendar.month_name[last_week_sat.month]}"
    title_year = str(first_week_sun.year) if first_week_sun.year == last_week_sat.year else f"{first_week_sun.year}-{last_week_sat.year}"
    out.append(f"{reg.name} — Cycle 1")
    out.append(f"{months} {title_year}")
    out.append("Sun       Mon       Tue       Wed       Thu       Fri       Sat")

    d = first_week_sun
    while d <= last_week_sat:
        week_cells: List[str] = []
        for _ in range(7):
            cell_lines = []
            # Calendar date
            cell_lines.append(f"{calendar.month_abbr[d.month]} {d.day}")
            # Cycle day
            if d >= start:
                cycle_day = (d - start).days + 1
                if 1 <= cycle_day <= max_day:
                    cell_lines.append(f"Day {cycle_day}")
                    if day_labels.get(cycle_day):
                        for agent in day_labels[cycle_day]:
                            cell_lines.append(agent)
                    else:
                        cell_lines.append("Rest")
            cell = "\n".join(cell_lines)
            week_cells.append(cell)
            d += dt.timedelta(days=1)
        # format fixed-width columns (rough)
        col_width = 10
        block_lines = []
        max_lines = max(cell.count("\n") + 1 for cell in week_cells)
        for row_idx in range(max_lines):
            row_parts = []
            for cell in week_cells:
                parts = cell.split("\n")
                row_parts.append((parts[row_idx] if row_idx < len(parts) else "").ljust(col_width))
            block_lines.append(" ".join(row_parts))
        out.extend(block_lines)
        out.append("")  # spacer between weeks
    return "\n".join(out)

def calendar_wizard(bank: RegimenBank) -> None:
    names = bank.list_regimens()
    if not names:
        print("No regimens saved yet. Launching Regimen Wizard...")
        wizard(bank)
        names = bank.list_regimens()
        if not names:
            print("No regimens created. Exiting.")
            return
    reg_name, _ = choose_from("Select a regimen to make a calendar for:", names, allow_new=False)
    reg = bank.get_regimen(reg_name)
    if not reg:
        print(f"Regimen '{reg_name}' not found.")
        return

    start = read_date("Cycle start date", default=dt.date.today())
    while True:
        s = input("Cycle length in days [28]: ").strip()
        if not s:
            cycle_len = 28
            break
        if s.isdigit() and int(s) >= 1:
            cycle_len = int(s)
            break
        print("Enter a positive integer.")

    cal_txt = make_calendar(reg, start, cycle_len)
    print("\n" + cal_txt + "\n")

    want = input("Save to file? [y/N]: ").strip().lower()
    if want == "y":
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in reg.name)
        out = f"{safe_name}_cycle1_{start.isoformat()}.txt"
        Path(out).write_text(cal_txt, encoding="utf-8")
        print(f"Saved: {out}")

# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JSON-backed chemotherapy regimen bank with variants + calendar")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to JSON DB (default: regimenbank.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("wizard", help="Interactive guided flow: select/add regimen and agents")
    sub.add_parser("calendar", help="Interactive calendar flow (no flags)")
    sub.add_parser("list", help="List regimen names")

    sp = sub.add_parser("show", help="Show a regimen")
    sp.add_argument("--name", required=True)

    sp = sub.add_parser("delete-regimen", help="Delete a regimen")
    sp.add_argument("--name", required=True)

    return p

def pretty_print_regimen(reg: Regimen) -> None:
    print(f"\nRegimen: {reg.name}")
    if reg.disease_state:
        print(f"Disease State: {reg.disease_state}")
    if not reg.therapies:
        print("Therapies: (none)")
        return
    print("Therapies:")
    for i, t in enumerate(reg.therapies, 1):
        print(f"  {i}. {t.name} | Route: {t.route} | Dose: {t.dose} | "
              f"Freq: {t.frequency} | Duration: {t.duration}")
    print("")

def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    bank = RegimenBank(args.db)

    if args.cmd == "wizard":
        wizard(bank)
        return 0

    if args.cmd == "calendar":
        calendar_wizard(bank)
        return 0

    if args.cmd == "list":
        names = bank.list_regimens()
        print("(no regimens)" if not names else "\n".join(names))
        return 0

    if args.cmd == "show":
        reg = bank.get_regimen(args.name)
        if not reg:
            print(f"Regimen '{args.name}' not found.")
            return 1
        pretty_print_regimen(reg)
        return 0

    if args.cmd == "delete-regimen":
        ok = bank.delete_regimen(args.name)
        print("Deleted." if ok else f"Regimen '{args.name}' not found.")
        return 0 if ok else 1

    print("Unknown command.")
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
