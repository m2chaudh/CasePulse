"""Shared page initialization — database, config, PIN gate."""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def init_page():
    """Initialize database, config, and PIN gate for any page.

    Returns (db, config) if unlocked, or calls st.stop() if locked.
    """
    from casepulse.storage.database import Database
    from casepulse.config import Config

    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "config" not in st.session_state:
        st.session_state.config = Config()

    db = st.session_state.db
    config = st.session_state.config

    # PIN gate
    from casepulse.legal.pin_lock import render_pin_gate
    if not render_pin_gate(db):
        st.stop()

    return db, config
