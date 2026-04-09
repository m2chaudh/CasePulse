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

    # Header
    st.markdown('<p class="main-header">CasePulse</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Legal Email Aggregation & Analysis</p>', unsafe_allow_html=True)

    # Dashboard stats
    stats = db.get_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Connected Accounts", stats["connected_accounts"])
    with col2:
        st.metric("Emails Collected", f"{stats['total_emails']:,}")
    with col3:
        st.metric("Attachments", f"{stats['total_attachments']:,}")
    with col4:
        st.metric("Duplicates Found", f"{stats['duplicate_attachments']:,}")
    with col5:
        st.metric("Selected Senders", stats["selected_senders"])

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
        provider = st.selectbox(
            "AI Provider",
            ["ollama", "claude", "openai", "custom"],
            index=["ollama", "claude", "openai", "custom"].index(config.llm_provider),
        )
        if provider != config.llm_provider:
            config.set("llm.provider", provider)

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


if __name__ == "__main__":
    main()
