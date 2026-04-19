from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class TherapyIn(BaseModel):
    name: str
    route: str
    dose: str
    frequency: str
    duration: str
    total_doses: Optional[int] = None


class RegimenIn(BaseModel):
    name: str
    disease_state: Optional[str] = None
    on_study: bool = False
    notes: Optional[str] = None
    therapies: List[TherapyIn] = Field(default_factory=list)


class RenameRegimenRequest(BaseModel):
    old_name: str
    new_name: str


class CalendarPreviewRequest(BaseModel):
    regimen_name: str
    title_override: Optional[str] = None
    start_date: str  # YYYY-MM-DD
    cycle_len: int = 28
    phase: Literal["Cycle", "Induction"] = "Cycle"
    cycle_num: Optional[int] = 1
    note: Optional[str] = None


class CalendarCell(BaseModel):
    date: str  # YYYY-MM-DD
    cycle_day: Optional[int] = None
    labels: List[str] = Field(default_factory=list)


class CalendarPreviewResponse(BaseModel):
    header: str
    label: str
    regimen_title: str
    first_sun: str
    last_sat: str
    grid: List[List[CalendarCell]]