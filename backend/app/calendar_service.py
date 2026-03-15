from __future__ import annotations

import calendar as pycal
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

from backend.app.regimenbank import Regimen, compute_calendar_grid


def _format_month_year_range(first_sun: dt.date, last_sat: dt.date) -> str:
    fm = pycal.month_name[first_sun.month]
    lm = pycal.month_name[last_sat.month]

    if first_sun.year == last_sat.year and first_sun.month == last_sat.month:
        return f"{fm} {first_sun.year}"
    if first_sun.year == last_sat.year:
        return f"{fm} – {lm} {first_sun.year}"
    return f"{fm} {first_sun.year} – {lm} {last_sat.year}"


def _cycle_label_from_inputs(phase: str, cycle_num: Optional[int]) -> str:
    if phase == "Induction":
        return "Induction"
    if cycle_num is None:
        return "Cycle 1"
    return f"Cycle {cycle_num}"


def build_preview(
    reg: Regimen,
    start: dt.date,
    cycle_len: int,
    phase: str,
    cycle_num: Optional[int],
    title_override: Optional[str],
) -> Tuple[str, str, Regimen, dt.date, dt.date, List[List[Dict[str, Any]]]]:
    label = _cycle_label_from_inputs(phase, cycle_num)
    cal_title = (title_override or reg.name).strip() or reg.name

    reg_for_preview = Regimen(
        name=cal_title,
        disease_state=reg.disease_state,
        on_study=reg.on_study,
        notes=reg.notes,
        therapies=reg.therapies,
    )

    first_sun, last_sat, _, grid = compute_calendar_grid(reg_for_preview, start, cycle_len)
    header = _format_month_year_range(first_sun, last_sat)

    # Convert grid dates to ISO strings for frontend
    out_grid: List[List[Dict[str, Any]]] = []
    for week in grid:
        w2: List[Dict[str, Any]] = []
        for cell in week:
            w2.append(
                {
                    "date": cell["date"].isoformat(),
                    "cycle_day": cell["cycle_day"],
                    "labels": cell["labels"] or [],
                }
            )
        out_grid.append(w2)

    return header, label, reg_for_preview, first_sun, last_sat, out_grid