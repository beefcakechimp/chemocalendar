#!/usr/bin/env python3
"""
regimenbank.py — JSON-backed regimen bank + calendar (TXT and DOCX export)

What you get
- Interactive Regimen Wizard: create/edit regimens; per-agent durations.
- Add agents brand-new OR reuse from existing agents across all regimens.
- Calendar Wizard: pick regimen, enter start date (supports past Day 1), choose "Cycle # or Induction",
  pick cycle length, then print/save (TXT) and optionally export DOCX matching clinic style.
- HIPAA-friendly: DOCX has blanks for Patient Name and DOB.

Requires no external deps unless you export DOCX:
  pip install python-docx
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
    duration: str   # e.g., "7 days" (stored per instance)

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
        # Safe defaults
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
            except Exception:
                # Corrupt: keep defaults
                pass

    def _save(self) -> None:
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

# ---------------- Helpers (dropdown + parsing) ----------------

def choose_from(prompt: str, options: List[str], allow_new: bool = False) -> Tuple[str, bool]:
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
    Parses: "Days 1–7", "Days 1-21", "Days 1,8,15", "Days 1–7, 15"
    """
    s = freq.replace("–", "-").lower().strip()
    m = re.search(r"days\s+(.+)", s)
    if not m:
        return []
    part = m.group(1)
    days: List[int] = []
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
        for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        print("Enter date as YYYY-MM-DD, M/D/YY, M/D/YYYY, 'today', or +N (e.g., +7).")

# ---------- Agent Catalog (reuse from existing) ----------

def build_agent_catalog(bank: RegimenBank) -> Dict[str, List[Chemotherapy]]:
    """
    Collect all agents across all regimens and bucket them by agent name (case-insensitive).
    Returns dict: name_key -> list[Chemotherapy variants]
    """
    catalog: Dict[str, List[Chemotherapy]] = {}
    for rname in bank.list_regimens():
        reg = bank.get_regimen(rname)
        if not reg:
            continue
        for t in reg.therapies:
            key = t.name.strip().lower()
            catalog.setdefault(key, [])
            # Avoid duplicate exact variants
            if not any((v.route == t.route and v.dose == t.dose and v.frequency == t.frequency and v.duration == t.duration)
                       for v in catalog[key]):
                catalog[key].append(t)
    return catalog

def choose_agent_from_catalog(catalog: Dict[str, List[Chemotherapy]]) -> Optional[Chemotherapy]:
    """
    Dropdown to choose agent name, then choose variant if multiple.
    Returns a cloned Chemotherapy or None if catalog empty.
    """
    if not catalog:
        print("No existing agents saved yet.")
        return None
    name_options = sorted(set(k for k in catalog.keys()))
    display = [n.title() for n in name_options]
    choice, _ = choose_from("Choose an existing agent to reuse:", display, allow_new=False)
    key = name_options[display.index(choice)]
    variants = catalog[key]
    if len(variants) == 1:
        v = variants[0]
        print(f"Selected: {v.name} | {v.route} | {v.dose} | {v.frequency} | {v.duration}")
        return Chemotherapy(v.name, v.route, v.dose, v.frequency, v.duration)
    else:
        for i, v in enumerate(variants, 1):
            print(f"  {i}. {v.route} | {v.dose} | {v.frequency} | {v.duration}")
        while True:
            sel = input("Pick a variant by number: ").strip()
            if sel.isdigit() and 1 <= int(sel) <= len(variants):
                v = variants[int(sel) - 1]
                return Chemotherapy(v.name, v.route, v.dose, v.frequency, v.duration)
            print("Invalid selection.")
    return None

# ---------------- Regimen Wizard ----------------

