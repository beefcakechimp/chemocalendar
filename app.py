import os
from pathlib import Path
import datetime as dt
import io

import streamlit as st

from regimenbank import (
    RegimenBank,
    Regimen,
    Chemotherapy,
    compute_calendar_grid,
    make_calendar_text,
    export_calendar_docx,
)

# ---------- CONFIG ----------
DB_PATH = Path("regimenbank.db")
LOGO_PATH = Path("ucm.png")  # for GUI header
APP_PASSWORD = os.getenv("CALENDAR_APP_PASSWORD")  # optional simple auth

st.set_page_config(
    page_title="Chemo Regimen Calendar",
    layout="wide",
)

# ---------- SIMPLE AUTH (optional) ----------
if APP_PASSWORD:
    pwd = st.sidebar.text_input("Password", type="password")
    if pwd != APP_PASSWORD:
        st.title("🔐 Chemotherapy Regimen Calendar")
        st.warning("Enter the correct password in the sidebar to access the app.")
        st.stop()

# ---------- DB SINGLETON ----------
@st.cache_resource
def get_bank():
    return RegimenBank(DB_PATH)

bank = get_bank()

# ---------- HEADER ----------
cols = st.columns([3, 1])
with cols[0]:
    st.title("🩺 Chemotherapy Regimen Calendar")
    st.caption("SQLite-backed regimen bank + calendar generator")
with cols[1]:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=True)

st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Calendar Builder", "Regimen Editor"],
)


# ============================================================
#                       HELPERS
# ============================================================
def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)


def _init_edit_state(selected_name: str):
    """
    Initialize st.session_state['edit_regimen'] for the chosen regimen.
    """
    if "edit_regimen_loaded_for" in st.session_state and \
       st.session_state["edit_regimen_loaded_for"] == selected_name:
        return  # already initialized for this regimen

    if selected_name == "⟨New regimen⟩":
        reg = Regimen(name="")
    else:
        reg = bank.get_regimen(selected_name)
        if reg is None:
            reg = Regimen(name=selected_name)

    # Build therapy list as dicts for easier editing
    therapies = []
    for t in reg.therapies:
        therapies.append(
            {
                "name": t.name,
                "route": t.route,
                "dose": t.dose,
                "frequency": t.frequency,
                "duration": t.duration,
            }
        )

    st.session_state["edit_regimen"] = {
        "name": reg.name,
        "disease_state": reg.disease_state or "",
        "notes": reg.notes or "",
        "therapies": therapies,
    }
    st.session_state["edit_regimen_loaded_for"] = selected_name


def _build_regimen_from_state() -> Regimen:
    """
    Turn st.session_state['edit_regimen'] into a Regimen object.
    """
    ed = st.session_state["edit_regimen"]
    reg = Regimen(
        name=ed["name"].strip(),
        disease_state=ed["disease_state"].strip() or None,
        notes=ed["notes"].strip() or None,
        therapies=[],
    )

    for t in ed["therapies"]:
        # Skip completely blank rows
        if not t["name"].strip():
            continue
        reg.therapies.append(
            Chemotherapy(
                name=t["name"].strip(),
                route=t["route"].strip(),
                dose=t["dose"].strip(),
                frequency=t["frequency"].strip(),
                duration=t["duration"].strip(),
            )
        )
    return reg


