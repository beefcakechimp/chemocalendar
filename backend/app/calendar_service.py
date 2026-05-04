"""
calendar_service.py — Calendar preview generator.
"""
import datetime as dt
from typing import List, Optional, Tuple

from .regimenbank import Regimen, parse_day_spec

def build_preview(
    reg: Regimen,
    start: dt.date,
    cycle_len: int,
    phase: str,
    cycle_num: Optional[int] = None,
    title_override: Optional[str] = None
) -> Tuple[str, str, Regimen, dt.date, dt.date, List[List[dict]]]:
    
    # 1. Labels and Titles
    if phase == "Induction":
        label = "Induction"
    else:
        label = f"Cycle {cycle_num or 1}"
        
    doc_title = (title_override or reg.name).strip() or reg.name
    
    # 2. Map therapies to days
    day_map = {}
    for t in reg.therapies:
        active_days = parse_day_spec(t.duration)
        for d in active_days:
            if d not in day_map:
                day_map[d] = []
            day_map[d].append(t.name)
    
    # 3. Grid Bounds (Expand to full Sun-Sat weeks)
    end_date = start + dt.timedelta(days=cycle_len - 1)
    first_sun = start - dt.timedelta(days=start.isoweekday() % 7)
    
    # 4. Build the Grid
    grid = []
    curr_date = first_sun
    
    done = False
    while not done:
        week = []
        for _ in range(7):
            cycle_day = (curr_date - start).days + 1
            is_active = 1 <= cycle_day <= cycle_len
            
            labels = []
            if is_active:
                drugs = day_map.get(cycle_day, [])
                if drugs:
                    labels.extend(drugs)
                else:
                    labels.append("Rest")
                    
            week.append({
                "date": curr_date.isoformat(),
                "cycle_day": cycle_day if is_active else None,
                "labels": labels
            })
            curr_date += dt.timedelta(days=1)
        grid.append(week)
        
        if curr_date > end_date:
            done = True
            
    last_sat = curr_date - dt.timedelta(days=1)
    
    # 5. Clean regimen for preview display
    reg_for_preview = Regimen(
        name=doc_title,
        disease_state=reg.disease_state,
        on_study=reg.on_study,
        notes=reg.notes,
        therapies=reg.therapies
    )
    
    return doc_title, label, reg_for_preview, first_sun, last_sat, grid