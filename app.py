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
[data-testid="block-container"]{
  padding-left: 2rem;
  padding-right: 2rem;
  padding-top: 1.25rem;
  padding-bottom: 1.25rem;
}

h1 {
  font-size: 2.05rem !important;
  font-weight: 800 !important;
  letter-spacing: -0.02em;
  margin-bottom: 0.35rem !important;
}
h2 {
  font-size: 1.25rem !important;
  font-weight: 750 !important;
  margin-top: 0.75rem !important;
  margin-bottom: 0.25rem !important;
}
h3 {
  font-size: 1.05rem !important;
  font-weight: 700 !important;
  margin-top: 0.65rem !important;
  margin-bottom: 0.25rem !important;
}

section[data-testid="stSidebar"] button {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 750 !important;
  padding: 0.72rem 0.95rem !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
}
section[data-testid="stSidebar"] button:hover { transform: translateY(-1px); }

button[kind="primary"] {
  font-weight: 850 !important;
  padding: 0.78rem 0.95rem !important;
  border-radius: 14px !important;
}

.chemo-calendar {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
  font-size: 0.86rem;
}
.chemo-calendar th, .chemo-calendar td {
  border: 1px solid rgba(0,0,0,0.12);
  padding: 6px 6px;
  vertical-align: top;
}
.chemo-calendar th {
  text-align: center;
  background-color: #111827;
  color: #ffffff;
  font-weight: 750;
  padding: 8px 6px;
}
.chemo-calendar .cell-date { text-align: right; font-weight: 750; margin-bottom: 2px; }
.chemo-calendar .cell-day  { font-style: italic; opacity: 0.9; margin-bottom: 4px; }
.chemo-calendar .cell-med  { font-weight: 750; }
.chemo-calendar .cell-rest { opacity: 0.6; }

hr { margin-top: 0.9rem; margin-bottom: 0.9rem; opacity: 0.35; }
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
    st.title("Chemotherapy Regimen Tools")
    st.write("Maintain a regimen bank and generate patient-facing chemotherapy calendars.")

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.subheader("Regimen Builder")
        st.markdown(
            """
- Create and standardize regimens  
- Use existing regimens as templates when helpful  
- Store selection notes to distinguish similar regimens
"""
        )
    with c2:
        st.subheader("Calendar Generator")
        st.markdown(
            """
- Generate an in-page preview  
- Export a formatted calendar file  
- Defaults to the regimen you just saved
"""
        )

# NOTE: page_builder is unchanged from what you pasted (kept as-is)
# (You can paste your existing page_builder here — leaving out for brevity would be bad,
# so I’m including it exactly as you provided.)

def page_builder(bank: RegimenBank) -> None:
    _init_workflow_state()
    st.title("Regimen Builder")

    mode = st.session_state["builder_mode"]

    if mode == "start":
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

        return

    if mode == "template":
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
        q = st.text_input("Search", value="", placeholder="Search regimens (name or notes)…", key="rb_tpl_q").strip().lower()

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

        return

    left, right = st.columns([2.8, 2.2], gap="large")

    with left:
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

    with right:
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

