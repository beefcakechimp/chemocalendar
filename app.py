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

# ---------------- page config + light styling ----------------
st.markdown("""
<style>
section[data-testid="stSidebar"] button {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 700 !important;
  padding: 0.7rem 0.9rem !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
}
section[data-testid="stSidebar"] button:hover {
  transform: translateY(-1px);
}

/* Make primary actions (like export) unmistakable */
button[kind="primary"] {
  font-weight: 800 !important;
  padding: 0.75rem 0.95rem !important;
  border-radius: 12px !important;
}
</style>
""", 

    unsafe_allow_html=True,
)

# ---------------- config ----------------
APP_PASSWORD = "honc25"  # change as needed


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

    st.write(
        "Enter the access key"
    )

    pw = st.text_input("Access key", type="password")

    col1, _ = st.columns([1, 3])
    with col1:
        if st.button("Sign in", type="primary"):
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
    if first_sun.year == last_sat.year:
        year_str = str(first_sun.year)
    else:
        year_str = f"{first_sun.year}–{last_sat.year}"

    st.markdown(f"**{reg.name} — {label}**")
    st.markdown(f"{months} {year_str}")
    if note:
        st.markdown(f"*{note}*")

    header_names = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]

    html = ['<table class="chemo-calendar">']
    # Header row
    html.append("<tr>")
    for dname in header_names:
        html.append(f"<th>{dname}</th>")
    html.append("</tr>")

    import calendar as calmod
    for week in grid:
        html.append("<tr>")
        for cell in week:
            date = cell["date"]
            cd = cell["cycle_day"]
            labels = cell["labels"] or []

            html.append("<td>")
            html.append(
                f'<div class="cell-date">{calmod.month_abbr[date.month]} {date.day}</div>'
            )
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

    st.write(
        "Use this interface to maintain a regimen bank and generate patient-facing "
        "chemotherapy calendars."
    )

    st.subheader("Sections")
    st.markdown(
        """
**Regimen Builder**

- Create or edit chemotherapy regimens  
- Set disease state, protocol status, and notes  
- Add or modify therapy components (route, dose, schedule)

**Calendar Generator**

- Select a regimen from the bank  
- Choose cycle start date, cycle length, and phase  
- Review an in-page calendar preview  
- Optionally download a formatted calendar file for printing or upload
"""
    )


