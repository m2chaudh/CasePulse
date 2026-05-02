"""Case Binder — calendar dashboard. Default landing page."""

from __future__ import annotations
from calendar import monthrange
from datetime import date, timedelta
import streamlit as st
from casepulse.storage.database import Database
from casepulse.binder.aggregator import aggregate
from casepulse.binder.calendar_component import render_calendar
from casepulse.binder.day_drawer import render_day_drawer
from casepulse.binder.year_view import render_year_view
from casepulse.binder.add_entry_form import open_add_entry_dialog
from casepulse.binder.filter_chips_builtin import BUILTIN_CHIPS, chip_to_filter
from casepulse.ui.workflow_help import (
    compute_workflow_state, render_workflow_help, WorkflowState,
)


st.set_page_config(page_title="Case Binder", layout="wide")


def _view_start(view: str, anchor_iso: str) -> date:
    d = date.fromisoformat(anchor_iso)
    if view == "month":
        return d.replace(day=1)
    if view == "week":
        return d - timedelta(days=d.weekday())
    return d


def _view_end(view: str, anchor_iso: str) -> date:
    d = date.fromisoformat(anchor_iso)
    if view == "month":
        return d.replace(day=monthrange(d.year, d.month)[1])
    if view == "week":
        return d - timedelta(days=d.weekday()) + timedelta(days=6)
    return d


def _active_case_id(db: Database):
    if "active_case_id" in st.session_state:
        return st.session_state["active_case_id"]
    with db._get_conn() as conn:
        row = conn.execute("SELECT id FROM cases ORDER BY id LIMIT 1").fetchone()
    return row["id"] if row else None


db: Database = st.session_state.get("db") or Database()
case_id = _active_case_id(db)

# Sidebar — case selector (always visible)
with st.sidebar:
    with db._get_conn() as conn:
        rows = conn.execute("SELECT id, name FROM cases ORDER BY id").fetchall()
    case_opts = {r["name"]: r["id"] for r in rows}
    if case_opts:
        names = list(case_opts.keys())
        ids = list(case_opts.values())
        idx = ids.index(case_id) if case_id in ids else 0
        chosen = st.selectbox("Active case", names, index=idx)
        st.session_state["active_case_id"] = case_opts[chosen]
        case_id = case_opts[chosen]
    else:
        st.info("No cases yet. Create one on the Cases page.")

# Empty-state when no case exists yet
if case_id is None:
    st.title("Case Binder")
    render_workflow_help(WorkflowState(), default_open=True)
    st.stop()

# View tabs + Today button
top = st.columns([2, 1, 4])
with top[0]:
    view = st.radio(
        "View", ["year", "month", "week", "day"],
        horizontal=True, key="binder_view", index=1,
    )
with top[1]:
    today_btn = st.button("Today")

# Date state
if "binder_anchor_date" not in st.session_state or today_btn:
    st.session_state["binder_anchor_date"] = date.today().isoformat()
anchor_iso = st.session_state["binder_anchor_date"]

if "binder_selected_date" not in st.session_state:
    st.session_state["binder_selected_date"] = anchor_iso
sel_val = st.session_state["binder_selected_date"]
selected_day = date.fromisoformat(sel_val) if isinstance(sel_val, str) \
    else date.fromordinal(sel_val)

# Filter chips row
chip_cols = st.columns(len(BUILTIN_CHIPS))
if "binder_chip_id" not in st.session_state:
    st.session_state["binder_chip_id"] = "all"
for i, c in enumerate(BUILTIN_CHIPS):
    label = f"{c['emoji']} {c['label']}".strip()
    with chip_cols[i]:
        if st.button(label, key=f"binder_chip_{c['id']}"):
            st.session_state["binder_chip_id"] = c["id"]
chip_filter = chip_to_filter(st.session_state["binder_chip_id"])

# Render the selected view
if view == "year":
    render_year_view(db, case_id=case_id, year=int(anchor_iso[:4]))
else:
    items = aggregate(
        db, case_id=case_id,
        date_start=_view_start(view, anchor_iso),
        date_end=_view_end(view, anchor_iso),
        chip_filter=chip_filter,
    )
    clicked = render_calendar(items, view=view, initial_date=anchor_iso)
    if clicked:
        st.session_state["binder_selected_date"] = clicked

# Day drawer always renders below
st.divider()
st.subheader("Selected day")
render_day_drawer(db, case_id=case_id, day=selected_day, chip_filter=chip_filter)

# Empty-state — show workflow help if no data anywhere for this case
wstate = compute_workflow_state(db, case_id=case_id)
if not (wstate.has_email or wstate.has_document or wstate.has_flagged_sender):
    st.divider()
    st.subheader("Getting started")
    render_workflow_help(wstate, default_open=True)

# Dialog hooks
if st.session_state.pop("binder_open_add_entry", False):
    open_add_entry_dialog(
        db, case_id=case_id,
        default_date=st.session_state.get("binder_add_entry_date", anchor_iso),
    )
