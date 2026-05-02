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
from casepulse.binder.attach_dialog import open_attach_dialog
from casepulse.binder.open_dialog import open_item_dialog
from casepulse.binder.density_bar import render_month_density, render_week_density
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


def _nav_step(view: str, anchor_iso: str, direction: int) -> str:
    """Step the anchor date forward/back by one unit of `view`."""
    d = date.fromisoformat(anchor_iso)
    if view == "year":
        return d.replace(year=d.year + direction).isoformat()
    if view == "month":
        # Month arithmetic with day-clamp for month-end dates.
        total = d.year * 12 + (d.month - 1) + direction
        y, m = divmod(total, 12)
        m += 1
        last_day = monthrange(y, m)[1]
        return date(y, m, min(d.day, last_day)).isoformat()
    if view == "week":
        return (d + timedelta(days=7 * direction)).isoformat()
    return (d + timedelta(days=direction)).isoformat()


def _period_label(view: str, anchor_iso: str) -> str:
    d = date.fromisoformat(anchor_iso)
    if view == "year":
        return str(d.year)
    if view == "month":
        return d.strftime("%B %Y")
    if view == "week":
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
        if start.year == end.year and start.month == end.month:
            return f"{start.strftime('%b %d')} – {end.strftime('%d, %Y')}"
        return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
    return d.strftime("%a, %B %d, %Y")


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

# View tabs
# `binder_view` is the *canonical* state. The radio uses a separate key
# (`binder_view_widget`) so other components can programmatically write
# to `binder_view` without hitting Streamlit's "can't write to a
# widget-bound key after instantiation" rule. We sync the widget key
# from the canonical key BEFORE the radio renders, so a programmatic
# change to `binder_view` is reflected on the next run.
if "binder_view" not in st.session_state:
    st.session_state["binder_view"] = "month"
# CRITICAL: sync widget key from canonical BEFORE radio renders, every run.
# Streamlit otherwise uses the stale widget-key value and overrides any
# programmatic change to `binder_view`.
st.session_state["binder_view_widget"] = st.session_state["binder_view"]

view_row = st.columns([3, 7])
with view_row[0]:
    _options = ["year", "month", "week", "day"]
    view = st.radio(
        "View", _options,
        horizontal=True,
        index=_options.index(st.session_state["binder_view"]),
        key="binder_view_widget",
    )
if view != st.session_state["binder_view"]:
    st.session_state["binder_view"] = view
    st.rerun()

# Date state — initialise before the nav row uses it
if "binder_anchor_date" not in st.session_state:
    st.session_state["binder_anchor_date"] = date.today().isoformat()
anchor_iso = st.session_state["binder_anchor_date"]

# Date navigation row — Prev | Period label | Next | Today
nav = st.columns([1, 5, 1, 1])
with nav[0]:
    if st.button("‹ Prev", key="binder_nav_prev", use_container_width=True):
        st.session_state["binder_anchor_date"] = _nav_step(view, anchor_iso, -1)
        st.rerun()
with nav[1]:
    st.markdown(
        f"<div style='text-align:center;font-weight:600;font-size:1.05em;padding-top:6px'>"
        f"{_period_label(view, anchor_iso)}</div>",
        unsafe_allow_html=True,
    )
with nav[2]:
    if st.button("Next ›", key="binder_nav_next", use_container_width=True):
        st.session_state["binder_anchor_date"] = _nav_step(view, anchor_iso, 1)
        st.rerun()
with nav[3]:
    if st.button("Today", key="binder_today", use_container_width=True):
        st.session_state["binder_anchor_date"] = date.today().isoformat()
        st.rerun()

# Re-read after potential update above (rerun reset)
anchor_iso = st.session_state["binder_anchor_date"]

if "binder_selected_date" not in st.session_state:
    st.session_state["binder_selected_date"] = anchor_iso
sel_val = st.session_state["binder_selected_date"]
selected_day = date.fromisoformat(sel_val) if isinstance(sel_val, str) \
    else date.fromordinal(sel_val)

# Filter state — chips themselves are rendered BELOW the calendar
# (right above the day drawer they filter). chip_filter is read here so
# the calendar/heat strip/density bars can use it on this render.
if "binder_chip_id" not in st.session_state:
    st.session_state["binder_chip_id"] = "all"
