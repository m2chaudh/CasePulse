# casepulse/case_theory/ui/refine_snippet_dialog.py
"""Refine the snippet (char_start/char_end) for an attached Evidence row.

Streamlit doesn't support text-selection natively. W1.2 fallback: paragraph
picker — split source text on \n\n; user picks one or many paragraphs;
char_start/char_end computed from the picked range.
"""
import streamlit as st
from casepulse.case_theory.evidence_resolver import resolve
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.repository import update_evidence_snippet


@st.dialog("Refine snippet")
def show(db, *, evidence_id: int, source_table: str, source_row_id: int) -> None:
    e = Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table=source_table, source_row_id=source_row_id,
    )
    rs = resolve(db, e)
    paragraphs = [p.strip() for p in (rs.text or "").split("\n\n") if p.strip()]
    if not paragraphs:
        st.info("Source has no paragraphs to pick from.")
        return
    picked = st.multiselect(
        "Pick paragraph(s) to use as the snippet",
        options=list(range(len(paragraphs))),
        format_func=lambda i: paragraphs[i][:80] + (
            "…" if len(paragraphs[i]) > 80 else ""
        ),
    )
    if st.button("Save"):
        if not picked:
            st.warning("Pick at least one paragraph.")
            return
        # Find char_start of first picked, char_end of last picked
        running = 0
        starts, ends = {}, {}
        for i, p in enumerate(paragraphs):
            starts[i] = running
            running += len(p)
            ends[i] = running
            running += 2  # the "\n\n" separator
        char_start = starts[min(picked)]
        char_end = ends[max(picked)]
        snippet = "\n\n".join(paragraphs[i] for i in picked)
        update_evidence_snippet(db, evidence_id,
                                char_start=char_start, char_end=char_end,
                                snippet=snippet)
        st.toast("Snippet refined")
        st.rerun()
