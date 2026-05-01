"""Shared "+ Add to Argument" dialog used from Search, Timeline, and
Documents pages.

`attach_to()` is the imperative entrypoint (testable). `show()` wraps it
in a Streamlit dialog with a target argument picker.
"""
import streamlit as st

from casepulse.case_theory.models import (
    Evidence, EvidenceKind, EvidenceRole,
)
from casepulse.case_theory.repository import (
    create_evidence, attach_evidence_to_argument,
    list_recent_arguments_for_picker,
)
from casepulse.case_theory.ui.picker_state import (
    get_recent_argument_id, set_recent_argument_id,
)


_KIND_MAP = {
    "emails": EvidenceKind.EMAIL,
    "chat_messages": EvidenceKind.CHAT,
    "attachments": EvidenceKind.ATTACHMENT,
    "documents": EvidenceKind.DOCUMENT,
    "annotations": EvidenceKind.EMAIL,  # fallback
}


def attach_to(db, *, argument_id: int, source_table: str,
              source_row_id: int,
              role: EvidenceRole = EvidenceRole.SUPPORTS) -> int:
    """Create Evidence and attach to argument. Returns evidence_id.

    This is the testable imperative entrypoint — no Streamlit imports
    needed.
    """
    kind = _KIND_MAP.get(source_table, EvidenceKind.EMAIL)
    e = create_evidence(db, Evidence(
        evidence_kind=kind,
        source_table=source_table,
        source_row_id=source_row_id,
    ))
    attach_evidence_to_argument(db, argument_id, e.id, role=role)
    return e.id


@st.dialog("+ Add to Argument")
def show(db, *, source_table: str, source_row_id: int,
         case_id: int) -> None:
    """Streamlit dialog wrapping attach_to — shown from per-result buttons."""
    candidates = list_recent_arguments_for_picker(db, case_id=case_id, limit=20)
    if not candidates:
        st.info("No Arguments yet — create one in the **Case Theory** Workbench first.")
        return

    recent_id = get_recent_argument_id(st.session_state)
    options = {
        f"{r['contradiction_headline']} → {r['argument_title']}": r["argument_id"]
        for r in candidates
    }
    labels = list(options.keys())
    default_idx = next(
        (i for i, lbl in enumerate(labels) if options[lbl] == recent_id), 0
    )
    label = st.selectbox("Argument", labels, index=default_idx, key="ata_argument_picker")
    role_key = st.selectbox(
        "Role",
        [r.value for r in EvidenceRole],
        index=0,
        key="ata_role_picker",
    )
    if st.button("Attach", key="ata_attach_btn"):
        target_arg = options[label]
        attach_to(
            db, argument_id=target_arg,
            source_table=source_table, source_row_id=source_row_id,
            role=EvidenceRole(role_key),
        )
        set_recent_argument_id(st.session_state, target_arg)
        st.toast(f"Attached to Argument #{target_arg}")
        st.rerun()
