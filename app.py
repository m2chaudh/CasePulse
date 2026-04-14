"""CasePulse — Legal Email Aggregation & Analysis Tool

Main Streamlit application entry point.
"""
import streamlit as st
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from casepulse.storage.database import Database
from casepulse.config import Config
from casepulse.setup_wizard import is_setup_complete

st.set_page_config(
    page_title="CasePulse",
    page_icon="CP",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #888;
        margin-top: -10px;
        margin-bottom: 30px;
    }
    .stat-card {
        background: #1a1a2e;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        border: 1px solid #333;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        color: #00d4ff;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #aaa;
        margin-top: 5px;
    }
    .status-ok { color: #00c853; }
    .status-warn { color: #ffd600; }
    .status-err { color: #ff1744; }
</style>
""", unsafe_allow_html=True)


def init_session():
    """Initialize session state."""
    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "config" not in st.session_state:
        st.session_state.config = Config()


def main():
    init_session()
    db: Database = st.session_state.db
    config: Config = st.session_state.config

    # First-run setup redirect
    if not is_setup_complete():
        st.markdown("## Welcome to CasePulse")
        st.info("Please complete the initial setup first.")
        st.page_link("pages/0_Setup.py", label="Go to Setup", icon=None)
        st.stop()
        return

    # PIN lock gate
    from casepulse.legal.pin_lock import render_pin_gate, is_pin_set
    if not render_pin_gate(db):
        st.stop()
        return

    # Header
    st.markdown('<p class="main-header">CasePulse</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Legal Email Aggregation & Analysis</p>', unsafe_allow_html=True)

    # Dashboard stats
    stats = db.get_stats()

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Accounts", stats["connected_accounts"])
    with col2:
        st.metric("Emails", f"{stats['total_emails']:,}")
    with col3:
        st.metric("Chat Messages", f"{stats.get('total_chat_messages', 0):,}")
    with col4:
        st.metric("Attachments", f"{stats['total_attachments']:,}")
    with col5:
        st.metric("Duplicates", f"{stats['duplicate_attachments']:,}")
    with col6:
        st.metric("Senders", stats["selected_senders"])

    st.divider()

    # Quick status
    accounts = db.get_accounts()
    if not accounts:
        st.warning("No email accounts connected. Go to **Accounts** to get started.")

        st.markdown("### Getting Started")
        st.markdown("""
        1. **Accounts** — Connect your Outlook, Hotmail, and Gmail accounts
        2. **Discover** — Scan for all contacts and select the ones relevant to your case
        3. **Fetch** — Download emails matching your senders and keywords
        4. **Timeline** — View a chronological timeline of all communications
        5. **Ask** — Query your emails with AI — get answers with exact citations
        """)
    else:
        # Show connected accounts
        st.markdown("### Connected Accounts")
        for acc in accounts:
            provider_icon = "M" if acc["provider"] == "microsoft" else "G"
            synced = acc.get("last_synced", "Never")
            st.markdown(
                f"**[{provider_icon}]** {acc['email']} — "
                f"Last synced: {synced or 'Never'}"
            )

        # Date range
        if stats["earliest_email"] and stats["latest_email"]:
            st.markdown(
                f"### Email Range\n"
                f"**{stats['earliest_email'][:10]}** to **{stats['latest_email'][:10]}**"
            )

        # Recent sync activity
        sync_history = db.get_sync_history(limit=5)
        if sync_history:
            st.markdown("### Recent Sync Activity")
            for sync in sync_history:
                status_icon = "+" if sync["status"] == "completed" else "x" if sync["status"] == "failed" else "..."
                st.markdown(
                    f"[{status_icon}] {sync['started_at']} — "
                    f"{sync['emails_fetched']} emails, {sync['attachments_downloaded']} attachments"
                )

    # Settings section
    st.divider()
    with st.expander("Settings"):
        st.markdown("#### Date Range")
        col1, col2 = st.columns(2)
        with col1:
            start = st.date_input("Start date", value=None,
                                  key="home_start",
                                  help="Earliest date to search for emails")
            if start:
                config.set("date_range.start", str(start))
        with col2:
            end = st.date_input("End date", value=None,
                                key="home_end",
                                help="Latest date to search for emails")
            if end:
                config.set("date_range.end", str(end))

        st.markdown(f"Current range: **{config.date_start}** to **{config.date_end}**")

        st.markdown("#### LLM Provider")
        from casepulse.llm.api_provider import PROVIDERS
        provider_keys = list(PROVIDERS.keys())
        provider_labels = [PROVIDERS[k]["label"] for k in provider_keys]
        current_idx = provider_keys.index(config.llm_provider) if config.llm_provider in provider_keys else 0
        provider = st.selectbox(
            "AI Provider",
            provider_keys,
            index=current_idx,
            format_func=lambda x: PROVIDERS[x]["label"],
        )
        if provider != config.llm_provider:
            config.set("llm.provider", provider)
            # Set default model for the new provider
            default_model = PROVIDERS[provider]["default_model"]
            if default_model:
                config.set("llm.model", default_model)

        if provider == "ollama":
            st.info("Ollama runs locally — your data never leaves this machine.")
            model = st.text_input("Model", value=config.llm_model)
            if model != config.llm_model:
                config.set("llm.model", model)
        else:
            api_key = st.text_input("API Key", value=config.llm_api_key, type="password")
            if api_key != config.llm_api_key:
                config.set("llm.api_key", api_key)
            model = st.text_input("Model", value=config.llm_model)
            if model != config.llm_model:
                config.set("llm.model", model)
            if provider == "custom":
                base_url = st.text_input("Base URL", value=config.llm_base_url)
                if base_url != config.llm_base_url:
                    config.set("llm.base_url", base_url)

        st.markdown("#### App Security")
        from casepulse.legal.pin_lock import is_pin_set, set_pin, remove_pin
        if is_pin_set(db):
            st.success("PIN lock is enabled.")
            col1, col2 = st.columns(2)
            with col1:
                current_pin = st.text_input("Current PIN", type="password", key="current_pin")
            with col2:
                new_pin = st.text_input("New PIN (leave blank to remove)", type="password", key="new_pin_change")
            if st.button("Update PIN"):
                if new_pin:
                    from casepulse.legal.pin_lock import verify_pin
                    if verify_pin(db, current_pin):
                        set_pin(db, new_pin)
                        st.success("PIN updated!")
                    else:
                        st.error("Current PIN is incorrect.")
                else:
                    if remove_pin(db, current_pin):
                        st.success("PIN removed.")
                        st.rerun()
                    else:
                        st.error("Current PIN is incorrect.")
        else:
            st.info("No PIN set. Set one to protect your data.")
            new_pin = st.text_input("Set PIN", type="password", key="new_pin_set",
                                     help="4-20 characters. Required every time you open CasePulse.")
            if st.button("Enable PIN Lock") and new_pin:
                if len(new_pin) >= 4:
                    set_pin(db, new_pin)
                    st.success("PIN lock enabled!")
                    st.rerun()
                else:
                    st.error("PIN must be at least 4 characters.")


if __name__ == "__main__":
    main()
