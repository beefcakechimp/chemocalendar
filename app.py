#!/usr/bin/env python3
import datetime as dt
from pathlib import Path
from typing import Optional, List

import streamlit as st

from regimenbank import (
    RegimenBank,
    Regimen,
    Chemotherapy,
    export_calendar_docx,
    compute_calendar_grid,
    DEFAULT_DB,
)

# ---------------- page config ----------------
st.set_page_config(
    page_title="Chemotherapy Regimen Tools",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------- styling ----------------
st.markdown(
    """
<style>
/* --- App background + canvas --- */
html, body, [data-testid="stAppViewContainer"] {
  background: #f5f7fb !important;
}
[data-testid="block-container"]{
  max-width: 1200px;
  padding-left: 1.6rem;
  padding-right: 1.6rem;
  padding-top: 1.1rem;
  padding-bottom: 2rem;
}

/* Headings */
h1 {
  font-size: 2.05rem !important;
  font-weight: 850 !important;
  letter-spacing: -0.02em;
  margin-bottom: 0.35rem !important;
}
h2 {
  font-size: 1.25rem !important;
  font-weight: 780 !important;
  margin-top: 0.75rem !important;
  margin-bottom: 0.25rem !important;
}
h3 {
  font-size: 1.05rem !important;
  font-weight: 740 !important;
  margin-top: 0.65rem !important;
  margin-bottom: 0.25rem !important;
}

/* --- Sidebar buttons --- */
section[data-testid="stSidebar"] button {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 760 !important;
  padding: 0.68rem 0.95rem !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
}
section[data-testid="stSidebar"] button:hover { transform: translateY(-1px); }

/* --- Buttons --- */
button[kind="primary"] {
  font-weight: 860 !important;
  padding: 0.78rem 0.95rem !important;
  border-radius: 12px !important;
}

/* --- Top "app bar" --- */
.appbar {
  background: #4f81c7;
  color: white;
  padding: 16px 18px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.10);
  margin-bottom: 14px;
}
.appbar .brand {
  font-weight: 880;
  font-size: 1.15rem;
  letter-spacing: 0.2px;
}
.appbar .sub {
  opacity: 0.92;
  font-size: 0.95rem;
}

/* --- Cards --- */
.card {
  background: white;
  border-radius: 14px;
  padding: 14px 14px;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

/* --- Stepper --- */
.stepper {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 4px 0 10px 0;
}
.step {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(79,129,199,0.10);
  color: #1f2a44;
  font-weight: 760;
  font-size: 0.90rem;
  border: 1px solid rgba(79,129,199,0.18);
}
.step.active {
  background: #4f81c7;
  color: white;
  border-color: rgba(255,255,255,0.25);
}

/* --- Make Streamlit widgets feel less "boxy" --- */
div[data-baseweb="input"], div[data-baseweb="select"] > div {
  border-radius: 12px !important;
}

/* Compact radio spacing */
div[role="radiogroup"] > label {
  padding-top: 0.15rem !important;
  padding-bottom: 0.15rem !important;
}

/* Subtle divider */
hr { margin-top: 0.9rem; margin-bottom: 0.9rem; opacity: 0.22; }

/* --- Calendar preview table --- */
.chemo-calendar {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
  font-size: 0.86rem;
}
.chemo-calendar th, .chemo-calendar td {
  border: 1px solid rgba(0,0,0,0.10);
  padding: 6px 6px;
  vertical-align: top;
}
.chemo-calendar th {
  text-align: center;
  background-color: #111827;
  color: #ffffff;
  font-weight: 760;
  padding: 8px 6px;
}
.chemo-calendar .cell-date { text-align: right; font-weight: 760; margin-bottom: 2px; }
.chemo-calendar .cell-day  { font-style: italic; opacity: 0.9; margin-bottom: 4px; }
.chemo-calendar .cell-med  { font-weight: 760; }
.chemo-calendar .cell-rest { opacity: 0.6; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- config ----------------
APP_PASSWORD = "honc25"
COLS_3 = [1.6, 4.8, 2.6]

# ---------------- helpers ----------------
def get_bank() -> RegimenBank:
    db_path = DEFAULT_DB
    if "db_path" not in st.session_state or st.session_state["db_path"] != str(db_path):
        st.session_state["db_path"] = str(db_path)
        st.session_state["bank"] = RegimenBank(db_path)
    return st.session_state["bank"]

def list_regimens_grouped(bank: RegimenBank):
    off: List[Regimen] = []
    on: List[Regimen] = []
    for name in bank.list_regimens():
        r = bank.get_regimen(name)
        if not r:
            continue
        (on if r.on_study else off).append(r)
    off.sort(key=lambda r: r.name.lower())
    on.sort(key=lambda r: r.name.lower())
    return off, on

def _cycle_label_from_inputs(phase: str, cycle_num: Optional[int]) -> str:
    if phase == "Induction":
        return "Induction"
    if cycle_num is None:
        return "Cycle 1"
    return f"Cycle {cycle_num}"

def _note_snip(s: Optional[str], n: int = 140) -> str:
    txt = (s or "").strip().replace("\n", " ")
    return (txt[:n] + "…") if len(txt) > n else txt

# ---------------- auth (form-based) ----------------
def require_login() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("auth_error", "")

    if st.session_state["authenticated"]:
        return

    st.title("Sign in")
    st.write("Enter the access key to continue.")

    with st.form("auth_form", clear_on_submit=True):
        pw = st.text_input("Access key", type="password", key="auth_pw")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        if pw and pw == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.session_state["auth_error"] = ""
            st.session_state.pop("auth_pw", None)
            st.rerun()
        else:
            st.session_state["auth_error"] = "Invalid access key."

    if st.session_state.get("auth_error"):
        st.error(st.session_state["auth_error"])

    st.stop()

# ---------------- calendar preview helpers ----------------
def _format_month_year_range(first_sun: dt.date, last_sat: dt.date) -> str:
    """
    Desired header formatting:
      - Same month/year: "December 2025"
      - Different months, same year: "December – January 2025"
      - Different years: "December 2025 – January 2026"
    """
    import calendar as pycal
    fm = pycal.month_name[first_sun.month]
    lm = pycal.month_name[last_sat.month]

    if first_sun.year == last_sat.year and first_sun.month == last_sat.month:
        return f"{fm} {first_sun.year}"
    if first_sun.year == last_sat.year:
        return f"{fm} – {lm} {first_sun.year}"
    return f"{fm} {first_sun.year} – {lm} {last_sat.year}"

def render_calendar_preview(
    reg: Regimen,
    start: dt.date,
    cycle_len: int,
    label: str,
    note: Optional[str],
) -> None:
    first_sun, last_sat, _, grid = compute_calendar_grid(reg, start, cycle_len)
    header = _format_month_year_range(first_sun, last_sat)

    st.markdown(f"**{reg.name} — {label}**")
    st.markdown(header)
    if note:
        st.markdown(f"*{note}*")

    header_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    html = ['<table class="chemo-calendar">']
    html.append("<tr>" + "".join(f"<th>{d}</th>" for d in header_names) + "</tr>")

    import calendar as calmod
    for week in grid:
        html.append("<tr>")
        for cell in week:
            date = cell["date"]
            cd = cell["cycle_day"]
            labels = cell["labels"] or []

            html.append("<td>")
            html.append(f'<div class="cell-date">{calmod.month_abbr[date.month]} {date.day}</div>')
            if cd is not None:
                html.append(f'<div class="cell-day">Day {cd}</div>')
                for lab in labels:
                    if lab.lower() == "rest":
                        html.append(f'<div class="cell-rest">{lab}</div>')
                    else:
                        html.append(f'<div class="cell-med">{lab}</div>')
            html.append("</td>")
        html.append("</tr>")

    html.append("</table>")
    st.markdown("".join(html), unsafe_allow_html=True)

# ---------------- workflow + draft state ----------------
def _init_workflow_state() -> None:
    st.session_state.setdefault("builder_mode", "start")
    st.session_state.setdefault("active_regimen_name", None)

    st.session_state.setdefault("draft_source_name", None)
    st.session_state.setdefault("draft_name", "")
    st.session_state.setdefault("draft_disease", "")
    st.session_state.setdefault("draft_on_study", False)
    st.session_state.setdefault("draft_notes", "")
    st.session_state.setdefault("draft_therapies", [])
    st.session_state.setdefault("th_edit_idx", None)

def _load_regimen_into_draft(reg: Optional[Regimen], source_name: Optional[str]) -> None:
    st.session_state["draft_source_name"] = source_name
    st.session_state["th_edit_idx"] = None

    if reg is None:
        st.session_state["draft_name"] = ""
        st.session_state["draft_disease"] = ""
        st.session_state["draft_on_study"] = False
        st.session_state["draft_notes"] = ""
        st.session_state["draft_therapies"] = []
        return

    st.session_state["draft_name"] = reg.name or ""
    st.session_state["draft_disease"] = reg.disease_state or ""
    st.session_state["draft_on_study"] = bool(reg.on_study)
    st.session_state["draft_notes"] = reg.notes or ""
    st.session_state["draft_therapies"] = [t for t in (reg.therapies or [])]

def _draft_to_regimen(name_override: Optional[str] = None) -> Regimen:
    nm = (name_override or st.session_state["draft_name"]).strip()
    return Regimen(
        name=nm,
        disease_state=(st.session_state["draft_disease"].strip() or None),
        on_study=bool(st.session_state["draft_on_study"]),
        notes=(st.session_state["draft_notes"].strip() or None),
        therapies=list(st.session_state["draft_therapies"]),
    )

# ---------------- pages ----------------
def page_overview() -> None:
    st.markdown(
        """
<div class="appbar">
  <div class="brand">Chemotherapy Regimen Tools</div>
  <div class="sub">Regimen bank • Calendar generator • DOCX export</div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Regimen Builder")
        st.markdown(
            """
- Create and standardize regimens  
- Use existing regimens as templates  
- Store selection notes to distinguish similar regimens
"""
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Calendar Generator")
        st.markdown(
            """
- Guided workflow (Regimen → Schedule → Preview/Export)  
- In-page preview  
- Export formatted DOCX
"""
        )
        st.markdown("</div>", unsafe_allow_html=True)

def page_builder(bank: RegimenBank) -> None:
    _init_workflow_state()

    st.markdown(
        """
<div class="appbar">
  <div class="brand">Regimen Builder</div>
  <div class="sub">Create • Template • Save</div>
</div>
""",
        unsafe_allow_html=True,
    )

    mode = st.session_state["builder_mode"]

    if mode == "start":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Start")
        c1, c2 = st.columns([1, 1], gap="large")
        with c1:
            st.markdown("### Create new")
            st.write("Start completely from scratch.")
            if st.button("New regimen", type="primary", use_container_width=True, key="rb_new"):
                _load_regimen_into_draft(None, source_name=None)
                st.session_state["builder_mode"] = "edit"
                st.rerun()

        with c2:
            st.markdown("### Use template")
            st.write("Copy an existing regimen, then edit.")
            if st.button("Use existing as template", use_container_width=True, key="rb_template"):
                st.session_state["builder_mode"] = "template"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if mode == "template":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Choose a template")

        top = st.columns([1, 1, 1], gap="medium")
        with top[0]:
            if st.button("← Back", use_container_width=True, key="rb_tpl_back"):
                st.session_state["builder_mode"] = "start"
                st.rerun()
        with top[2]:
            if st.button("Start blank instead", type="primary", use_container_width=True, key="rb_tpl_blank"):
                _load_regimen_into_draft(None, source_name=None)
                st.session_state["builder_mode"] = "edit"
                st.rerun()

        off, on = list_regimens_grouped(bank)
        q = st.text_input(
            "Search",
            value="",
            placeholder="Search regimens (name or notes)…",
            key="rb_tpl_q",
        ).strip().lower()

        tab_off, tab_on = st.tabs([f"Off protocol ({len(off)})", f"On study ({len(on)})"])

        def _render_template_list(regs: List[Regimen], empty_msg: str):
            if q:
                regs = [r for r in regs if q in r.name.lower() or q in (r.notes or "").lower()]

            if not regs:
                st.info(empty_msg)
                return

            with st.container(height=520, border=True):
                for r in regs:
                    if st.button(r.name, use_container_width=True, key=f"tpl_{r.name}"):
                        _load_regimen_into_draft(r, source_name=r.name)
                        st.session_state["builder_mode"] = "edit"
                        st.rerun()

                    sn = _note_snip(r.notes, n=140)
                    if sn:
                        st.caption(sn)
                    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

        with tab_off:
            _render_template_list(off, "No matching off-protocol regimens.")
        with tab_on:
            _render_template_list(on, "No matching on-study regimens.")

        st.markdown("</div>", unsafe_allow_html=True)
        return

    left, right = st.columns([2.8, 2.2], gap="large")

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        header = st.columns([1, 3], gap="small")
        with header[0]:
            if st.button("← Start", use_container_width=True, key="rb_back_start"):
                st.session_state["builder_mode"] = "start"
                st.rerun()
        with header[1]:
            src = st.session_state.get("draft_source_name")
            if src:
                st.caption(f"Template / existing regimen: {src}")

        st.markdown("### Basics")
        st.text_input("Regimen name", key="draft_name", placeholder="e.g., Aza/Ven 70 mg x14")
        st.text_input("Disease state", key="draft_disease", placeholder="e.g., AML")

        status = st.radio(
            "Protocol status",
            options=["Off protocol", "On study"],
            index=1 if st.session_state["draft_on_study"] else 0,
            horizontal=True,
            key="rb_status",
        )
        st.session_state["draft_on_study"] = (status == "On study")

        st.markdown("### Selection notes")
        st.text_area(
            "These show during template selection to distinguish similar regimens.",
            key="draft_notes",
            height=120,
            placeholder="Differentiators: dose variant, schedule nuance, supportive care, etc.",
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### Save")

        def _save_regimen(go_to_calendar: bool) -> None:
            reg = _draft_to_regimen()
            if not reg.name:
                st.error("Regimen name is required.")
                return

            old_name = st.session_state.get("draft_source_name")
            new_name = reg.name

            if old_name and old_name != new_name:
                if bank.get_regimen(new_name):
                    st.error(f"A regimen named '{new_name}' already exists. Choose a different name.")
                    return

                bank.upsert_regimen(reg)
                bank.delete_regimen(old_name)
                st.session_state["draft_source_name"] = new_name
            else:
                bank.upsert_regimen(reg)
                st.session_state["draft_source_name"] = new_name

            st.session_state["active_regimen_name"] = new_name

            if go_to_calendar:
                st.session_state["section"] = "Calendar Generator"
                # jump user straight into Step 2 (schedule) now that regimen is set
                st.session_state["cal_step"] = 2
                st.rerun()
            else:
                st.success("Saved.")

        save_row = st.columns([1, 1], gap="medium")
        with save_row[0]:
            if st.button("Save & continue → Calendar", type="primary", use_container_width=True, key="rb_save_cal"):
                _save_regimen(go_to_calendar=True)
        with save_row[1]:
            if st.button("Save (stay here)", use_container_width=True, key="rb_save_stay"):
                _save_regimen(go_to_calendar=False)

        saved_name = st.session_state.get("draft_source_name")
        if saved_name:
            with st.expander("Delete regimen", expanded=False):
                st.write("Type the regimen name to confirm deletion.")
                confirm = st.text_input("Confirmation", placeholder=saved_name, key="delete_confirm")
                if st.button("Delete", use_container_width=True, key="rb_delete"):
                    if confirm.strip() == saved_name:
                        bank.delete_regimen(saved_name)
                        _load_regimen_into_draft(None, source_name=None)
                        st.session_state["builder_mode"] = "start"
                        st.success("Deleted.")
                        st.rerun()
                    else:
                        st.error("Confirmation text does not match.")

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Therapies")
        therapies: List[Chemotherapy] = st.session_state["draft_therapies"]

        if therapies:
            for i, t in enumerate(therapies):
                st.markdown(
                    f"**{t.name}**  \n"
                    f"{t.route} — {t.dose} — {t.frequency} — {t.duration}"
                )
                a, b = st.columns([1, 1], gap="small")
                with a:
                    if st.button("Edit", key=f"th_edit_{i}", use_container_width=True):
                        st.session_state["th_edit_idx"] = i
                        st.rerun()
                with b:
                    if st.button("Remove", key=f"th_rm_{i}", use_container_width=True):
                        st.session_state["draft_therapies"].pop(i)
                        st.rerun()
                st.markdown("---")
        else:
            st.info("No therapies yet. Add the first one below.")

        is_editing = (
            st.session_state["th_edit_idx"] is not None
            and 0 <= st.session_state["th_edit_idx"] < len(therapies)
        )
        cur = therapies[st.session_state["th_edit_idx"]] if is_editing else None

        with st.form("therapy_editor", clear_on_submit=not is_editing):
            st.markdown("#### " + ("Edit therapy" if is_editing else "Add therapy"))

            name = st.text_input("Agent", value=(cur.name if cur else ""), placeholder="e.g., Venetoclax")
            route = st.text_input("Route", value=(cur.route if cur else ""), placeholder="e.g., PO / IV / SQ")
            dose = st.text_input("Dose", value=(cur.dose if cur else ""), placeholder="e.g., 70 mg")
            freq = st.text_input("Frequency", value=(cur.frequency if cur else ""), placeholder="e.g., Daily / BID")
            daymap = st.text_input("Day map", value=(cur.duration if cur else ""), placeholder="e.g., Days 1–14")
            total = st.text_input(
                "Total doses (optional)",
                value=("" if not cur or cur.total_doses is None else str(cur.total_doses)),
                placeholder="e.g., 14",
            )

            c1, c2 = st.columns([1, 1], gap="medium")
            with c1:
                ok = st.form_submit_button("Save therapy", type="primary", use_container_width=True)
            with c2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

        if cancel:
            st.session_state["th_edit_idx"] = None
            st.rerun()

        if ok:
            errs = []
            if not name.strip(): errs.append("Agent is required.")
            if not route.strip(): errs.append("Route is required.")
            if not dose.strip(): errs.append("Dose is required.")
            if not daymap.strip(): errs.append("Day map is required.")

            if errs:
                for e in errs:
                    st.error(e)
            else:
                td = None
                if total.strip():
                    try:
                        td = int(total.strip())
                    except ValueError:
                        st.error("Total doses must be an integer (or blank).")
                        td = None

                new_t = Chemotherapy(
                    name=name.strip(),
                    route=route.strip(),
                    dose=dose.strip(),
                    frequency=freq.strip(),
                    duration=daymap.strip(),
                    total_doses=td,
                )

                if is_editing:
                    therapies[st.session_state["th_edit_idx"]] = new_t
                    st.session_state["th_edit_idx"] = None
                else:
                    therapies.append(new_t)

                st.session_state["draft_therapies"] = therapies
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

def page_calendar(bank: RegimenBank) -> None:
    st.markdown(
        """
<div class="appbar">
  <div class="brand">Chemotherapy Calendar</div>
  <div class="sub">Guided workflow • Professional preview • DOCX export</div>
</div>
""",
        unsafe_allow_html=True,
    )

    off, on = list_regimens_grouped(bank)
    if not off and not on:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.info("No regimens available. Create regimens in Regimen Builder first.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ---------- stable state ----------
    st.session_state.setdefault("cal_step", 1)

    st.session_state.setdefault("cal_group", "Off protocol")
    st.session_state.setdefault("cal_search", "")
    st.session_state.setdefault("cal_regimen_name", None)

    # Title state (user-facing doc title; does NOT rename regimen in bank)
    st.session_state.setdefault("cal_title", "")
    st.session_state.setdefault("cal_title_seeded_for", None)
    st.session_state.setdefault("cal_title_dirty", False)

    st.session_state.setdefault("cal_start", dt.date.today())
    st.session_state.setdefault("cal_cycle_len", 28)
    st.session_state.setdefault("cal_phase", "Cycle")
    st.session_state.setdefault("cal_cycle_num", 1)
    st.session_state.setdefault("cal_note", "")

    # ---------- stepper ----------
    steps = {1: "1) Regimen", 2: "2) Schedule", 3: "3) Preview / Export"}
    st.markdown(
        '<div class="stepper">'
        + "".join(
            f'<div class="step {"active" if st.session_state["cal_step"]==k else ""}">{v}</div>'
            for k, v in steps.items()
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    nav = st.columns([1, 1, 6], gap="small")
    with nav[0]:
        if st.button("← Back", use_container_width=True, disabled=st.session_state["cal_step"] == 1):
            st.session_state["cal_step"] -= 1
            st.rerun()
    with nav[1]:
        if st.button("Next →", type="primary", use_container_width=True, disabled=st.session_state["cal_step"] == 3):
            st.session_state["cal_step"] += 1
            st.rerun()

    # ---------- helper: regimen selection ----------
    def _select_regimen(name: str) -> None:
        st.session_state["cal_regimen_name"] = name
        # Auto-populate title from regimen name whenever regimen changes
        st.session_state["cal_title"] = name
        st.session_state["cal_title_seeded_for"] = name
        st.session_state["cal_title_dirty"] = False

    def _mark_title_dirty() -> None:
        st.session_state["cal_title_dirty"] = True

    # ---------- Step 1: Regimen ----------
    if st.session_state["cal_step"] == 1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        row = st.columns([1.15, 2.4], gap="medium")
        with row[0]:
            st.radio(
                "Group",
                options=["Off protocol", "On study"],
                key="cal_group",
                horizontal=True,
            )
        with row[1]:
            st.text_input(
                "Search",
                key="cal_search",
                placeholder="Filter by regimen name or selection notes…",
            )

        candidates = off if st.session_state["cal_group"] == "Off protocol" else on
        if not candidates:
            st.warning(f"No {st.session_state['cal_group'].lower()} regimens found.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        q = (st.session_state.get("cal_search") or "").strip().lower()
        regs = candidates
        if q:
            regs = [r for r in regs if q in r.name.lower() or q in (r.notes or "").lower()]
        if not regs:
            st.warning("No matching regimens.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        reg_map_all = {r.name: r for r in candidates}
        filtered_names = [r.name for r in regs]

        active = st.session_state.get("active_regimen_name")
        if st.session_state.get("cal_regimen_name") not in filtered_names:
            st.session_state["cal_regimen_name"] = active if active in filtered_names else filtered_names[0]

        options = [r.name for r in regs]
        label_lookup = {r.name: r.name for r in regs}  # name-only; notes shown only in Details

        pick_col, details_col = st.columns([2.2, 1.8], gap="large")
        with pick_col:
            st.markdown("**Pick a regimen**")
            with st.container(height=520, border=True):
                chosen = st.radio(
                    "Regimens",
                    options=options,
                    index=options.index(st.session_state["cal_regimen_name"]),
                    format_func=lambda name: label_lookup.get(name, name),
                    key="cal_regimen_radio",
                    label_visibility="collapsed",
                )
            if chosen != st.session_state["cal_regimen_name"]:
                _select_regimen(chosen)
                st.rerun()

        selected_name = st.session_state["cal_regimen_name"]
        reg = reg_map_all[selected_name]

        with details_col:
            st.markdown("**Details**")
            meta = []
            meta.append("On study" if reg.on_study else "Off protocol")
            if reg.disease_state:
                meta.append(reg.disease_state)
            st.caption(" • ".join(meta) if meta else " ")

            with st.container(height=520, border=True):
                if reg.notes and reg.notes.strip():
                    st.write(reg.notes)
                else:
                    st.info("No selection notes for this regimen.")

        st.markdown("</div>", unsafe_allow_html=True)

        # Ensure title seeded at least once (if user lands here via sidebar)
        if st.session_state.get("cal_title_seeded_for") != reg.name:
            st.session_state["cal_title"] = reg.name
            st.session_state["cal_title_seeded_for"] = reg.name
            st.session_state["cal_title_dirty"] = False

        return  # step 1 ends here

    # For steps 2/3 we need a resolved regimen
    candidates = off if st.session_state["cal_group"] == "Off protocol" else on
    if not candidates:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.warning(f"No {st.session_state['cal_group'].lower()} regimens found.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    reg_map_all = {r.name: r for r in candidates}
    if st.session_state.get("cal_regimen_name") not in reg_map_all:
        # fall back safely
        st.session_state["cal_regimen_name"] = candidates[0].name

    reg = reg_map_all[st.session_state["cal_regimen_name"]]

    # If regimen changed implicitly (e.g., group), re-seed title
    if st.session_state.get("cal_title_seeded_for") != reg.name:
        st.session_state["cal_title"] = reg.name
        st.session_state["cal_title_seeded_for"] = reg.name
        st.session_state["cal_title_dirty"] = False

    # ---------- Step 2: Schedule ----------
    if st.session_state["cal_step"] == 2:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        top = st.columns([2.2, 1.8], gap="large")
        with top[0]:
            st.subheader("Schedule")
            st.caption("Define the cycle parameters. Preview/export comes next.")

            st.text_input(
                "Calendar title (for the document)",
                key="cal_title",
                on_change=_mark_title_dirty,
                help="This does not rename the regimen in the bank. It only changes the calendar document title.",
            )

            c1, c2, c3 = st.columns([1, 1, 1], gap="medium")
            with c1:
                st.date_input("Cycle start date", key="cal_start")
            with c2:
                st.number_input("Cycle length (days)", min_value=1, key="cal_cycle_len")
            with c3:
                st.selectbox("Phase", options=["Cycle", "Induction"], key="cal_phase")
                if st.session_state["cal_phase"] == "Cycle":
                    st.number_input("Cycle number", min_value=1, step=1, key="cal_cycle_num")

            cycle_num = st.session_state["cal_cycle_num"] if st.session_state["cal_phase"] == "Cycle" else None
            label = _cycle_label_from_inputs(st.session_state["cal_phase"], cycle_num)
            st.text_input("Calendar label", value=label, disabled=True)

            st.text_input(
                "Optional note",
                key="cal_note",
                placeholder="e.g., ‘Hold venetoclax if ANC < …’",
            )

        with top[1]:
            st.subheader("Selected regimen")
            meta = []
            meta.append("On study" if reg.on_study else "Off protocol")
            if reg.disease_state:
                meta.append(reg.disease_state)
            st.caption(" • ".join(meta) if meta else " ")

            with st.container(height=360, border=True):
                st.markdown(f"**{reg.name}**")
                st.markdown("---")
                if reg.notes and reg.notes.strip():
                    st.write(reg.notes)
                else:
                    st.caption("No selection notes.")

            # Quick jump back to regimen selection
            if st.button("Change regimen", use_container_width=True):
                st.session_state["cal_step"] = 1
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ---------- Step 3: Preview / Export ----------
    st.markdown('<div class="card">', unsafe_allow_html=True)

    # Derive label
    cycle_num = st.session_state["cal_cycle_num"] if st.session_state["cal_phase"] == "Cycle" else None
    label = _cycle_label_from_inputs(st.session_state["cal_phase"], cycle_num)

    # Title override (not mutating bank regimen)
    cal_title = (st.session_state.get("cal_title") or reg.name).strip()

    reg_for_preview = Regimen(
        name=cal_title,
        disease_state=reg.disease_state,
        on_study=reg.on_study,
        notes=reg.notes,
        therapies=reg.therapies,
    )

    left, right = st.columns([3.2, 1.4], gap="large")

    with left:
        st.subheader("Preview")
        render_calendar_preview(
            reg=reg_for_preview,
            start=st.session_state["cal_start"],
            cycle_len=int(st.session_state["cal_cycle_len"]),
            label=label,
            note=(st.session_state["cal_note"].strip() or None),
        )

    with right:
        st.subheader("Export")
        st.caption("Generates a formatted calendar matching the preview.")

        st.markdown("**Summary**")
        meta = []
        meta.append("On study" if reg.on_study else "Off protocol")
        if reg.disease_state:
            meta.append(reg.disease_state)
        st.write(f"**Regimen:** {reg.name}")
        st.write(f"**Doc title:** {cal_title}")
        st.write(f"**Start:** {st.session_state['cal_start'].isoformat()}")
        st.write(f"**Cycle length:** {int(st.session_state['cal_cycle_len'])} days")
        st.write(f"**Label:** {label}")
        if meta:
            st.caption(" • ".join(meta))

        st.markdown("---")

        if st.button("Generate calendar", type="primary", use_container_width=True, key="cal_generate"):
            tmp_path = Path("calendar_preview.docx")

            reg_for_export = Regimen(
                name=cal_title,
                disease_state=reg.disease_state,
                on_study=reg.on_study,
                notes=reg.notes,
                therapies=reg.therapies,
            )

            ok = export_calendar_docx(
                reg=reg_for_export,
                start=st.session_state["cal_start"],
                cycle_len=int(st.session_state["cal_cycle_len"]),
                out_path=tmp_path,
                cycle_label=label,
                note=(st.session_state["cal_note"].strip() or None),
            )
            if not ok:
                st.error("Export failed. Ensure python-docx is installed.")
            else:
                data = tmp_path.read_bytes()
                tmp_path.unlink(missing_ok=True)
                st.success("Calendar generated.")

                safe_title = cal_title.replace(" ", "_")
                st.download_button(
                    label="Download",
                    data=data,
                    file_name=f"{safe_title}_{label.replace(' ', '')}_{st.session_state['cal_start'].isoformat()}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        if st.button("Edit schedule", use_container_width=True):
            st.session_state["cal_step"] = 2
            st.rerun()

        if st.button("Pick different regimen", use_container_width=True):
            st.session_state["cal_step"] = 1
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- main ----------------
def main() -> None:
    require_login()

    st.session_state.setdefault("section", "Main")
    section = st.session_state["section"]

    with st.sidebar:
        st.title("Navigation")

        if st.button("Main", type="primary" if section == "Main" else "secondary", use_container_width=True, key="nav_main"):
            st.session_state["section"] = "Main"
            st.rerun()

        if st.button("Regimen Builder", type="primary" if section == "Regimen Builder" else "secondary", use_container_width=True, key="nav_builder"):
            st.session_state["section"] = "Regimen Builder"
            st.rerun()

        if st.button("Calendar Generator", type="primary" if section == "Calendar Generator" else "secondary", use_container_width=True, key="nav_calendar"):
            st.session_state["section"] = "Calendar Generator"
            # If user comes in fresh, default to step 1
            st.session_state.setdefault("cal_step", 1)
            st.rerun()

    bank = get_bank()

    section = st.session_state["section"]
    if section == "Main":
        page_overview()
    elif section == "Regimen Builder":
        page_builder(bank)
    elif section == "Calendar Generator":
        page_calendar(bank)

if __name__ == "__main__":
    main()