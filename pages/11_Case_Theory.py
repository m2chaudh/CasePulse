"""Case Theory Workbench — manual analyst page for building Allegations,
Contradictions, Arguments, and attached Evidence.

Layout: dual-pane via st.columns([1, 1]).
- Left:  Argument editor (Contradiction → Arguments → attached Evidence)
- Right: Evidence Tray (FTS5-backed search + filters + result list)

This file is the page entry-point. Implementation is split across
casepulse/case_theory/ui/ for reusability and testability.
"""
import streamlit as st
from casepulse.storage.database import Database
from casepulse.config import Config
from casepulse.case_theory.repository import (
    list_contradictions,
)
from casepulse.case_theory.ui import argument_editor
from casepulse.legal.pin_lock import render_pin_gate

st.set_page_config(page_title="Case Theory — CasePulse", layout="wide")


def _init_session():
    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "config" not in st.session_state:
        st.session_state.config = Config()


def main():
    _init_session()
    db: Database = st.session_state.db
    if not render_pin_gate(db):
        st.stop()
        return

    st.markdown("## Case Theory Workbench")

    # Case picker
    cases = db.get_cases() if hasattr(db, "get_cases") else []
    if not cases:
        st.info("No cases yet. Go to the **Cases** page to create one.")
        st.stop()
        return

    case_options = {f"{c['name']} ({c['case_type']})": c["id"] for c in cases}
    selected_label = st.sidebar.selectbox("Active case", list(case_options.keys()))
    case_id = case_options[selected_label]

    # Contradiction picker
    contradictions = list_contradictions(db, case_id=case_id)
    if not contradictions:
        st.info("No contradictions yet for this case. Use the form below to "
                "create one.")
        # Stub: a simple "create contradiction" form will be added in Task 1.2.
        st.stop()
        return

    contra_labels = {f"{c.headline} [{c.status.value}]": c.id
                     for c in contradictions}
    selected = st.sidebar.selectbox("Contradiction", list(contra_labels.keys()))
    contradiction_id = contra_labels[selected]

    # Dual-pane layout (Tasks 1.2-1.6 will fill these in)
    left, right = st.columns([1, 1])
    with left:
        st.markdown(f"### Contradiction #{contradiction_id}")
        argument_editor.render(db, contradiction_id=contradiction_id)
    with right:
        st.markdown("### Evidence Tray")
        st.write("[Tray search + result list lands in Task 1.4]")


if __name__ == "__main__":
    main()
else:
    main()