def page_calendar(bank: RegimenBank) -> None:
    st.title("Calendar Generator")

    off, on = list_regimens_grouped(bank)
    if not off and not on:
        st.info("No regimens available. Create regimens in Regimen Builder first.")
        return

    # ---------- stable state for calendar inputs ----------
    st.session_state.setdefault("cal_group", "Off protocol")
    st.session_state.setdefault("cal_search", "")
    st.session_state.setdefault("cal_regimen_name", None)

    # Title state (user-facing doc title; does NOT rename regimen in bank)
    st.session_state.setdefault("cal_title_seeded_for", None)  # regimen name last used to seed
    # NOTE: we intentionally do NOT setdefault("cal_title", "") here,
    # because we want the widget to be able to re-seed cleanly by popping the key.

    st.session_state.setdefault("cal_start", dt.date.today())
    st.session_state.setdefault("cal_cycle_len", 28)
    st.session_state.setdefault("cal_phase", "Cycle")
    st.session_state.setdefault("cal_cycle_num", 1)
    st.session_state.setdefault("cal_note", "")

    # ---------- 1) Regimen (FULL WIDTH) ----------
    st.subheader("1) Regimen")

    st.radio(
        "Group",
        options=["Off protocol", "On study"],
        key="cal_group",
        horizontal=True,
    )

    candidates = off if st.session_state["cal_group"] == "Off protocol" else on
    if not candidates:
        st.warning(f"No {st.session_state['cal_group'].lower()} regimens found.")
        return

    # Filter tucked away so the page doesn’t look like a control panel
    with st.expander("Filter regimens", expanded=False):
        st.text_input(
            "Search",
            key="cal_search",
            placeholder="Type to filter by regimen name or selection notes…",
        )
    q = (st.session_state.get("cal_search") or "").strip().lower()

    regs = candidates
    if q:
        regs = [
            r for r in regs
            if q in r.name.lower() or q in (r.notes or "").lower()
        ]

    if not regs:
        st.warning("No matching regimens.")
        return

    reg_map_all = {r.name: r for r in candidates}
    filtered_names = [r.name for r in regs]

    # Keep a stable selection even when switching groups/filters
    active = st.session_state.get("active_regimen_name")
    if st.session_state["cal_regimen_name"] not in filtered_names:
        st.session_state["cal_regimen_name"] = active if active in filtered_names else filtered_names[0]

    def _select_regimen(name: str) -> None:
        st.session_state["cal_regimen_name"] = name

        # IMPORTANT: force title to re-seed next run (auto-populate behavior)
        st.session_state.pop("cal_title", None)
        st.session_state["cal_title_seeded_for"] = None

    selected_name = st.session_state["cal_regimen_name"]
    reg = reg_map_all[selected_name]

    # Two-panel selector: left list (with note snippets), right full notes/details
    pick_col, notes_col = st.columns([1.6, 2.4], gap="large")

    with pick_col:
        # Scrollable pick list with visible note snippets (no dropdown)
        with st.container(height=420, border=True):
            for r in regs:
                is_sel = (r.name == st.session_state["cal_regimen_name"])
                btn_label = f"✅ {r.name}" if is_sel else r.name

                if st.button(btn_label, use_container_width=True, key=f"cal_pick_{r.name}"):
                    _select_regimen(r.name)
                    st.rerun()

                sn = _note_snip(r.notes, n=140)
                if sn:
                    st.caption(sn)
                else:
                    st.caption(" ")
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # Resolve selection after possible rerun-triggering click
    selected_name = st.session_state["cal_regimen_name"]
    reg = reg_map_all[selected_name]

    with notes_col:
        st.markdown("**Selection notes (full)**")
        if reg.notes and reg.notes.strip():
            st.write(reg.notes)
        else:
            st.caption("No selection notes for this regimen.")

        st.markdown("---")
        st.write(f"**Status:** {'On study' if reg.on_study else 'Off protocol'}")
        if reg.disease_state:
            st.write(f"**Disease state:** {reg.disease_state}")

    # --- Calendar title: auto-populate from regimen, but still editable ---
    # If regimen changed since last seed, reset the widget by popping the key BEFORE rendering it.
    if st.session_state.get("cal_title_seeded_for") != reg.name:
        st.session_state.pop("cal_title", None)  # <- key move that restores “auto-populate”
        st.session_state["cal_title_seeded_for"] = reg.name

    st.text_input(
        "Calendar title (for the document)",
        key="cal_title",
        value=reg.name,  # used only when key is newly created (after pop)
        help="This does not rename the regimen in the bank. It only changes the calendar document title.",
    )

    st.markdown("---")

    # ---------- 2) Cycle + preview and 3) Export ----------
    col_cycle, col_export = st.columns([4.8, 2.6], gap="large")

    with col_cycle:
        st.subheader("2) Cycle + preview")

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

        st.markdown("---")
        st.text_input("Optional note", key="cal_note", placeholder="e.g., ‘Hold venetoclax if ANC < …’")

        cal_title = (st.session_state.get("cal_title") or reg.name).strip()

        # Don’t mutate the bank regimen name; just swap the title for preview/export
        reg_for_preview = Regimen(
            name=cal_title,
            disease_state=reg.disease_state,
            on_study=reg.on_study,
            notes=reg.notes,
            therapies=reg.therapies,
        )

        render_calendar_preview(
            reg=reg_for_preview,
            start=st.session_state["cal_start"],
            cycle_len=int(st.session_state["cal_cycle_len"]),
            label=label,
            note=(st.session_state["cal_note"].strip() or None),
        )

    with col_export:
        st.subheader("3) Export")
        st.write("Generates a formatted calendar matching the preview.")

        cycle_num = st.session_state["cal_cycle_num"] if st.session_state["cal_phase"] == "Cycle" else None
        label = _cycle_label_from_inputs(st.session_state["cal_phase"], cycle_num)

        if st.button("Generate calendar", type="primary", use_container_width=True, key="cal_generate"):
            tmp_path = Path("calendar_preview.docx")

            cal_title = (st.session_state.get("cal_title") or reg.name).strip()
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
