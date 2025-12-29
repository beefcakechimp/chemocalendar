#!/usr/bin/env python3
import datetime as dt
from pathlib import Path
from typing import Optional, List

import streamlit as st

from regimenbank import (
    RegimenBank,
    Regimen,
    Chemotherapy,
    parse_day_spec,
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
/* Page padding + typography rhythm */
[data-testid="block-container"]{
  padding-left: 2rem;
  padding-right: 2rem;
  padding-top: 1.25rem;
  padding-bottom: 1.25rem;
}

/* Stronger header hierarchy */
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

/* Sidebar buttons: stacked nav pills */
section[data-testid="stSidebar"] button {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 750 !important;
  padding: 0.72rem 0.95rem !important;
  border: 1px solid rgba(255,255,255,0.14) !important;
}
section[data-testid="stSidebar"] button:hover {
  transform: translateY(-1px);
}

/* Make primary actions unmistakable */
button[kind="primary"] {
  font-weight: 850 !important;
  padding: 0.78rem 0.95rem !important;
  border-radius: 14px !important;
}

/* Calendar preview table */
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
.chemo-calendar .cell-date {
  text-align: right;
  font-weight: 750;
  margin-bottom: 2px;
}
.chemo-calendar .cell-day {
  font-style: italic;
  opacity: 0.9;
  margin-bottom: 4px;
}
.chemo-calendar .cell-med {
  font-weight: 750;
}
.chemo-calendar .cell-rest {
  opacity: 0.6;
}

/* Reduce visual noise from markdown separators */
hr {
  margin-top: 0.9rem;
  margin-bottom: 0.9rem;
  opacity: 0.35;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- config ----------------
APP_PASSWORD = "honc25"  # change as needed

# Use a single column ratio everywhere for visual consistency
COLS_3 = [1.6, 4.8, 2.6]


# ---------------- helpers ----------------
def get_bank() -> RegimenBank:
    """Return a RegimenBank tied to the current Streamlit session."""
    db_path = DEFAULT_DB
    if "db_path" not in st.session_state or st.session_state["db_path"] != str(db_path):
        st.session_state["db_path"] = str(db_path)
        st.session_state["bank"] = RegimenBank(db_path)
    return st.session_state["bank"]


def list_regimens_grouped(bank: RegimenBank):
    """Return (off_protocol, on_study) lists of Regimen objects."""
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


def require_login() -> None:
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return

    st.title("Sign in")
    st.write("Enter the access key.")

    pw = st.text_input("Access key", type="password")

    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Sign in", type="primary", use_container_width=True):
            if pw and pw == APP_PASSWORD:
                st.session_state["authenticated"] = True
            else:
                st.error("Invalid access key.")

    st.stop()


def render_calendar_preview(
    reg: Regimen,
    start: dt.date,
    cycle_len: int,
    label: str,
    note: Optional[str],
) -> None:
    """Render a visual calendar preview in-page using compute_calendar_grid."""
    first_sun, last_sat, _, grid = compute_calendar_grid(reg, start, cycle_len)

    import calendar as pycal
    months = pycal.month_name[first_sun.month]
    if first_sun.month != last_sat.month or first_sun.year != last_sat.year:
        months += f" – {pycal.month_name[last_sat.month]}"
    year_str = str(first_sun.year) if first_sun.year == last_sat.year else f"{first_sun.year}–{last_sat.year}"

    st.markdown(f"**{reg.name} — {label}**")
    st.markdown(f"{months} {year_str}")
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


# ---------------- pages ----------------
def page_overview() -> None:
    st.title("Chemotherapy Regimen Tools")
    st.write("Maintain a regimen bank and generate patient-facing chemotherapy calendars.")

    st.subheader("Regimen Builder")
    st.markdown(
        """
- Create or edit regimens  
- Set disease state, protocol status, and notes  
- Manage therapy components (route, dose, schedule)
"""
    )

    st.subheader("Calendar Generator")
    st.markdown(
        """
- Select a regimen from the bank  
- Choose cycle start date, cycle length, and phase  
- Review an in-page calendar preview  
- Export a formatted calendar file
"""
    )


def page_builder(bank: RegimenBank) -> None:
    st.title("Regimen Builder")

    if "edit_therapies_open" not in st.session_state:
        st.session_state["edit_therapies_open"] = False

    col_sel, col_edit, col_summary = st.columns(COLS_3, gap="large")

    # -------- left: selection + delete --------
    with col_sel:
        st.subheader("Selection")

        names = bank.list_regimens()
        selected_name: Optional[str] = None
        if not names:
            st.info("No regimens found. Create one in the center panel.")
        else:
            names_sorted = sorted(names, key=str.lower)
            selected_name = st.selectbox(
                "Regimen",
                options=["(new)"] + names_sorted,
                index=0,
            )
            if selected_name == "(new)":
                selected_name = None

        st.markdown("---")

        if selected_name:
            st.subheader("Delete")
            st.write("Type the regimen name to confirm deletion.")
            confirm_text = st.text_input(
                "Confirmation",
                placeholder=selected_name,
                key="delete_confirm",
            )
            if st.button("Delete regimen", use_container_width=True):
                if confirm_text.strip() == selected_name:
                    ok = bank.delete_regimen(selected_name)
                    if ok:
                        st.success(f"Deleted '{selected_name}'.")
                        st.session_state.pop("delete_confirm", None)
                        st.rerun()
                    else:
                        st.error("Regimen not found.")
                else:
                    st.error("Confirmation text does not match.")

    # Load current regimen or create empty
    base = bank.get_regimen(selected_name) if selected_name else None

    if base is None:
        reg_name = ""
        disease_state_val = ""
        on_study_val = False
        notes_val = ""
        therapies: List[Chemotherapy] = []
    else:
        reg_name = base.name
        disease_state_val = base.disease_state or ""
        on_study_val = base.on_study
        notes_val = base.notes or ""
        therapies = [t for t in base.therapies]

    # -------- middle: details + save + therapy editor toggle --------
    with col_edit:
        st.subheader("Details")

        reg_name = st.text_input("Regimen name", value=reg_name)
        disease_state_val = st.text_input("Disease state", value=disease_state_val)
        on_study_val = st.radio(
            "Protocol status",
            options=["Off protocol", "On study"],
            index=1 if on_study_val else 0,
            horizontal=True,
        ) == "On study"
        notes_val = st.text_area("Notes", value=notes_val, height=90)

        st.markdown("---")

        # Primary actions grouped cleanly
        a1, a2 = st.columns([1, 1], gap="medium")
        with a1:
            if st.button("Save regimen", type="primary", use_container_width=True):
                if not reg_name.strip():
                    st.error("Regimen name is required.")
                else:
                    reg = Regimen(
                        name=reg_name.strip(),
                        disease_state=disease_state_val.strip() or None,
                        on_study=on_study_val,
                        notes=notes_val.strip() or None,
                        therapies=therapies,
                    )
                    bank.upsert_regimen(reg)
                    st.success(f"Saved '{reg.name}'.")

        with a2:
            new_name = st.text_input(
                "Save as",
                value="",
                placeholder="New regimen name",
                key="save_as_name",
            )
            if st.button("Save as new", use_container_width=True):
                if not new_name.strip():
                    st.error("New regimen name is required.")
                else:
                    reg = Regimen(
                        name=new_name.strip(),
                        disease_state=disease_state_val.strip() or None,
                        on_study=on_study_val,
                        notes=notes_val.strip() or None,
                        therapies=therapies,
                    )
                    bank.upsert_regimen(reg)
                    st.success(f"Saved '{reg.name}'.")
                    st.rerun()

        st.markdown("---")

        # Therapy editor toggle
        label = "Edit therapies" if not st.session_state["edit_therapies_open"] else "Close therapy editor"
        if st.button(label, use_container_width=True):
            st.session_state["edit_therapies_open"] = not st.session_state["edit_therapies_open"]

        if st.session_state["edit_therapies_open"]:
            st.subheader("Therapy editor")

            with st.form("therapy_form", clear_on_submit=False):
                edit_mode = st.checkbox("Edit existing therapy", value=False)

                if edit_mode and therapies:
                    idx = st.selectbox(
                        "Therapy to edit",
                        options=range(len(therapies)),
                        format_func=lambda i: therapies[i].name,
                    )
                    current = therapies[idx]
                else:
                    idx = None
                    current = None

                name_val = st.text_input("Agent name", value=current.name if current else "")
                route_val = st.text_input("Route", value=current.route if current else "")
                dose_val = st.text_input("Dose", value=current.dose if current else "")
                freq_val = st.text_input("Frequency", value=current.frequency if current else "")
                dur_val = st.text_input("Day map", value=current.duration if current else "")
                total_doses_val = st.text_input(
                    "Total doses (optional)",
                    value=str(current.total_doses) if current and current.total_doses is not None else "",
                )

                submitted = st.form_submit_button("Apply")

                if submitted:
                    if not name_val.strip():
                        st.error("Agent name is required.")
                    elif not route_val.strip():
                        st.error("Route is required.")
                    elif not dose_val.strip():
                        st.error("Dose is required.")
                    elif not dur_val.strip():
                        st.error("Day map is required.")
                    else:
                        td = None
                        if total_doses_val.strip():
                            try:
                                td = int(total_doses_val.strip())
                            except ValueError:
                                st.warning("Total doses must be an integer (or blank).")

                        new_t = Chemotherapy(
                            name=name_val.strip(),
                            route=route_val.strip(),
                            dose=dose_val.strip(),
                            frequency=freq_val.strip(),
                            duration=dur_val.strip(),
                            total_doses=td,
                        )
                        if edit_mode and idx is not None:
                            therapies[idx] = new_t
                        else:
                            therapies.append(new_t)
                        st.success("Updated therapy (in this session).")

            if therapies:
                with st.expander("Remove a therapy"):
                    idx_to_remove = st.selectbox(
                        "Therapy",
                        options=["(none)"] + list(range(len(therapies))),
                        format_func=lambda x: "(none)" if x == "(none)" else therapies[x].name,
                    )
                    if idx_to_remove != "(none)":
                        if st.button("Remove", use_container_width=True):
                            removed = therapies.pop(idx_to_remove)
                            st.success(f"Removed {removed.name}.")

    # -------- right: summary (including therapies) --------
    with col_summary:
        st.subheader("Summary")

        st.markdown(f"**Name:** {reg_name.strip() or '(new regimen)'}")
        if disease_state_val.strip():
            st.markdown(f"**Disease state:** {disease_state_val.strip()}")
        st.markdown(f"**Protocol status:** {'On study' if on_study_val else 'Off protocol'}")

        if notes_val.strip():
            st.markdown("---")
            st.markdown("**Notes**")
            st.write(notes_val.strip())

        st.markdown("---")
        st.markdown("**Therapies**")
        if therapies:
            for t in therapies:
                st.markdown(f"- **{t.name}** ({t.route}) — {t.dose}; {t.frequency}; {t.duration}")
        else:
            st.write("No therapies defined yet.")


def page_calendar(bank: RegimenBank) -> None:
    st.title("Calendar Generator")

    off, on = list_regimens_grouped(bank)
    if not off and not on:
        st.info("No regimens available. Create regimens in Regimen Builder first.")
        return

    col_reg, col_cycle, col_export = st.columns(COLS_3, gap="large")

    # -------- left: regimen selection --------
    with col_reg:
        st.subheader("Regimen")

        regimen_type = st.radio(
            "Group",
            options=["Off protocol", "On study"],
            index=0,
            horizontal=False,
        )

        candidates = off if regimen_type == "Off protocol" else on
        if not candidates:
            st.warning(f"No {regimen_type.lower()} regimens found.")
            return

        reg_map = {r.name: r for r in candidates}
        selected_name = st.selectbox("Select regimen", options=sorted(reg_map.keys(), key=str.lower))
        reg = reg_map[selected_name]

        st.markdown("---")
        st.write(f"**Status:** {'On study' if reg.on_study else 'Off protocol'}")

    # -------- middle: cycle settings + preview --------
    with col_cycle:
        st.subheader("Cycle")

        c1, c2, c3 = st.columns([1, 1, 1], gap="medium")
        with c1:
            start_date = st.date_input("Cycle start date", value=dt.date.today())
        with c2:
            cycle_len = st.number_input("Cycle length (days)", min_value=1, value=28)
        with c3:
            phase = st.selectbox("Phase", options=["Cycle", "Induction"], index=0)
            cycle_num: Optional[int] = None
            if phase == "Cycle":
                cycle_num = st.number_input("Cycle number", min_value=1, value=1, step=1)

        label = _cycle_label_from_inputs("Induction" if phase == "Induction" else "Cycle", cycle_num)
        st.text_input("Calendar label", value=label, disabled=True)

        st.markdown("---")
        st.subheader("Preview")

        note = st.text_input("Optional note", value="")
        render_calendar_preview(
            reg=reg,
            start=start_date,
            cycle_len=int(cycle_len),
            label=label,
            note=note or None,
        )

    # -------- right: export --------
    with col_export:
        st.subheader("Export")

        st.write("Generate a formatted calendar file matching the preview.")

        if st.button("Generate calendar", type="primary", use_container_width=True):
            tmp_path = Path("calendar_preview.docx")
            ok = export_calendar_docx(
                reg=reg,
                start=start_date,
                cycle_len=int(cycle_len),
                out_path=tmp_path,
                cycle_label=label,
                note=note or None,
            )
            if not ok:
                st.error("Export failed. Ensure python-docx is installed.")
            else:
                data = tmp_path.read_bytes()
                tmp_path.unlink(missing_ok=True)
                st.success("Calendar generated.")
                st.download_button(
                    label="Download",
                    data=data,
                    file_name=f"{reg.name.replace(' ', '_')}_{label.replace(' ', '')}_{start_date.isoformat()}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )


# ---------------- main ----------------
def main() -> None:
    require_login()

    if "section" not in st.session_state:
        st.session_state["section"] = "Main"

    section = st.session_state["section"]

    with st.sidebar:
        st.title("Navigation")

        # Active state: current page uses primary button
        if st.button("Main", type="primary" if section == "Main" else "secondary", use_container_width=True):
            st.session_state["section"] = "Main"
            st.rerun()
        if st.button("Regimen Builder", type="primary" if section == "Regimen Builder" else "secondary", use_container_width=True):
            st.session_state["section"] = "Regimen Builder"
            st.rerun()
        if st.button("Calendar Generator", type="primary" if section == "Calendar Generator" else "secondary", use_container_width=True):
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
