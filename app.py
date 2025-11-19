import os
from pathlib import Path
import datetime as dt

import streamlit as st

from regimenbank import (
    RegimenBank,
    Regimen,
    Chemotherapy,
    make_calendar_text,
    export_calendar_docx,
)

# ---------- CONFIG ----------
DB_PATH = Path("regimenbank.db")
LOGO_PATH = Path("ucm.png")  # optional logo in UI header

VALID_USER = "honc25"
VALID_PASS = "Chemo!"

st.set_page_config(
    page_title="Chemo Calendar ",
    layout="wide",
)


# ---------- AUTH ----------
def require_login():
    if "auth_ok" not in st.session_state:
        st.session_state["auth_ok"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None

    if st.session_state["auth_ok"]:
        return  # already logged in

    st.markdown(
        """
        <style>
        .login-card {
            padding: 2rem 2.5rem;
            border-radius: 0.75rem;
            border: 1px solid #dddddd;
            background-color: #fafafa;
            max-width: 420px;
            margin-left: auto;
            margin-right: auto;
            margin-top: 4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("### 🔐 Chemotherapy Regimen Calendar Login")
    st.caption("Access restricted to HONC pharmacy team.")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

        if submitted:
            if username == VALID_USER and password == VALID_PASS:
                st.session_state["auth_ok"] = True
                st.session_state["username"] = username
                st.success("Login successful.")
                st.markdown("</div>", unsafe_allow_html=True)
                st.rerun()
            else:
                st.error("Invalid username or password.")

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


require_login()


# ---------- DB SINGLETON ----------
@st.cache_resource
def get_bank():
    return RegimenBank(DB_PATH)


bank = get_bank()


# ---------- HEADER ----------
top_cols = st.columns([3, 1])
with top_cols[0]:
    st.markdown("## 🩺 Chemotherapy Regimen Calendar")
    st.caption(
        "Automate chemotherapy calendar creation"
    )
with top_cols[1]:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)

st.sidebar.title("HONC Tools")
st.sidebar.write(f"Signed in as **{st.session_state['username']}**")
if st.sidebar.button("Log out"):
    st.session_state["auth_ok"] = False
    st.session_state["username"] = None
    st.rerun()

st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigation",
    ["Overview / Preview", "Calendar Builder", "Regimen Editor"],
)


# ---------- COMMON HELPERS ----------
def _safe_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)


def _init_edit_state(selected_name: str):
    """
    Initialize st.session_state['edit_regimen'] for the chosen regimen.
    """
    if (
        "edit_regimen_loaded_for" in st.session_state
        and st.session_state["edit_regimen_loaded_for"] == selected_name
    ):
        return  # already initialized for this regimen

    if selected_name == "⟨New regimen⟩":
        reg = Regimen(name="")
    else:
        reg = bank.get_regimen(selected_name)
        if reg is None:
            reg = Regimen(name=selected_name)

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
#                 PAGE: OVERVIEW / PREVIEW
# ============================================================
if page == "Overview / Preview":
    st.subheader("📊 Regimen Overview & Preview")

    regimen_names = bank.list_regimens()
    if not regimen_names:
        st.info("No regimens in the bank yet. Use the **Regimen Editor** to create one.")
    else:
        col_sel, col_meta = st.columns([2, 1])
        with col_sel:
            selected_regimen = st.selectbox("Select regimen", regimen_names)
        with col_meta:
            st.caption("Read-only preview. Edit details in **Regimen Editor**.")

        reg = bank.get_regimen(selected_regimen)
        if not reg:
            st.error("Selected regimen not found in the bank.")
        else:
            info_cols = st.columns(2)
            with info_cols[0]:
                st.markdown("#### Regimen details")
                st.write(f"**Name:** {reg.name}")
                st.write(f"**Disease state:** {reg.disease_state or '—'}")
            with info_cols[1]:
                st.markdown("#### Notes")
                st.write(reg.notes or "—")

            st.markdown("#### Therapies")
            if not reg.therapies:
                st.write("_No therapies defined._")
            else:
                data = [
                    {
                        "Agent": t.name,
                        "Route": t.route,
                        "Dose": t.dose,
                        "Frequency": t.frequency,
                        "Duration": t.duration,
                    }
                    for t in reg.therapies
                ]
                st.dataframe(data, use_container_width=True)

            st.markdown("#### Quick calendar preview")
            with st.expander("Show 28-day Induction preview (starting today)", expanded=False):
                try:
                    today = dt.date.today()
                    preview_text = make_calendar_text(
                        reg,
                        today,
                        28,
                        "Induction",
                        note=None,
                    )
                    st.code(preview_text, language="text")
                    st.caption(
                        "This is a read-only preview. Use **Calendar Builder** to configure dates, "
                        "cycle length, notes, and download TXT/DOCX."
                    )
                except Exception as e:
                    st.error(f"Error generating preview: {e}")


# ============================================================
#                 PAGE: CALENDAR BUILDER
# ============================================================
elif page == "Calendar Builder":
    st.subheader("📅 Calendar Builder")

    regimen_names = bank.list_regimens()
    if not regimen_names:
        st.info("No regimens in the bank yet. Use the **Regimen Editor** to create one.")
    else:
        col_sel, col_note = st.columns([2, 1])
        with col_sel:
            selected_regimen = st.selectbox("Select regimen", regimen_names)
        with col_note:
            st.caption("To modify drugs, go to **Regimen Editor**.")

        reg = bank.get_regimen(selected_regimen)
        if not reg:
            st.error("Selected regimen not found in the bank.")
        else:
            st.markdown("#### Therapies in this regimen")
            if not reg.therapies:
                st.write("_No therapies defined._")
            else:
                for t in reg.therapies:
                    st.markdown(
                        f"- **{t.name}** | {t.route} | {t.dose} | {t.frequency} | {t.duration}"
                    )

            st.divider()
            st.markdown("### Calendar Settings")

            settings_cols = st.columns(2)
            with settings_cols[0]:
                start_date = st.date_input("Cycle start date", dt.date.today())
                cycle_len = st.number_input(
                    "Cycle length (days)", min_value=1, max_value=60, value=28
                )
            with settings_cols[1]:
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
                    "Calendar-specific note (optional, prints under title)",
                    value="",
                )
                note_val = inst_note.strip() or None

            st.divider()
            st.markdown("### Generate & Export")

            if st.button("Generate calendar"):
                try:
                    txt = make_calendar_text(
                        reg, start_date, int(cycle_len), cycle_label, note_val
                    )
                    st.success("Calendar generated.")

                    tab_preview, tab_export = st.tabs(["Preview", "Download"])

                    with tab_preview:
                        st.markdown("#### Text calendar preview")
                        st.code(txt, language="text")

                    with tab_export:
                        safe = _safe_filename(reg.name or "regimen")
                        basefn = f"{safe}_{cycle_label.replace(' ', '').lower()}_{start_date.isoformat()}"

                        txt_bytes = txt.encode("utf-8")
                        st.download_button(
                            "Download TXT",
                            data=txt_bytes,
                            file_name=f"{basefn}.txt",
                            mime="text/plain",
                        )

                        tmp_path = Path(basefn + ".docx")
                        ok = export_calendar_docx(
                            reg,
                            start_date,
                            int(cycle_len),
                            tmp_path,
                            cycle_label,
                            note_val,
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
                            try:
                                tmp_path.unlink(missing_ok=True)
                            except Exception:
                                pass
                        else:
                            st.error(
                                "DOCX export failed. Is python-docx installed in this environment?"
                            )
                except Exception as e:
                    st.error(f"Error generating calendar: {e}")


# ============================================================
#                 PAGE: REGIMEN EDITOR
# ============================================================
elif page == "Regimen Editor":
    st.subheader("🧪 Regimen Editor")

    existing_names = bank.list_regimens()
    regimen_options = ["⟨New regimen⟩"] + existing_names
    selected_for_edit = st.selectbox(
        "Select regimen to view / edit", regimen_options
    )

    _init_edit_state(selected_for_edit)
    ed = st.session_state["edit_regimen"]

    st.markdown("### Regimen Details")

    top_cols = st.columns(2)
    with top_cols[0]:
        ed["name"] = st.text_input("Regimen name", ed["name"])
        ed["disease_state"] = st.text_input("Disease state", ed["disease_state"])
    with top_cols[1]:
        ed["notes"] = st.text_area(
            "Regimen notes (selection aid only)",
            ed["notes"],
            height=80,
        )

    st.markdown("### Therapies")

    therapies = ed["therapies"]

    if st.button("➕ Add new agent"):
        therapies.append(
            {"name": "", "route": "", "dose": "", "frequency": "", "duration": ""}
        )

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
                "Route (IV, PO, SQ, IM, IT, etc.)",
                value=t["route"],
                key=f"t_{idx}_route",
            )
            t["dose"] = st.text_input(
                "Dose (e.g., 100 mg/m²)",
                value=t["dose"],
                key=f"t_{idx}_dose",
            )
            t["frequency"] = st.text_input(
                "Frequency (once, daily, BID, etc.)",
                value=t["frequency"],
                key=f"t_{idx}_freq",
            )
            t["duration"] = st.text_input(
                "Day map (e.g., 'Days 1-7', 'Days 1,8,15')",
                value=t["duration"],
                key=f"t_{idx}_dur",
            )
            if st.button("🗑 Remove this agent", key=f"t_{idx}_del"):
                to_delete_indices.append(idx)

    for i in sorted(to_delete_indices, reverse=True):
        if 0 <= i < len(therapies):
            del therapies[i]

    ed["therapies"] = therapies
    st.session_state["edit_regimen"] = ed

    st.divider()

    reg_obj = _build_regimen_from_state()
    exists_already = reg_obj.name and (reg_obj.name in existing_names)

    save_cols = st.columns(2)
    with save_cols[0]:
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

    with save_cols[1]:
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
                reg2 = Regimen(
                    name=new_name.strip(),
                    disease_state=reg_obj.disease_state,
                    notes=reg_obj.notes,
                    therapies=list(reg_obj.therapies),
                )
                bank.upsert_regimen(reg2)
                st.success(f"Saved a new regimen as '{reg2.name}'.")
                st.session_state.pop("edit_regimen_loaded_for", None)
