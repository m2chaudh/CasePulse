# casepulse/case_theory/ui/page_help.py
"""Page-level help — default-open collapsible expander at top of every page.

Reads from PAGE_HELP registry. Each entry: title, description, what_to_do.
Render produces a Streamlit expander labeled 'About this page' that opens
by default per session and collapses on click.
"""
from typing import Optional
import streamlit as st


PAGE_HELP: dict[str, dict[str, str]] = {
    "home": {
        "title": "CasePulse Home",
        "description": "Dashboard for your cases, recent activity, and connected email accounts. "
                       "From here you can jump to any feature in the sidebar.",
        "what_to_do": "Use the sidebar to navigate. New users start with Cases (create a case), "
                      "then Case Theory (build contradictions), then Search to find evidence.",
    },
    "case_theory": {
        "title": "Case Theory Workbench",
        "description": "Build your case theory: mark allegations the opposing party made, "
                       "document contradictions, and attach evidence to specific arguments. "
                       "AI assists *after* the structural work — you do the analysis first.",
        "what_to_do": "Pick a Contradiction on the left or create a new one. Add Arguments under it "
                      "with type (Alibi, Self-contradiction, Witness, Documentary, Timing, Pattern) "
                      "and strength (Strong, Moderate, Circumstantial). Use the Evidence Tray on "
                      "the right to find and attach evidence.",
    },
    "search": {
        "title": "Search",
        "description": "Search across every email, chat message, attachment, and document with "
                       "keyword + semantic ranking. Results are court-defensible — each links back "
                       "to its original source row with a verifiable hash.",
        "what_to_do": "Type a query. Use the Filters panel for source type, date range, sender. "
                      "Click '+ Add to Argument' on a result to attach it to a Contradiction.",
    },
    "timeline": {
        "title": "Timeline",
        "description": "Chronological view of every email and chat message. Use this to scan dates "
                       "and threads, or filter to a specific window of activity.",
        "what_to_do": "Set the date range, filter by sender or keyword, and click into any row "
                      "to expand the full body. Use '+ Add to Argument' to attach an item to your case theory.",
    },
    "cases": {
        "title": "Cases & Evidence Manager",
        "description": "Create and manage your cases (one for family law, one for criminal defence, "
                       "etc.). Each case has its own exhibit numbering format and tagging system.",
        "what_to_do": "Create your first case below. Once created, switch to Case Theory or Search "
                      "to start building. The Tag Evidence Items tab lets you bulk-assign exhibit labels.",
    },
    "witnesses": {
        "title": "Witnesses",
        "description": "Manage character witnesses and fact witnesses. Each witness can have multiple "
                       "statements linked to specific Contradictions or Arguments.",
        "what_to_do": "Add a witness on the left (name, relationship, type, contact info, status). "
                      "On the right, edit details and add statements. Linking a statement to a "
                      "Contradiction makes it appear in the Argument editor automatically.",
    },
    "documents": {
        "title": "Documents & Timeline",
        "description": "Import, browse, and manage standalone documents — affidavits, police reports, "
                       "court orders, scanned PDFs. Documents are full-text searchable and EXIF metadata "
                       "is extracted from images.",
        "what_to_do": "Use the Document Library tab to browse. Click '+ Add to Argument' to attach "
                      "a document as evidence. Use Import Documents to add new ones from a folder.",
    },
    "ask": {
        "title": "Ask",
        "description": "Ask natural-language questions about your case. Answers come with structured "
                       "citations linking back to specific source rows. Build the RAG index first "
                       "(button in sidebar) for semantic answers; keyword search works without it.",
        "what_to_do": "Type a question. Citations appear under each answer — click to view the source.",
    },
    "import_chats": {
        "title": "Import Chats",
        "description": "Import WhatsApp exports, AppClose PDFs, ChatVault HTML, and generic PDF chat exports. "
                       "Auto-detects format. Imported chats are searchable and timeline-merged with emails.",
        "what_to_do": "Pick a tab matching your export format and follow the upload steps. "
                      "After import, chats appear in Timeline, Search, and the Workbench Tray.",
    },
    "discover_senders": {
        "title": "Discover Senders",
        "description": "Scan your connected email accounts to find every contact you've corresponded with. "
                       "Select the ones relevant to your case before fetching their emails.",
        "what_to_do": "Set the date range, click Scan for Contacts, then check the contacts you want to "
                      "fetch. Click Save Selection. Then go to Fetch Emails to download their messages.",
    },
    "fetch_emails": {
        "title": "Fetch Emails",
        "description": "Download emails from your selected senders within a date range. Runs in the "
                       "background — you can leave the page and come back. Emails are deduplicated "
                       "across accounts.",
        "what_to_do": "Confirm the date range and selected senders, then click Fetch. Watch progress "
                      "in the sidebar. After completion, emails appear in Timeline and Search.",
    },
    "accounts": {
        "title": "Accounts",
        "description": "Connect your Outlook, Hotmail, and Gmail accounts. Multiple accounts per provider "
                       "are supported. OAuth tokens are stored locally — your credentials never leave this machine.",
        "what_to_do": "Click Add to connect a new account. Sign in via OAuth in the popup window. "
                      "Once connected, the account appears in Discover Senders and Fetch Emails.",
    },
    "export": {
        "title": "Export",
        "description": "Generate court-ready PDF bundles, AI analysis packages, Excel timelines, and more. "
                       "Each export carries a SHA-256 manifest for chain-of-custody.",
        "what_to_do": "Pick an export preset, configure the date range and case scope, then click "
                      "Generate. The output folder is shown after completion.",
    },
    "contradictions": {
        "title": "Contradiction Engine",
        "description": "AI-powered contradiction detection across emails, chats, and documents. "
                       "This is the legacy automated engine — the new Case Theory workbench is the "
                       "human-driven approach (recommended).",
        "what_to_do": "Pick contacts to analyze, set the email batch size, then click Run. "
                      "Findings appear at the bottom. You can promote interesting findings into your "
                      "Case Theory by hand.",
    },
    "setup": {
        "title": "First-Time Setup",
        "description": "Choose which optional modules you want enabled (cloud AI, local AI via Ollama, "
                       "RAG pipeline, vision/OCR, contradiction engine, exports). Core features are always on.",
        "what_to_do": "Tick the modules you want. Default selections cover the typical setup. "
                      "Click Save when done — you can change this later.",
    },
}


def get_help(page_key: str) -> Optional[dict[str, str]]:
    """Look up help entry by page_key. Returns None if missing."""
    return PAGE_HELP.get(page_key)


def render_help_markdown(page_key: str) -> str:
    """Build the markdown body of the page help expander.

    Returns empty string if page_key is not in PAGE_HELP.
    """
    entry = get_help(page_key)
    if not entry:
        return ""
    return (
        f"### {entry['title']}\n\n"
        f"{entry['description']}\n\n"
        f"**What to do here**\n\n{entry['what_to_do']}"
    )


def render(page_key: str) -> None:
    """Render a default-open collapsible expander at the top of a Streamlit page.

    Default-open per Streamlit session; user can collapse to reclaim space.
    Uses session_state to persist the open/closed state for this session.
    """
    body = render_help_markdown(page_key)
    if not body:
        return
    state_key = f"page_help_open_{page_key}"
    default_open = st.session_state.get(state_key, True)
    with st.expander("ℹ About this page", expanded=default_open):
        st.markdown(body)
        if st.button("Hide for now", key=f"hide_help_{page_key}"):
            st.session_state[state_key] = False
            st.rerun()