chip_id = st.session_state["binder_chip_id"]
chip_filter = chip_to_filter(chip_id)

# Render the selected view
if view == "year":
    render_year_view(db, case_id=case_id, year=int(anchor_iso[:4]))
else:
    # Density indicator above the calendar — week-cells for month view,
    # day-cells for week/day view. Hover shows the count per cell.
    if view == "month":
        render_month_density(db, case_id=case_id, anchor_iso=anchor_iso)
    elif view in ("week", "day"):
        render_week_density(db, case_id=case_id, anchor_iso=anchor_iso)

    items = aggregate(
        db, case_id=case_id,
        date_start=_view_start(view, anchor_iso),
        date_end=_view_end(view, anchor_iso),
        chip_filter=chip_filter,
    )
    _selected = st.session_state.get("binder_selected_date")
    clicked = render_calendar(
        items,
        view=view,
        initial_date=anchor_iso,
        selected_date=_selected if isinstance(_selected, str) else None,
    )
    if clicked and clicked != _selected:
        st.session_state["binder_selected_date"] = clicked
        st.session_state["binder_scroll_to_drawer"] = True
        st.rerun()

# Day drawer always renders below — re-read selected_day in case it just changed
sel_val = st.session_state["binder_selected_date"]
selected_day = date.fromisoformat(sel_val) if isinstance(sel_val, str) \
    else date.fromordinal(sel_val)

st.divider()

# Anchor for scroll-into-view when user clicks a day above
st.markdown("<div id='binder-day-drawer-anchor'></div>", unsafe_allow_html=True)
if st.session_state.pop("binder_scroll_to_drawer", False):
    import streamlit.components.v1 as components
    components.html(
        """<script>
            // Streamlit components run in an iframe; jump in the parent.
            const target = window.parent.document.getElementById('binder-day-drawer-anchor');
            if (target) target.scrollIntoView({behavior: 'smooth', block: 'start'});
        </script>""",
        height=0,
    )

# Filter chips — small pill-style buttons under the calendar, above the
# day drawer they primarily affect. Inline CSS tightens the buttons so
# they feel like chips rather than full-width buttons.
st.markdown(
    """<style>
    div[data-testid="stHorizontalBlock"].binder-chip-bar .stButton > button {
        padding: 2px 10px !important;
        font-size: 0.82em !important;
        line-height: 1.3 !important;
        min-height: 0 !important;
        border-radius: 14px !important;
    }
    </style>""",
    unsafe_allow_html=True,
)
st.caption("Filter")
# Wrap the chip row so the CSS scope above only hits these buttons. We
# can't set a class on st.columns directly, but Streamlit groups columns
# under a stHorizontalBlock — we add a sentinel container with our class.
chip_row = st.container()
with chip_row:
    chip_cols = st.columns(len(BUILTIN_CHIPS), gap="small")
    for i, c in enumerate(BUILTIN_CHIPS):
        label = f"{c['emoji']} {c['label']}".strip()
        is_active = c["id"] == chip_id
        with chip_cols[i]:
            if st.button(
                label,
                key=f"binder_chip_{c['id']}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
            ):
                if c["id"] != chip_id:
                    st.session_state["binder_chip_id"] = c["id"]
                    st.rerun()

# Active filter caption — explains 0-result chips aren't broken
if chip_id != "all":
    active_chip = next((c for c in BUILTIN_CHIPS if c["id"] == chip_id), None)
    if active_chip:
        st.caption(
            f"Active filter: **{active_chip['emoji']} {active_chip['label']}** "
            "· click **All** to clear"
        )

st.caption("↓ Click a day above to view + edit its items here ↓")
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

if st.session_state.pop("binder_open_attach", False):
    open_attach_dialog(
        db, case_id=case_id,
        day=st.session_state.get("binder_attach_date", anchor_iso),
    )

# Open-item dialog (clicked from day drawer's Open / Edit buttons)
_open_src = st.session_state.pop("binder_open_dialog_source", None)
_open_sid = st.session_state.pop("binder_open_dialog_id", None)
if _open_src and _open_sid:
    open_item_dialog(db, source=_open_src, source_id=_open_sid)