def page_builder(bank: RegimenBank) -> None:
    st.title("Regimen Builder")

    # Track whether therapy editor is visible
    if "edit_therapies_open" not in st.session_state:
        st.session_state["edit_therapies_open"] = False

    # 3-column layout: selection, editing, summary
    col_sel, col_edit, col_summary = st.columns((1.5, 4.5, 2.5), gap="medium")

    # -------- left: selection + delete --------
    with col_sel:
        st.subheader("Select regimen")

        names = bank.list_regimens()
        selected_name: Optional[str] = None
        if not names:
            st.info("No regimens found. Use the middle column to create a new regimen.")
        else:
            names_sorted = sorted(names, key=str.lower)
            selected_name = st.selectbox(
                "Existing regimens",
                options=["(none)"] + names_sorted,
                index=0,
            )
            if selected_name == "(none)":
                selected_name = None

        st.markdown("---")

        # Delete regimen
        if selected_name:
            st.subheader("Delete regimen")
            st.write(
                "Type the regimen name to confirm deletion."
            )
            confirm_text = st.text_input(
                "Confirmation",
                placeholder=selected_name,
                key="delete_confirm",
            )
            if st.button("Delete regimen"):
                if confirm_text.strip() == selected_name:
                    ok = bank.delete_regimen(selected_name)
                    if ok:
                        st.success(f"Deleted regimen '{selected_name}'.")
                        st.session_state.pop("delete_confirm", None)
                        st.rerun()
                    else:
                        st.error("Regimen not found.")
                else:
                    st.error("Confirmation text does not match regimen name.")

    # Load current regimen or create empty
    if selected_name:
        base = bank.get_regimen(selected_name)
    else:
        base = None

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
        st.subheader("Regimen details")

        reg_name = st.text_input("Regimen name", value=reg_name)
        disease_state_val = st.text_input("Disease state", value=disease_state_val)
        on_study_val = st.radio(
            "Protocol status",
            options=["Off protocol", "On study"],
            index=1 if on_study_val else 0,
            horizontal=True,
        ) == "On study"
        notes_val = st.text_area(
            "Notes (shown only on selection lists)",
            value=notes_val,
            height=80,
        )

        st.markdown("---")
        col_save1, col_save2 = st.columns(2)

        with col_save1:
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
                    st.success(f"Saved '{reg.name}' to the regimen bank.")

        with col_save2:
            new_name = st.text_input(
                "Save as new regimen name",
                value="",
                placeholder="Leave blank to skip",
                key="save_as_name",
            )
            if st.button("Save as new regimen", use_container_width=True):
                if not new_name.strip():
                    st.error("New regimen name is required for Save as new.")
                else:
                    reg = Regimen(
                        name=new_name.strip(),
                        disease_state=disease_state_val.strip() or None,
                        on_study=on_study_val,
                        notes=notes_val.strip() or None,
                        therapies=therapies,
                    )
                    bank.upsert_regimen(reg)
                    st.success(f"Saved new regimen '{reg.name}'.")
                    st.rerun()

        st.markdown("---")

        # Toggle therapy editor visibility
        if st.button(
            "Edit therapies",
            use_container_width=True,
        ):
            st.session_state["edit_therapies_open"] = not st.session_state[
                "edit_therapies_open"
            ]

        # Therapy editor (only if toggled on)
        if st.session_state["edit_therapies_open"]:
            st.markdown("#### Therapy editor")

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

                name_val = st.text_input(
                    "Agent name",
                    value=current.name if current else "",
                )
                route_val = st.text_input(
                    "Route (e.g. IV, PO, SQ, IM, IT)",
                    value=current.route if current else "",
                )
                dose_val = st.text_input(
                    "Dose",
                    value=current.dose if current else "",
                )
                freq_val = st.text_input(
                    "Frequency (free text: once, daily, BID, weekly …)",
                    value=current.frequency if current else "",
                )
                dur_val = st.text_input(
                    "Day map for calendar (e.g. 'Days 1–7', 'Days 1,8,15')",
                    value=current.duration if current else "",
                )
                total_doses_val = st.text_input(
                    "Total doses (optional; leave blank to auto-calculate)",
                    value=(
                        str(current.total_doses)
                        if current and current.total_doses is not None
                        else ""
                    ),
                )

                submitted = st.form_submit_button("Apply therapy")

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
                                st.warning(
                                    "Could not parse total doses as an integer; "
                                    "leaving it auto-calculated."
                                )
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
                        st.success("Therapy updated in this session.")

            # remove therapy
            if therapies:
                with st.expander("Remove a therapy"):
                    idx_to_remove = st.selectbox(
                        "Select therapy to remove",
                        options=["(none)"] + list(range(len(therapies))),
                        format_func=lambda x: "(none)" if x == "(none)" else therapies[x].name,
                    )
                    if idx_to_remove != "(none)":
                        if st.button("Remove selected therapy"):
                            removed = therapies.pop(idx_to_remove)
                            st.success(f"Removed {removed.name} from this regimen.")

    # -------- right: summary (including therapies) --------
    with col_summary:
        st.subheader("Summary")

        if reg_name.strip():
            st.markdown(f"**Name:** {reg_name.strip()}")
        else:
            st.markdown("**Name:** (new regimen)")

        if disease_state_val.strip():
            st.markdown(f"**Disease state:** {disease_state_val.strip()}")
        if on_study_val:
            st.markdown("**Protocol status:** On study")
        else:
            st.markdown("**Protocol status:** Off protocol")

        if notes_val.strip():
            st.markdown("**Notes**")
            st.markdown(notes_val.strip())

        st.markdown("---")
        st.markdown("**Therapies**")

        if therapies:
            for t in therapies:
                line = (
                    f"- **{t.name}** ({t.route}) — {t.dose}; "
                    f"{t.frequency}; {t.duration}"
                )
                st.markdown(line)
        else:
            st.write("No therapies defined for this regimen yet.")