def wizard(bank: RegimenBank) -> None:
    print("\n=== Regimen Wizard ===")
    reg_names = bank.list_regimens()
    reg_name, is_new = choose_from("Select a regimen or add a new one:", reg_names, allow_new=True)
    reg = bank.get_regimen(reg_name) if not is_new else Regimen(name=reg_name)
    reg.disease_state = prompt_optional("Disease state", reg.disease_state)

    if is_new and "ven" in reg_name.lower():
        quick = input("Scaffold AZA/VEN agents now? [y/N]: ").strip().lower() == "y"
        if quick:
            aza = Chemotherapy(
                name="Azacitidine",
                route="IV",
                dose=prompt_required("Azacitidine dose (e.g., 75 mg/m^2)"),
                frequency="Days 1–7",
                duration="7 days",
            )
            ven_dose = prompt_required("Venetoclax dose (e.g., 70 mg / 100 mg / 400 mg)")
            common_durs = ["7", "14", "21", "28"]
            print("\nVenetoclax duration days:")
            for i, d in enumerate(common_durs, 1):
                print(f"  {i}. {d}")
            print("  n. Other")
            while True:
                sel = input("Choose duration number, actual day count (e.g., 21), or 'n': ").strip().lower()
                if sel.isdigit():
                    val = int(sel)
                    if 1 <= val <= 365:
                        ven_days = val; break
                if sel.isdigit() and 1 <= int(sel) <= len(common_durs):
                    ven_days = int(common_durs[int(sel) - 1]); break
                if sel == "n":
                    ven_days = int(prompt_required("Enter Venetoclax duration days (integer)")); break
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

    while True:
        print("\nCurrent therapies:")
        if not reg.therapies:
            print("  (none yet)")
        else:
            for i, t in enumerate(reg.therapies, 1):
                print(f"  {i}. {t.name} | {t.route} | {t.dose} | {t.frequency} | {t.duration}")

        print("\nActions:")
        print("  1. Add a new agent")
        print("  2. Add from existing agents")
        print("  3. Edit an existing agent")
        print("  4. Remove an agent")
        print("  5. Save and finish")
        choice = input("Select action [1-5]: ").strip()

        if choice == "1":
            name = prompt_required("Agent name")
            routes = ["IV", "PO", "SQ", "IM", "IT", "Intra-arterial"]
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
            catalog = build_agent_catalog(bank)
            tmpl = choose_agent_from_catalog(catalog)
            if tmpl:
                print("\nYou can accept as-is or tweak fields.")
                name = prompt_required("Agent name", tmpl.name)
                route = prompt_required("Route", tmpl.route)
                dose = prompt_required("Dose", tmpl.dose)
                freq = prompt_required("Frequency", tmpl.frequency)
                dur  = prompt_required("Duration", tmpl.duration)
                reg.upsert_chemo(Chemotherapy(name, route, dose, freq, dur))

        elif choice == "3":
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

        elif choice == "4":
            if not reg.therapies:
                print("No agents to remove."); continue
            idx = input("Enter agent number to remove: ").strip()
            if idx.isdigit() and 1 <= int(idx) <= len(reg.therapies):
                removed = reg.therapies.pop(int(idx) - 1)
                print(f"Removed {removed.name}.")
            else:
                print("Invalid number.")

        elif choice == "5":
            bank.upsert_regimen(reg)
            print(f"\nSaved regimen '{reg.name}'.")
            return
        else:
            print("Choose 1–5.")

# ---------------- Calendar core ----------------

def compute_calendar_grid(reg: Regimen, start: dt.date, cycle_length: int):
    """
    Returns (first_week_sun, last_week_sat, max_day, grid)
    grid: List[week] where week = List[dict] for 7 days with keys:
      date, cycle_day (int|None), labels (List[str])
    """
    # Map day numbers to agents
    agent_days: Dict[str, List[int]] = {}
    max_day = cycle_length
    for t in reg.therapies:
        days = parse_frequency_days(t.frequency)
        agent_days[t.name] = [d for d in days if 1 <= d <= cycle_length]
        if days:
            max_day = max(max_day, max(days))

    day_labels: Dict[int, List[str]] = {d: [] for d in range(1, max_day + 1)}
    for t in reg.therapies:
        for d in agent_days.get(t.name, []):
            day_labels.setdefault(d, []).append(t.name)

    # Sunday of the start week (past or future ok)
    first_week_sun = start - dt.timedelta(days=(start.weekday() + 1) % 7)
    last_date_needed = start + dt.timedelta(days=max_day - 1)
    # Saturday of the last needed week
    last_week_sat = last_date_needed + dt.timedelta(days=(5 - last_date_needed.weekday()) % 7 + 1)

    # Build grid
    grid: List[List[Dict[str, Any]]] = []
    d = first_week_sun
    week: List[Dict[str, Any]] = []
    while d <= last_week_sat:
        entry: Dict[str, Any] = {"date": d, "cycle_day": None, "labels": []}
        if d >= start:
            cday = (d - start).days + 1
            if 1 <= cday <= max_day:
                entry["cycle_day"] = cday
                entry["labels"] = list(day_labels.get(cday, [])) or ["Rest"]
        week.append(entry)
        if len(week) == 7:
            grid.append(week); week = []
        d += dt.timedelta(days=1)
    if week:
        while len(week) < 7:
            week.append({"date": d, "cycle_day": None, "labels": []})
            d += dt.timedelta(days=1)
        grid.append(week)
    return first_week_sun, last_week_sat, max_day, grid

