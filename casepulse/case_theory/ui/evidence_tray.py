# casepulse/case_theory/ui/evidence_tray.py
"""Right-pane Evidence Tray for the Workbench page.

A persistent FTS5-backed search box + faceted filters + result list. Each
result has an inline "+ add" button that calls into the active argument's
attach handler.
"""
from typing import Callable
import streamlit as st

from casepulse.search.retrieval import hybrid_search, SearchFacets
from casepulse.case_theory.ui import facets as facets_mod
from casepulse.case_theory.ui.source_row_card import format_one_line_meta
from casepulse.case_theory.ui.picker_state import (
    get_tray_query, set_tray_query, get_recent_argument_id,
)


def render(db, *, on_add: Callable[[str, int], None] | None = None) -> None:
    st.markdown("### Evidence Tray")
    query = st.text_input(
        "Search",
        value=get_tray_query(st.session_state),
        key="tray_search_input",
    )
    set_tray_query(st.session_state, query)

    with st.expander("Filters"):
        f = facets_mod.render(key_prefix="tray")

    if not query:
        st.caption("Enter a search to see results")
        return

    facets = SearchFacets(
        source_types=f.source_types,
        date_from=f.date_from,
        date_to=f.date_to,
        sender=f.sender,
    )
    try:
        hits = hybrid_search(db, query, facets=facets, k=20)
    except Exception as exc:
        st.warning(f"Search error: {exc}")
        return

    if not hits:
        st.info("No matches")
        return

    # Build set of already-attached (source_table, source_row_id) for active arg
    arg_id = get_recent_argument_id(st.session_state)
    already_attached_ids: set = set()
    if arg_id:
        from casepulse.case_theory.repository import list_evidence_for_argument
        for entry in list_evidence_for_argument(db, arg_id):
            ev = entry["evidence"]
            already_attached_ids.add((ev.source_table, ev.source_row_id))

    for hit in hits:
        with st.container(border=True):
            cit = hit.citation
            kind = cit.table.rstrip("s") if cit.table.endswith("s") else cit.table
            line = format_one_line_meta(
                kind=kind,
                subject=(cit.snippet or "")[:80],
            )
            st.markdown(line, unsafe_allow_html=True)
            if cit.snippet:
                st.markdown(
                    f"<span style='font-size:0.82em; opacity:0.7'>"
                    f"{cit.snippet}</span>",
                    unsafe_allow_html=True,
                )
            cols = st.columns([2, 1, 1])
            key_tuple = (cit.table, cit.row_id)
            with cols[1]:
                if st.button("View source", key=f"view_{cit.table}_{cit.row_id}_{id(hit)}"):
                    from casepulse.case_theory.ui.view_source_dialog import show
                    show(db, source_table=cit.table, source_row_id=cit.row_id)
            with cols[2]:
                if key_tuple in already_attached_ids:
                    st.markdown(
                        "<span style='color:#10b981;opacity:0.7'>✓ attached</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button("+ add", key=f"add_{cit.table}_{cit.row_id}_{id(hit)}"):
                        if on_add:
                            on_add(cit.table, cit.row_id)
