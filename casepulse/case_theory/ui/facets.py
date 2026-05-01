# casepulse/case_theory/ui/facets.py
"""Faceted filter widgets. Render checkboxes / date-range / multiselects;
return a dict of facet values for hybrid_search."""
from dataclasses import dataclass
from typing import Any
import streamlit as st


SOURCE_TYPES = ["emails", "chat_messages", "attachments", "documents", "annotations"]


@dataclass
class TrayFacets:
    source_types: list[str] | None
    date_from: str | None
    date_to: str | None
    sender: str | None


def render(*, key_prefix: str = "tray") -> TrayFacets:
    types = st.multiselect(
        "Source types",
        SOURCE_TYPES,
        default=None,
        key=f"{key_prefix}_source_types",
    )
    col1, col2 = st.columns(2)
    with col1:
        date_from = st.text_input(
            "From",
            placeholder="2024-01-01",
            key=f"{key_prefix}_date_from",
        )
    with col2:
        date_to = st.text_input(
            "To",
            placeholder="2024-12-31",
            key=f"{key_prefix}_date_to",
        )
    sender = st.text_input(
        "Sender contains",
        placeholder="email or name",
        key=f"{key_prefix}_sender",
    )
    return TrayFacets(
        source_types=types or None,
        date_from=date_from or None,
        date_to=date_to or None,
        sender=sender or None,
    )
