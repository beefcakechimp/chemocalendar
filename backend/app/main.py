from __future__ import annotations
import os
import datetime as dt
import io
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
#from fastapi.responses import StreamingResponse

from regimenbank import (
    RegimenBank,
    Regimen,
    Chemotherapy,
    export_calendar_docx,
    DEFAULT_DB,
)
from .schemas import (
    RegimenIn,
    RenameRegimenRequest,
    CalendarPreviewRequest,
    CalendarPreviewResponse,
)
from .calendar_service import build_preview

app = FastAPI(title="Chemo Calendar API")

# Read allowed origins from environment, default to localhost
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
# Allow requests from:
#   - Local dev (localhost:3000, Codespaces)
#   - Railway production frontend (*.railway.app, *.up.railway.app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_origin_regex=r"https://.*\.(railway\.app|up\.railway\.app|app\.github\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use /data/regimenbank.db when running on Railway (persistent volume),
# otherwise fall back to the local default.
import os
_db_path = Path(os.environ.get("DB_PATH", str(DEFAULT_DB)))
BANK = RegimenBank(_db_path)


def _to_regimen(rin: RegimenIn) -> Regimen:
    therapies = [
        Chemotherapy(
            name=t.name,
            route=t.route,
            dose=t.dose,
            frequency=t.frequency,
            duration=t.duration,
            total_doses=t.total_doses,
        )
        for t in rin.therapies
    ]
    return Regimen(
        name=rin.name.strip(),
        disease_state=(rin.disease_state.strip() if rin.disease_state else None),
        on_study=bool(rin.on_study),
        notes=(rin.notes.strip() if rin.notes else None),
        therapies=therapies,
    )


def _cycle_label_from_inputs(phase: str, cycle_num: int | None) -> str:
    if phase == "Induction":
        return "Induction"
    if cycle_num is None:
        return "Cycle 1"
    return f"Cycle {cycle_num}"


def _safe_filename_piece(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return "calendar"
    out = []
    for ch in s:
        if ch.isalnum() or ch in ("_", "-"):
            out.append(ch)
        elif ch.isspace():
            out.append("_")
    return "".join(out) or "calendar"


@app.get("/")
def root():
    return {"name": "Chemo Calendar API", "ok": True, "docs": "/docs"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/regimens", response_model=List[str])
def list_regimens():
    return BANK.list_regimens()


@app.get("/regimens/{name}")
def get_regimen(name: str):
    r = BANK.get_regimen(name)
    if not r:
        raise HTTPException(status_code=404, detail="Regimen not found")
    return {
        "name": r.name,
        "disease_state": r.disease_state,
        "on_study": r.on_study,
        "notes": r.notes,
        "therapies": [
            {
                "name": t.name,
                "route": t.route,
                "dose": t.dose,
                "frequency": t.frequency,
                "duration": t.duration,
                "total_doses": t.total_doses,
            }
            for t in (r.therapies or [])
        ],
    }


@app.post("/regimens")
def upsert_regimen(body: RegimenIn):
    reg = _to_regimen(body)
    if not reg.name:
        raise HTTPException(status_code=400, detail="Regimen name is required")
    BANK.upsert_regimen(reg)
    return {"ok": True}


@app.delete("/regimens/{name}")
def delete_regimen(name: str):
    ok = BANK.delete_regimen(name)
    if not ok:
        raise HTTPException(status_code=404, detail="Regimen not found")
    return {"ok": True}


@app.post("/regimens/rename")
def rename_regimen(body: RenameRegimenRequest):
    old = body.old_name.strip()
    new = body.new_name.strip()
    if not old or not new:
        raise HTTPException(status_code=400, detail="old_name and new_name required")
    if old == new:
        return {"ok": True}

    r = BANK.get_regimen(old)
    if not r:
        raise HTTPException(status_code=404, detail="Regimen not found")

    if BANK.get_regimen(new):
        raise HTTPException(status_code=409, detail="A regimen with new_name already exists")

    BANK.save_as(r, new)
    BANK.delete_regimen(old)
    return {"ok": True}


@app.post("/calendar/preview", response_model=CalendarPreviewResponse)
def calendar_preview(req: CalendarPreviewRequest):
    reg = BANK.get_regimen(req.regimen_name)
    if not reg:
        raise HTTPException(status_code=404, detail="Regimen not found")

    try:
        start = dt.date.fromisoformat(req.start_date)
    except Exception:
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")

    if int(req.cycle_len) < 1:
        raise HTTPException(status_code=400, detail="cycle_len must be >= 1")

    header, label, reg_for_preview, first_sun, last_sat, grid = build_preview(
        reg=reg,
        start=start,
        cycle_len=int(req.cycle_len),
        phase=req.phase,
        cycle_num=req.cycle_num,
        title_override=req.title_override,
    )

    return CalendarPreviewResponse(
        header=header,
        label=label,
        regimen_title=reg_for_preview.name,
        first_sun=first_sun.isoformat(),
        last_sat=last_sat.isoformat(),
        grid=grid,
    )


@app.post("/calendar/export")
def calendar_export(req: CalendarPreviewRequest):
    reg = BANK.get_regimen(req.regimen_name)
    if not reg:
        raise HTTPException(status_code=404, detail="Regimen not found")

    try:
        start = dt.date.fromisoformat(req.start_date)
    except Exception:
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")

    if int(req.cycle_len) < 1:
        raise HTTPException(status_code=400, detail="cycle_len must be >= 1")

    label = _cycle_label_from_inputs(req.phase, req.cycle_num)

    doc_title = (req.title_override or reg.name).strip() or reg.name
    reg_for_export = Regimen(
        name=doc_title,
        disease_state=reg.disease_state,
        on_study=reg.on_study,
        notes=reg.notes,
        therapies=reg.therapies,
    )

    tmp_path = Path("/_calendar_export.docx")
    ok = export_calendar_docx(
        reg=reg_for_export,
        start=start,
        cycle_len=int(req.cycle_len),
        out_path=tmp_path,
        cycle_label=label,
        note=(req.note.strip() if req.note else None),
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Export failed (python-docx missing or export error).")

    data = tmp_path.read_bytes()
    try:
        tmp_path.unlink(missing_ok=True)
    except Exception:
        pass

    safe_title = _safe_filename_piece(doc_title)
    safe_label = _safe_filename_piece(label.replace(" ", ""))
    filename = f"{safe_title}_{safe_label}_{start.isoformat()}.docx"

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
