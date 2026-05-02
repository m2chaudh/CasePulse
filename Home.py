"""CasePulse — entrypoint. Initializes session, runs setup/PIN gates, then dispatches via st.navigation."""

from pathlib import Path
import sys
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from casepulse.storage.database import Database
from casepulse.config import Config
from casepulse.setup_wizard import is_setup_complete


def _init_session():
    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "config" not in st.session_state:
        st.session_state.config = Config()


_init_session()

# First-run setup gate — only show the Setup page until setup is complete.
if not is_setup_complete():
    st.warning("Welcome to CasePulse. Please complete initial setup.")
    setup_only = st.navigation([
        st.Page("pages_modules/setup.py", title="Setup"),
    ])
    setup_only.run()
    st.stop()

# PIN lock gate — must pass before any page is shown.
from casepulse.legal.pin_lock import render_pin_gate
if not render_pin_gate(st.session_state.db):
    st.stop()

# Inject reading-friendly CSS once per app render. Streamlit's `nav.run()`
# below executes the active page in the same script run, so the <style>
# block is already in the DOM when each page renders.
from casepulse.case_theory.ui.reading_styles import inject_global
inject_global()

# Theme picker in the sidebar — visible on every page so users can
# experiment without hunting through Setup.
with st.sidebar:
    st.markdown("---")
    with st.expander("🎨 Theme", expanded=False):
        from casepulse.ui.themes import render_theme_picker
        render_theme_picker(st.session_state.db, location="main")

nav = st.navigation({
    "Setup": [
        st.Page("pages_modules/setup.py",            title="Setup",            icon=":material/key:"),
        st.Page("pages_modules/accounts.py",         title="Accounts",         icon=":material/mail:"),
        st.Page("pages_modules/data_repairs.py",     title="Data Repairs",     icon=":material/build:"),
    ],
    "Data Sources": [
        st.Page("pages_modules/discover_senders.py", title="Discover Senders"),
        st.Page("pages_modules/fetch_emails.py",     title="Fetch Emails"),
        st.Page("pages_modules/import_chats.py",     title="Import Chats"),
        st.Page("pages_modules/documents.py",        title="Documents"),
    ],
    "Workspace": [
        st.Page("pages_modules/case_binder.py",      title="Case Binder", default=True),
        st.Page("pages_modules/dashboard.py",        title="Dashboard"),
        st.Page("pages_modules/cases.py",            title="Cases"),
        st.Page("pages_modules/witnesses.py",        title="Witnesses"),
        st.Page("pages_modules/case_theory.py",      title="Case Theory"),
    ],
    "Find & Reason": [
        st.Page("pages_modules/search.py",           title="Search"),
        st.Page("pages_modules/ask.py",              title="Ask"),
        st.Page("pages_modules/contradictions.py",   title="Contradictions"),
    ],
    "Export": [
        st.Page("pages_modules/export.py",           title="Export"),
        st.Page("pages_modules/timeline.py",         title="Timeline (HTML)"),
    ],
})
nav.run()
