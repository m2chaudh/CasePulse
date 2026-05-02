"""First-run setup wizard — module selection."""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Setup", page_icon="CP", layout="wide")

from casepulse.setup_wizard import (
    MODULES, is_setup_complete, load_installed_modules,
    save_installed_modules, get_default_selections,
)
from casepulse.case_theory.ui import page_help
from casepulse.storage.database import Database
from casepulse.ui.workflow_help import (
    compute_workflow_state, render_workflow_help, WorkflowState,
)

# If setup is already done, show settings view
setup_done = is_setup_complete()

# Render workflow help at the top of the page
_db = Database()
with _db._get_conn() as _conn:
    _row = _conn.execute("SELECT id FROM cases ORDER BY id LIMIT 1").fetchone()
if _row:
    _wstate = compute_workflow_state(_db, case_id=_row["id"])
    render_workflow_help(
        _wstate,
        default_open=not (_wstate.has_email or _wstate.has_document),
    )
else:
    render_workflow_help(WorkflowState(), default_open=True)

if setup_done:
    st.markdown("## Module Settings")
    st.markdown("Enable or disable optional modules. Changes take effect on next restart.")
else:
    st.markdown("## Welcome to CasePulse")
    st.markdown("Select the modules you want to enable. You can change this later in Setup.")
    st.info("Core features (Accounts, Email Fetch, Timeline, Import Chats, Cases, Export) are always included.")

page_help.render("setup")

current = load_installed_modules() if setup_done else get_default_selections()

st.divider()

selections = {}
total_size = 200  # Core size in MB

for key, mod in MODULES.items():
    col1, col2, col3 = st.columns([0.5, 3, 1])
    with col1:
        enabled = st.checkbox(
            mod["name"],
            value=current.get(key, mod["default"]),
            key=f"mod_{key}",
            label_visibility="collapsed",
        )
        selections[key] = enabled
    with col2:
        st.markdown(f"**{mod['name']}**")
        st.caption(mod["description"])
    with col3:
        st.caption(f"~{mod['size']}")

    if enabled:
        size_str = mod["size"].split()[0]
        try:
            total_size += int(size_str)
        except ValueError:
            pass

st.divider()
st.markdown(f"**Estimated install size:** ~{total_size} MB")

if setup_done:
    if st.button("Save Changes", type="primary"):
        save_installed_modules(selections)
        st.success("Module settings saved. Restart CasePulse for changes to take effect.")
else:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Get Started", type="primary"):
            save_installed_modules(selections)
            st.balloons()
            st.success("Setup complete! Navigate to **Accounts** to connect your email.")
            st.rerun()
    with col2:
        st.caption("You can change these settings anytime from the Setup page.")