def page_calendar(bank: RegimenBank) -> None:
    st.title("Calendar Generator")

    off, on = list_regimens_grouped(bank)

    if not off and not on:
        st.info("No regimens available. Use the Regimen Builder to create regimens first.")
        return

    # 3-column layout: regimen selection, cycle settings + preview, export
    col_reg, col_cycle, col_export = st.columns((1.5, 4.5, 2.5), gap="medium")

    # -------- left: regimen selection --------
    with col_reg:
        st.subheader("Regimen")

        regimen_type = st.radio(
            "Regimen group",
            options=["Off protocol", "On study"],
            index=0,
            horizontal=False,
        )

        candidates = off if regimen_type == "Off protocol" else on
        if not candidates:
            st.warning(f"No {regimen_type.lower()} regimens found.")
            return

        reg_map = {r.name: r for r in candidates}
        selected_name = st.selectbox(
            "Select regimen",
            options=sorted(reg_map.keys(), key=str.lower),
        )
        reg = reg_map[selected_name]

        st.markdown("---")
        st.write("Protocol status:")
        st.write("On study" if reg.on_study else "Off protocol")

    # -------- middle: cycle settings + preview --------
    with col_cycle:
        st.subheader("Cycle settings")

        c1, c2, c3 = st.columns(3)
        with c1:
            start_date = st.date_input("Cycle start date", value=dt.date.today())
        with c2:
            cycle_len = st.number_input("Cycle length (days)", min_value=1, value=28)
        with c3:
            phase = st.selectbox(
                "Phase",
                options=["Cycle", "Induction"],
                index=0,
            )
            cycle_num: Optional[int] = None
            if phase == "Cycle":
                cycle_num = st.number_input(
                    "Cycle number",
                    min_value=1,
                    value=1,
                    step=1,
                )

        label = _cycle_label_from_inputs(
            "Induction" if phase == "Induction" else "Cycle",
            cycle_num,
        )

        st.text_input("Calendar label", value=label, disabled=True)

        st.markdown("---")
        st.subheader("Calendar preview")

        note = st.text_input(
            "Optional note (e.g. clinic contact or key instructions)",
            value="",
        )

        render_calendar_preview(
            reg=reg,
            start=start_date,
            cycle_len=int(cycle_len),
            label=label,
            note=note or None,
        )

    # -------- right: export --------
    with col_export:
        st.subheader("Calendar file")

        st.write(
            "Generate a formatted calendar document matching the preview. "
            "This file can be printed or uploaded to the chart."
        )

        if st.button("Generate calendar file", type="primary", use_container_width=True):
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
                st.error(
                    "Calendar export failed. Ensure python-docx is installed."
                )
            else:
                data = tmp_path.read_bytes()
                tmp_path.unlink(missing_ok=True)
                st.success("Calendar file generated.")
                st.download_button(
                    label="Download calendar file",
                    data=data,
                    file_name=f"{reg.name.replace(' ', '_')}_{label.replace(' ', '')}_{start_date.isoformat()}.docx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                )


# ---------------- main ----------------
def main() -> None:
    require_login()

    if "section" not in st.session_state:
        st.session_state["section"] = "Main"

    with st.sidebar:
        st.title("Navigation")

        if st.button("Main", use_container_width=True):
            st.session_state["section"] = "Main"
        if st.button("Regimen Builder", use_container_width=True):
            st.session_state["section"] = "Regimen Builder"
        if st.button("Calendar Generator", use_container_width=True):
            st.session_state["section"] = "Calendar Generator"

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