def make_calendar_text(reg: Regimen, start: dt.date, cycle_length: int, cycle_label: str) -> str:
    first_sun, last_sat, max_day, grid = compute_calendar_grid(reg, start, cycle_length)
    out = []
    months = calendar.month_name[first_sun.month]
    if first_sun.month != last_sat.month or first_sun.year != last_sat.year:
        months += f" - {calendar.month_name[last_sat.month]}"
    title_year = str(first_sun.year) if first_sun.year == last_sat.year else f"{first_sun.year}-{last_sat.year}"
    out.append(f"{reg.name} — {cycle_label}")
    out.append(f"{months} {title_year}")
    out.append("Sun       Mon       Tue       Wed       Thu       Fri       Sat")

    for week in grid:
        col_width = 12
        cell_lines = [ [] for _ in range(7) ]
        max_lines = 0
        for idx, cell in enumerate(week):
            lines = [f"{calendar.month_abbr[cell['date'].month]} {cell['date'].day}"]
            if cell["cycle_day"] is not None:
                lines.append(f"Day {cell['cycle_day']}")
                lines.extend(cell["labels"])
            max_lines = max(max_lines, len(lines))
            cell_lines[idx] = lines
        for row in range(max_lines):
            row_parts = []
            for col in range(7):
                ln = cell_lines[col][row] if row < len(cell_lines[col]) else ""
                row_parts.append(ln.ljust(col_width))
            out.append(" ".join(row_parts))
        out.append("")
    return "\n".join(out)

# ---------------- DOCX export (clinic style) ----------------

