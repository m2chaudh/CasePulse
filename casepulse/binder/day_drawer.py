"""Day drawer — chronological strip with inline actions."""

from __future__ import annotations
from datetime import date
import streamlit as st
from casepulse.binder.models import AggregatedItem, CrossRef
from casepulse.binder.aggregator import aggregate
from casepulse.binder.calendar_component import (
    _emoji_for, _COLORS, item_color_key,
)


def format_time_label(item: AggregatedItem) -> str:
    if item.when.hour == 0 and item.when.minute == 0:
        return "—"
    return item.when.strftime("%H:%M")


def source_badge(item: AggregatedItem) -> str:
    color = _COLORS.get(item_color_key(item), "#475569")
    emoji = _emoji_for(item)
    return f"<span style='background:{color};color:white;padding:2px 6px;border-radius:3px;font-size:0.78em'>{emoji}</span>"


def format_cross_ref(cr: CrossRef) -> str:
    label = cr.label or f"{cr.target_type} #{cr.target_id}"
    if cr.target_type == "argument":
        return f"✓ In {label} · {cr.relationship}"
    return f"↪ {cr.relationship.replace('_', ' ')} {label}"


def render_day_drawer(db, *, case_id: int, day: date, chip_filter=None) -> None:
    """Render the chronological day drawer for one date."""
    items = aggregate(db, case_id=case_id,
                      date_start=day, date_end=day, chip_filter=chip_filter)

    cols = st.columns([1, 4, 1])
    with cols[0]:
        if st.button("‹ Prev", key="binder_day_prev"):
            from datetime import timedelta
            st.session_state["binder_selected_date"] = (day - timedelta(days=1)).isoformat()
    with cols[1]:
        st.markdown(f"### 📅 {day.strftime('%a, %B %d, %Y')}")
    with cols[2]:
        if st.button("Next ›", key="binder_day_next"):
            from datetime import timedelta
            st.session_state["binder_selected_date"] = (day + timedelta(days=1)).isoformat()

    a1, a2 = st.columns(2)
    with a1:
        if st.button("+ Add Entry", key="binder_day_add", type="primary"):
            st.session_state["binder_open_add_entry"] = True
            st.session_state["binder_add_entry_date"] = day.isoformat()
    with a2:
        if st.button("+ Attach to this day", key="binder_day_attach"):
            st.session_state["binder_open_attach"] = True
            st.session_state["binder_attach_date"] = day.isoformat()

    if not items:
        st.caption("No entries on this day.")
        return

    st.caption("Chronological · earliest first")

    for it in items:
        c1, c2 = st.columns([1, 9])
        with c1:
            st.markdown(f"<div style='opacity:0.6'>{format_time_label(it)}</div>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown(
                f"{source_badge(it)} **{it.title}**",
                unsafe_allow_html=True,
            )
            if it.summary:
                st.caption(it.summary)
            for cr in it.cross_refs:
                st.markdown(f"<small>{format_cross_ref(cr)}</small>",
                            unsafe_allow_html=True)
            _render_inline_actions(it)
        st.divider()


def _render_inline_actions(it: AggregatedItem) -> None:
    # Phase A: Open / Edit only. The "+ Link" inline action ships with the
    # Link picker dialog in Phase B.
    cols = st.columns([1, 1, 6])
    with cols[0]:
        if st.button("Open", key=f"binder_open_{it.source}_{it.source_id}"):
            st.session_state["binder_open_dialog_source"] = it.source
            st.session_state["binder_open_dialog_id"] = it.source_id
            st.rerun()
    with cols[1]:
        # Edit currently meaningful only for timeline_event entries (binder
        # entries we created); imported items are read-only — but the Open
        # dialog for a timeline_event also offers Delete.
        if it.source == "timeline_event":
            if st.button("Edit", key=f"binder_edit_{it.source}_{it.source_id}"):
                st.session_state["binder_open_dialog_source"] = it.source
                st.session_state["binder_open_dialog_id"] = it.source_id
                st.rerun()
        else:
            st.button(
                "Edit",
                key=f"binder_edit_{it.source}_{it.source_id}",
                disabled=True,
                help="Imported items aren't editable. Tag/annotate from the "
                     "Cases page or create a binder entry that links to this item.",
            )
