# casepulse/case_theory/ui/view_source_dialog.py
"""Renders the full source content for an Evidence row.

Two modes:
- Streamlit dialog (default — when called from a button)
- Inline string return (for tests; `inline=True`)
"""
import streamlit as st

from casepulse.case_theory.evidence_resolver import resolve
from casepulse.case_theory.models import Evidence, EvidenceKind


def _resolve_for_display(db, *, source_table: str, source_row_id: int):
    e = Evidence(
        evidence_kind=EvidenceKind.EMAIL,  # placeholder — resolver dispatches on source_table
        source_table=source_table,
        source_row_id=source_row_id,
    )
    return resolve(db, e)


def render_source_panel(db, *, source_table: str, source_row_id: int,
                        inline: bool = False) -> str:
    rs = _resolve_for_display(db, source_table=source_table,
                               source_row_id=source_row_id)
    parts = [f"### {rs.kind.title()}"]
    for k, v in rs.metadata.items():
        if v is None or v == "":
            continue
        parts.append(f"**{k}:** {v}")
    parts.append("\n---\n")
    parts.append(rs.text or "[empty body]")
    rendered = "\n".join(parts)
    if inline:
        return rendered
    st.markdown(rendered)
    return rendered


@st.dialog("Source")
def show(db, *, source_table: str, source_row_id: int):
    render_source_panel(db, source_table=source_table,
                        source_row_id=source_row_id)