def export_calendar_docx(reg: Regimen, start: dt.date, cycle_length: int, out_path: Path, cycle_label: str) -> bool:
    """
    Clinic-style DOCX:
      - Landscape Letter, 0.5" margins
      - Table with:
          Row 1: merged title (3 lines)
          Row 2: merged Name/DOB
          Row 3: weekday header
          Rows 4+: weeks grid
      - Cell formatting per request:
          Date = right, bold
          Day # = left, italic
          Chemo lines = left, bold
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        import calendar as calmod
    except Exception:
        return False

    # Build grid
    first_sun, last_sat, max_day, grid = compute_calendar_grid(reg, start, cycle_length)

    # Month banner (e.g., "October - November 2025" or single month)
    months = calmod.month_name[first_sun.month]
    if first_sun.month != last_sat.month or first_sun.year != last_sat.year:
        months += f" - {calmod.month_name[last_sat.month]}"
    title_year = str(first_sun.year) if first_sun.year == last_sat.year else f"{first_sun.year}-{last_sat.year}"

    # Document + page setup
    doc = Document()
    section = doc.sections[0]
    section.orientation = 1  # landscape
    section.page_width, section.page_height = Inches(11), Inches(8.5)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Inches(0.5)

    # Table: 0 title, 1 name/dob, 2 weekday header, 3.. weeks
    table = doc.add_table(rows=len(grid) + 3, cols=7)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    def merge_row_across(row_idx: int):
        row = table.rows[row_idx]
        first_cell = row.cells[0]
        for j in range(1, 7):
            first_cell.merge(row.cells[j])
        return first_cell

    # Row 0: Title (inside table)
    cell_title = merge_row_across(0)
    p = cell_title.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Chemotherapy Calendar\n"); r.bold = True; r.font.size = Pt(14)
    r2 = p.add_run(f"{reg.name}  - {cycle_label}\n"); r2.font.size = Pt(12)
    r3 = p.add_run(f"{months} {title_year}"); r3.font.size = Pt(12)

    # Row 1: Name/DOB blanks
    cell_pid = merge_row_across(1)
    p = cell_pid.paragraphs[0]
    p.add_run("Patient Name: ").bold = True; p.add_run("__________________________    ")
    p.add_run("DOB: ").bold = True; p.add_run("______________")

    # Row 2: Weekday headers
    hdr = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    for i, text in enumerate(hdr):
        cell = table.cell(2, i)
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(10)

    # Body rows with requested formatting
    body_row_start = 3
    for w_i, week in enumerate(grid):
        for d_i, cell in enumerate(week):
            c = table.cell(body_row_start + w_i, d_i)

            # Reset cell safely
            c.text = ""  # leaves one empty paragraph

            # Date line: right-aligned, bold
            p_date = c.paragraphs[0]
            p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p_date.paragraph_format.space_after = Pt(0)
            r_date = p_date.add_run(f"{calmod.month_abbr[cell['date'].month]} {cell['date'].day}")
            r_date.bold = True
            r_date.font.size = Pt(9)

            # Day + labels if inside the cycle
            if cell["cycle_day"] is not None:
                # Day line: left, italic
                p_day = c.add_paragraph()
                p_day.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_day.paragraph_format.space_after = Pt(0)
                r_day = p_day.add_run(f"Day {cell['cycle_day']}")
                r_day.italic = True
                r_day.font.size = Pt(9)

                # Labels: left, bold for chemo; leave "Rest" unbolded for subtlety
                for lab in cell["labels"]:
                    p_lab = c.add_paragraph()
                    p_lab.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p_lab.paragraph_format.space_after = Pt(0)
                    r_lab = p_lab.add_run(lab)
                    r_lab.font.size = Pt(9)
                    if lab.lower() != "rest":
                        r_lab.bold = True

    # Thin borders for printability
    def set_tbl_borders(tbl):
        tbl_pr = tbl._element.tblPr
        tbl_borders = OxmlElement('w:tblBorders')
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            elem = OxmlElement(f'w:{edge}')
            elem.set(qn('w:val'), 'single')
            elem.set(qn('w:sz'), '4')   # 1/8 pt units
            elem.set(qn('w:space'), '0')
            elem.set(qn('w:color'), 'auto')
            tbl_borders.append(elem)
        tbl_pr.append(tbl_borders)

    set_tbl_borders(table)

    # Footer note (HIPAA reminder)
    doc.add_paragraph().add_run("Note: Add patient identifiers (Name/DOB) after generating this document.").italic = True

    doc.save(out_path)
    return True

    """
    Clinic-style DOCX:
      - Landscape Letter, 0.5" margins
      - Table with:
          Row 1: merged title (3 lines)
          Row 2: merged Name/DOB
          Row 3: weekday header
          Rows 4+: weeks grid
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except Exception:
        return False

    first_sun, last_sat, max_day, grid = compute_calendar_grid(reg, start, cycle_length)

    months = calendar.month_name[first_sun.month]
    if first_sun.month != last_sat.month or first_sun.year != last_sat.year:
        months += f" - {calendar.month_name[last_sat.month]}"
    title_year = str(first_sun.year) if first_sun.year == last_sat.year else f"{first_sun.year}-{last_sat.year}"

    doc = Document()

    # Page setup
    section = doc.sections[0]
    section.orientation = 1  # landscape
    section.page_width, section.page_height = Inches(11), Inches(8.5)
    section.left_margin = section.right_margin = section.top_margin = section.bottom_margin = Inches(0.5)

    # Table structure
    table = doc.add_table(rows=len(grid) + 3, cols=7)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True

    def merge_row_across(row_idx: int):
        row = table.rows[row_idx]
        first_cell = row.cells[0]
        for j in range(1, 7):
            first_cell.merge(row.cells[j])
        return first_cell

    # Row 0: title
    cell_title = merge_row_across(0)
    p = cell_title.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Chemotherapy Calendar\n")
    r.bold = True; r.font.size = Pt(14)
    r2 = p.add_run(f"{reg.name}  - {cycle_label}\n")
    r2.font.size = Pt(12)
    r3 = p.add_run(f"{months} {title_year}")
    r3.font.size = Pt(12)

    # Row 1: Name/DOB blanks
    cell_pid = merge_row_across(1)
    p = cell_pid.paragraphs[0]
    p.add_run("Patient Name: ").bold = True
    p.add_run("__________________________    ")
    p.add_run("DOB: ").bold = True
    p.add_run("______________")

    # Row 2: weekday headers
    hdr = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    for i, text in enumerate(hdr):
        cell = table.cell(2, i)
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(text)
        run.bold = True
        run.font.size = Pt(10)

    # Body rows
    body_row_start = 3
    for w_i, week in enumerate(grid):
        for d_i, cell in enumerate(week):
            c = table.cell(body_row_start + w_i, d_i)
            para = c.paragraphs[0]
            r1 = para.add_run(f"{calendar.month_abbr[cell['date'].month]} {cell['date'].day}\n")
            r1.bold = True
            r1.font.size = Pt(9)
            if cell["cycle_day"] is not None:
                r2 = para.add_run(f"Day {cell['cycle_day']}\n")
                r2.font.size = Pt(9)
                if cell["labels"]:
                    for lab in cell["labels"]:
                        para.add_run(f"{lab}\n").font.size = Pt(9)

    # Thin borders for printability
    def set_tbl_borders(tbl):
        tbl_pr = tbl._element.tblPr
        tbl_borders = OxmlElement('w:tblBorders')
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            elem = OxmlElement(f'w:{edge}')
            elem.set(qn('w:val'), 'single')
            elem.set(qn('w:sz'), '4')
            elem.set(qn('w:space'), '0')
            elem.set(qn('w:color'), 'auto')
            tbl_borders.append(elem)
        tbl_pr.append(tbl_borders)

    set_tbl_borders(table)

    # Footer note
    doc.add_paragraph()
    note = doc.add_paragraph()
    note_run = note.add_run("Note: Add patient identifiers (Name/DOB) after generating this document.")
    note_run.italic = True
    note_run.font.size = Pt(8)

    doc.save(out_path)
    return True

