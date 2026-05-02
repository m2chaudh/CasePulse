"""Workflow help component shown on Setup and on the empty Case Binder.
Renders a numbered onboarding path with checkmarks for completed steps."""

from __future__ import annotations
from dataclasses import dataclass
import streamlit as st
from casepulse.storage.database import Database


@dataclass
class WorkflowState:
    has_account: bool = False
    has_flagged_sender: bool = False
    has_email: bool = False
    has_document: bool = False


def compute_workflow_state(db: Database, *, case_id: int) -> WorkflowState:
    state = WorkflowState()
    with db._get_conn() as conn:
        row = conn.execute("SELECT 1 FROM accounts LIMIT 1").fetchone()
        state.has_account = row is not None
        row = conn.execute(
            "SELECT 1 FROM case_relevant_senders WHERE case_id=? AND active=1 LIMIT 1",
            (case_id,)).fetchone()
        state.has_flagged_sender = row is not None
        row = conn.execute(
            """SELECT 1 FROM evidence_tags
               WHERE case_id=? AND item_type='email' LIMIT 1""",
            (case_id,)).fetchone()
        state.has_email = row is not None
        row = conn.execute(
            """SELECT 1 FROM evidence_tags
               WHERE case_id=? AND item_type='document' LIMIT 1""",
            (case_id,)).fetchone()
        state.has_document = row is not None
    return state


_STEPS = [
    ("Connect your email accounts.",
     "Setup → Accounts. OAuth (Gmail) or IMAP credentials. You can connect more than one account."),
    ("Discover senders for a date window.",
     "Data Sources → Discover Senders. The app does a lightweight header scan and surfaces unique sender addresses so you can flag which are case-relevant — Crown counsel, opposing counsel, your own counsel, OCL, witnesses, doctor, school, employer."),
    ("Fetch emails (full bodies, only flagged senders recommended).",
     "Data Sources → Fetch Emails. Toggle 'Only flagged senders' to pull bodies and attachments just for the addresses you flagged."),
    ("Import chats.",
     "Data Sources → Import Chats. Drop in a WhatsApp / iMessage / Signal / SMS export."),
    ("Add documents and other evidence.",
     "Data Sources → Documents. Drop in court-served PDFs, affidavits, police reports, financial statements, audio recordings, voicemails, screenshots, paper documents you've scanned. The app extracts text and reads any embedded date."),
    ("Watch the calendar fill in.",
     "Workspace → Case Binder. Emails, chats, documents and photos all auto-aggregate to their natural date."),
    ("Attach extras to specific dates and link related items.",
     "Click any day → drawer opens → '+ Attach to this day' to link an item; '+ Add Entry' for a court appearance, disclosure entry, counsel correspondence, or personal event; '+ Link' on any item to typed-relate it to another."),
]


def render_workflow_help(state: WorkflowState, *, default_open: bool = False) -> None:
    """Render the workflow help. Call from Streamlit pages."""
    with st.expander("How to use CasePulse — workflow", expanded=default_open):
        st.markdown(
            "**Your data stays on this device.** CasePulse only reaches out when you "
            "tell it to fetch your own email or run an export. Nothing is sent to "
            "Anthropic, Google, or anyone else."
        )
        st.divider()

        check = lambda b: "✓" if b else "○"
        completion = [
            state.has_account,
            state.has_flagged_sender,
            state.has_email,
            False,
            state.has_document,
            False,
            False,
        ]
        for i, ((title, body), done) in enumerate(zip(_STEPS, completion), 1):
            st.markdown(f"**{i}. {check(done)} {title}**")
            st.caption(body)

        st.divider()
        st.markdown(
            "**Two mental models that overlap a little but are distinct:**\n\n"
            "- **Case Binder** — *what* happened *when*. Factual chronology.\n"
            "- **Case Theory** — *why* it matters and *how* to argue it. "
            "Allegations → Arguments → Evidence."
        )