# ============================================================
#                     PAGE: CALENDAR BUILDER
# ============================================================
if page == "Calendar Builder":
    st.subheader("📅 Calendar Builder")

    regimen_names = bank.list_regimens()
    col_sel, col_note = st.columns([2, 1])
    with col_sel:
        selected_regimen = st.selectbox("Select regimen", regimen_names)
    with col_note:
        st.caption("Use the Regimen Editor to modify.")

    reg = bank.get_regimen(selected_regimen)
    if not reg:
        st.error("Selected regimen not found in the bank.")
        st.stop()

    st.markdown("Therapies in this regimen")
    for t in reg.therapies:
        st.markdown(
            f"- **{t.name}** | {t.route} | {t.dose} | {t.frequency} | {t.duration}"
        )

    st.divider()
    st.markdown("Calendar Settings")

    col_left, col_right = st.columns(2)
    with col_left:
        start_date = st.date_input("Cycle start date", dt.date.today())
        cycle_len = st.number_input(
            "Cycle length (days)", min_value=1, max_value=60, value=28
        )
    with col_right:
        phase = st.radio(
            "Phase",
            ["Cycle #", "Induction"],
            horizontal=True,
        )
        if phase == "Cycle #":
            cycle_number = st.number_input("Cycle number", min_value=1, value=1)
            cycle_label = f"Cycle {cycle_number}"
        else:
            cycle_label = "Induction"

        inst_note = st.text_input(
            "Calendar-specific note (prints under title, optional)", value=""
        )
        note_val = inst_note.strip() or None

    st.divider()
    if st.button("Generate calendar"):
        try:
            txt = make_calendar_text(
                reg, start_date, int(cycle_len), cycle_label, note_val
            )
            st.success("Calendar generated.")

            st.markdown("#### Text Calendar Preview")
            st.code(txt, language="text")

            # TXT download
            safe = _safe_filename(reg.name or "regimen")
            basefn = f"{safe}_{cycle_label.replace(' ', '').lower()}_{start_date.isoformat()}"

            txt_bytes = txt.encode("utf-8")
            st.download_button(
                "Download TXT",
                data=txt_bytes,
                file_name=f"{basefn}.txt",
                mime="text/plain",
            )

            # DOCX download (in-memory buffer)
            tmp_path = Path(basefn + ".docx")
            ok = export_calendar_docx(
                reg, start_date, int(cycle_len), tmp_path, cycle_label, note_val
            )
            if ok and tmp_path.exists():
                with open(tmp_path, "rb") as f:
                    docx_bytes = f.read()
                st.download_button(
                    "Download DOCX",
                    data=docx_bytes,
                    file_name=f"{basefn}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                # Clean up temp file
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                st.error("DOCX export failed. Is python-docx installed in this env?")
        except Exception as e:
            st.error(f"Error generating calendar: {e}")


# ============================================================
#                     PAGE: REGIMEN EDITOR
# ============================================================
elif page == "Regimen Editor":
    st.subheader("🧪 Regimen Editor")

    existing_names = bank.list_regimens()
    regimen_options = ["⟨New regimen⟩"] + existing_names
    selected_for_edit = st.selectbox("Select regimen to view / edit", regimen_options)

    # Initialize edit state for this regimen
    _init_edit_state(selected_for_edit)
    ed = st.session_state["edit_regimen"]

    # --- Top-level fields ---
    st.markdown("### Regimen Details")

    col1, col2 = st.columns(2)
    with col1:
        ed["name"] = st.text_input("Regimen name", ed["name"])
        ed["disease_state"] = st.text_input("Disease state", ed["disease_state"])
    with col2:
        ed["notes"] = st.text_area(
            "Regimen notes (selection aid only)",
            ed["notes"],
            height=80,
        )

    st.markdown("### Therapies")

    therapies = ed["therapies"]

    # Button to add a new blank therapy row
    if st.button("➕ Add new agent"):
        therapies.append(
            {"name": "", "route": "", "dose": "", "frequency": "", "duration": ""}
        )

    # Render each therapy in an expander
    to_delete_indices = []
    for idx, t in enumerate(therapies):
        label = t["name"].strip() or f"Agent {idx + 1}"
        with st.expander(f"{idx + 1}. {label}", expanded=True):
            t["name"] = st.text_input(
                "Agent name",
                value=t["name"],
                key=f"t_{idx}_name",
            )
            t["route"] = st.text_input(
                "Route (e.g. IV, PO, SQ, IM, IT)",
                value=t["route"],
                key=f"t_{idx}_route",
            )
            t["dose"] = st.text_input(
                "Dose (e.g. 100 mg/m2)",
                value=t["dose"],
                key=f"t_{idx}_dose",
            )
            t["frequency"] = st.text_input(
                "Frequency (free text: once, daily, BID, etc.)",
                value=t["frequency"],
                key=f"t_{idx}_freq",
            )
            t["duration"] = st.text_input(
                "Day map for calendar (e.g. 'Days 1-7' or 'Days 1,8,15')",
                value=t["duration"],
                key=f"t_{idx}_dur",
            )
            if st.button("🗑 Remove this agent", key=f"t_{idx}_del"):
                to_delete_indices.append(idx)

    # Apply deletions (from last to first to not shift indices incorrectly)
    for i in sorted(to_delete_indices, reverse=True):
        if 0 <= i < len(therapies):
            del therapies[i]

    # Write therapies back into edit state
    ed["therapies"] = therapies
    st.session_state["edit_regimen"] = ed

    st.divider()

    # --- Save / Save As controls ---
    reg_obj = _build_regimen_from_state()
    exists_already = reg_obj.name and (reg_obj.name in existing_names)

    col_save, col_saveas = st.columns(2)

    with col_save:
        st.markdown("#### Save (overwrite existing)")

        if not reg_obj.name:
            st.info("Enter a regimen name to enable saving.")
        else:
            if exists_already:
                st.warning(
                    f"Regimen named **'{reg_obj.name}'** already exists and will be overwritten."
                )
                confirm_overwrite = st.checkbox(
                    "I understand this will overwrite the existing regimen.",
                    key="confirm_overwrite",
                )
            else:
                st.caption("This will create a new regimen with this name.")

            if st.button("💾 Save regimen"):
                if exists_already and not confirm_overwrite:
                    st.error("Check the overwrite box to overwrite the existing regimen.")
                else:
                    bank.upsert_regimen(reg_obj)
                    st.success(f"Regimen '{reg_obj.name}' saved to regimen bank.")

    with col_saveas:
        st.markdown("#### Save As (create new copy)")
        new_name = st.text_input(
            "New regimen name (Save As)",
            value="",
            key="save_as_name",
        )
        if st.button("📁 Save As new regimen"):
            if not new_name.strip():
                st.error("Enter a new regimen name for Save As.")
            else:
                # Clone with new name
                reg2 = Regimen(
                    name=new_name.strip(),
                    disease_state=reg_obj.disease_state,
                    notes=reg_obj.notes,
                    therapies=list(reg_obj.therapies),
                )
                bank.upsert_regimen(reg2)
                st.success(f"Saved a new regimen as '{reg2.name}'.")
                # Refresh options next run
                st.session_state.pop("edit_regimen_loaded_for", None)