# ---------------- Calendar wizard ----------------

def choose_cycle_or_induction() -> str:
    """
    Restrict choices to 'Cycle #' or 'Induction'.
    - If user selects Cycle, prompt for a positive integer and return 'Cycle N'.
    - If user selects Induction, return 'Induction'.
    """
    print("\nChoose phase label:")
    print("  1. Cycle #")
    print("  2. Induction")
    while True:
        sel = input("Select [1-2]: ").strip()
        if sel == "1":
            while True:
                n = input("Enter cycle number (e.g., 1, 2, 3): ").strip()
                if n.isdigit() and int(n) >= 1:
                    return f"Cycle {int(n)}"
                print("Please enter a positive integer.")
        if sel == "2":
            return "Induction"
        print("Please choose 1 or 2.")

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

    # Day 1 can be past or future
    start = read_date("Cycle start date", default=dt.date.today())

    # Cycle length
    while True:
        s = input("Cycle length in days [28]: ").strip()
        if not s:
            cycle_len = 28
            break
        if s.isdigit() and int(s) >= 1:
            cycle_len = int(s)
            break
        print("Enter a positive integer.")

    # Strict selector: Cycle # or Induction
    cycle_label = choose_cycle_or_induction()

    # 1) Print text calendar
    cal_txt = make_calendar_text(reg, start, cycle_len, cycle_label)
    print("\n" + cal_txt + "\n")

    # 2) Save options
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in reg.name)
    default_txt = f"{safe_name}_{cycle_label.replace(' ', '').lower()}_{start.isoformat()}.txt"
    default_docx = f"{safe_name}_{cycle_label.replace(' ', '').lower()}_{start.isoformat()}.docx"

    if input(f"Save text file [{default_txt}]? [Y/n]: ").strip().lower() != "n":
        Path(default_txt).write_text(cal_txt, encoding="utf-8")
        print(f"Saved: {default_txt}")

    want_docx = input(f"Export DOCX [{default_docx}]? [y/N]: ").strip().lower()
    if want_docx == "y":
        ok = export_calendar_docx(reg, start, cycle_len, Path(default_docx), cycle_label)
        if ok:
            print(f"Saved: {default_docx}")
            print("Reminder: fill Patient Name and DOB in the document.")
        else:
            print("python-docx is not installed. In your Codespace run:  pip install python-docx")
            print("Then re-run: python regimenbank.py calendar")

# ---------------- CLI ----------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JSON-backed chemotherapy regimen bank with calendar export")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to JSON DB (default: regimenbank.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("wizard", help="Interactive guided flow: select/add regimen and agents")
    sub.add_parser("calendar", help="Interactive calendar flow (TXT/DOCX export)")
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
        print(f"  {i}. {t.name} | {t.route} | {t.dose} | "
              f"Freq: {t.frequency} | Duration: {t.duration}")
    print("")

def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    bank = RegimenBank(args.db)

    if args.cmd == "wizard":
        wizard(bank); return 0
    if args.cmd == "calendar":
        calendar_wizard(bank); return 0
    if args.cmd == "list":
        names = bank.list_regimens()
        print("(no regimens)" if not names else "\n".join(names))
        return 0
    if args.cmd == "show":
        reg = bank.get_regimen(args.name)
        if not reg:
            print(f"Regimen '{args.name}' not found."); return 1
        pretty_print_regimen(reg); return 0
    if args.cmd == "delete-regimen":
        ok = bank.delete_regimen(args.name)
        print("Deleted." if ok else f"Regimen '{args.name}' not found.")
        return 0 if ok else 1

    print("Unknown command."); return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
