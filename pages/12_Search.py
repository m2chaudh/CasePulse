"""Dedicated faceted Search page.

Differs from Workbench's Evidence Tray in that this is a full-width experience
optimized for "I don't know where the evidence is" exploration. Each result
gets a "+ Add to Argument" inline button.
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="Search — CasePulse", layout="wide")

from components.page_init import init_page
from casepulse.search.retrieval import hybrid_search, SearchFacets
from casepulse.case_theory.ui import facets as facets_mod
from casepulse.case_theory.ui.source_row_card import format_one_line_meta

db, config = init_page()

st.markdown("## Search")
st.markdown("Search across emails, chats, attachments, documents, and annotations.")

# Active case picker (needed for "+ Add to Argument")
cases = db.get_cases() if hasattr(db, "get_cases") else []
active_case_id = None
if cases:
    case_options = {f"{c['name']} ({c.get('case_type', 'case')})": c["id"] for c in cases}
    with st.sidebar:
        st.markdown("### Active Case")
        selected_label = st.selectbox(
            "Case",
            list(case_options.keys()),
            key="search_active_case",
        )
        active_case_id = case_options[selected_label]

query = st.text_input(
    "Search",
    placeholder="Search emails, chats, documents…",
    key="search_query",
)

with st.sidebar:
    st.markdown("### Filters")
    f = facets_mod.render(key_prefix="search")

if not query:
    st.caption("Enter a search to see results")
    st.stop()

facets = SearchFacets(
    source_types=f.source_types,
    date_from=f.date_from,
    date_to=f.date_to,
    sender=f.sender,
)
hits = hybrid_search(db, query, facets=facets, k=50)
if not hits:
    st.info("No matches.")
    st.stop()

st.caption(f"{len(hits)} hits")
for hit in hits:
    with st.container(border=True):
        cit = hit.citation
        kind = cit.table.rstrip("s") if cit.table.endswith("s") else cit.table
        st.markdown(format_one_line_meta(
            kind=kind,
            subject=(cit.snippet or "")[:80],
        ))
        if cit.snippet:
            st.markdown(
                f"<span style='font-size:0.85em; opacity:0.75'>"
                f"{cit.snippet}</span>",
                unsafe_allow_html=True,
            )
        cols = st.columns([3, 1, 1])
        with cols[1]:
            if st.button(
                "View source",
                key=f"vs_{cit.table}_{cit.row_id}_{hit.score:.4f}",
            ):
                from casepulse.case_theory.ui.view_source_dialog import show as show_vs
                show_vs(db, source_table=cit.table, source_row_id=cit.row_id)
        with cols[2]:
            if st.button(
                "+ Add to Argument",
                key=f"ata_{cit.table}_{cit.row_id}_{hit.score:.4f}",
            ):
                if active_case_id:
                    from casepulse.case_theory.ui.add_to_argument import show as show_ata
                    show_ata(
                        db,
                        source_table=cit.table,
                        source_row_id=cit.row_id,
                        case_id=active_case_id,
                    )
                else:
                    st.warning("Select a case first (sidebar).")
