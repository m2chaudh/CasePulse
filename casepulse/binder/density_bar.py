"""Per-cell activity density bars for month and week views.

Renders a thin row of colored cells indicating activity intensity for the
sub-units of the active period — weeks within a month, days within a week.
Pure visual; no click handlers (the calendar grid below handles selection).

The per-day count is cached for 30 seconds in st.session_state so that
sequential day navigation (Prev/Next on the day drawer) doesn't re-fire
35 SQL queries on every step.
"""
from __future__ import annotations
import time
from calendar import monthrange
from datetime import date, timedelta
import streamlit as st
from casepulse.storage.database import Database


def _density_color(t: float) -> str:
    """5-step color ramp from empty to dense, matched to year_view._density_color."""
    if t == 0:
        return "#e2e8f0"
    if t < 0.25:
        return "#cbd5e1"
    if t < 0.5:
        return "#94a3b8"
    if t < 0.75:
        return "#475569"
    return "#1e293b"


_CACHE_TTL_SEC = 30
_CACHE_KEY = "_density_count_cache"


def clear_density_cache() -> None:
    """Drop every memoised per-day count.

    Call after any operation that adds/removes chat_messages, emails,
    timeline_events, documents, attachments, or evidence_tags — the
    legacy TTL-only cache could show stale counts for up to 30 s after
    a migration apply, which lied to the user about how much data the
    calendar would render."""
    import streamlit as st  # noqa: F401  (already imported at module top)
    if _CACHE_KEY in st.session_state:
        st.session_state[_CACHE_KEY] = {}


def _count_items_for_day(db: Database, case_id: int, day: date) -> int:
    """Count all aggregator-visible items for a given day. Mirrors the
    aggregator's 'exclude only items tagged to a different case' rule.

    Cached in st.session_state for 30 s so sequential day navigation
    doesn't re-query 5 tables × 7 days × every interaction. Cache is
    keyed by (case_id, day) and invalidated by TTL only — fine for a
    visual density indicator."""
    cache = st.session_state.setdefault(_CACHE_KEY, {})
    now = time.monotonic()
    key = (case_id, day.isoformat())
    if key in cache:
        ts, val = cache[key]
        if now - ts < _CACHE_TTL_SEC:
            return val

    ds = day.isoformat()
    de = day.isoformat()
    total = 0
    with db._get_conn() as conn:
        # timeline_events
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM timeline_events WHERE case_id=? AND date=?",
            (case_id, ds),
        ).fetchone()
        total += row["n"]
        # emails
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM emails e
               WHERE substr(COALESCE(e.date_received, e.date_sent, ''),1,10)=?
                 AND e.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='email' AND case_id != ?
                 )""",
            (ds, case_id),
        ).fetchone()
        total += row["n"]
        # chats
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM chat_messages c
               WHERE substr(c.timestamp,1,10)=?
                 AND c.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='chat' AND case_id != ?
                 )""",
            (ds, case_id),
        ).fetchone()
        total += row["n"]
        # documents + attachments
        for tbl, col, t_type in (("documents", "created_at", "document"),
                                  ("attachments", "created_at", "attachment")):
            row = conn.execute(
                f"""SELECT COUNT(*) AS n FROM {tbl} x
                    WHERE substr(COALESCE(x.{col}, ''),1,10)=?
                      AND x.id NOT IN (
                        SELECT item_id FROM evidence_tags
                         WHERE item_type='{t_type}' AND case_id != ?
                      )""",
                (ds, case_id),
            ).fetchone()
            total += row["n"]
    cache[key] = (now, total)
    return total


def render_month_density(db: Database, *, case_id: int, anchor_iso: str) -> None:
    """Show one cell per week of the month, colored by total activity."""
    d = date.fromisoformat(anchor_iso)
    first = d.replace(day=1)
    last_day = monthrange(d.year, d.month)[1]

    # Group days into weeks (Mon-Sun); first row may be partial
    weeks: list[list[date]] = []
    cur = first
    while cur.day <= last_day:
        # Find this week's start (Monday) and end (Sunday)
        wstart = cur - timedelta(days=cur.weekday())
        wend = wstart + timedelta(days=6)
        # Clamp to the month
        actual_start = max(wstart, first)
        actual_end = min(wend, date(d.year, d.month, last_day))
        days_in_week = []
        di = actual_start
        while di <= actual_end:
            days_in_week.append(di)
            di += timedelta(days=1)
        weeks.append(days_in_week)
        # Move to the Monday after this week's end
        cur = wend + timedelta(days=1)
        if cur.month != d.month:
            break

    counts = [sum(_count_items_for_day(db, case_id, dd) for dd in wk) for wk in weeks]
    max_c = max(counts) or 1

    cells = []
    for wk, n in zip(weeks, counts):
        if not wk:
            continue
        label = f"{wk[0].strftime('%b %d')}–{wk[-1].strftime('%b %d')} · {n} items"
        cells.append(
            f"<div title='{label}' style='flex:{len(wk)};height:14px;"
            f"background:{_density_color(n/max_c)};border-radius:2px;'></div>"
        )
    st.markdown(
        f"<div style='display:flex;gap:2px;margin:6px 0 8px'>{''.join(cells)}</div>",
        unsafe_allow_html=True,
    )


def render_week_density(db: Database, *, case_id: int, anchor_iso: str) -> None:
    """Show 7 cells, one per day of the week, colored by total activity."""
    d = date.fromisoformat(anchor_iso)
    monday = d - timedelta(days=d.weekday())
    days = [monday + timedelta(days=i) for i in range(7)]
    counts = [_count_items_for_day(db, case_id, dd) for dd in days]
    max_c = max(counts) or 1
    dow = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cells = []
    for dd, n, name in zip(days, counts, dow):
        label = f"{name} {dd.strftime('%b %d')} · {n} items"
        cells.append(
            f"<div title='{label}' style='flex:1;height:14px;"
            f"background:{_density_color(n/max_c)};border-radius:2px;'></div>"
        )
    st.markdown(
        f"<div style='display:flex;gap:2px;margin:6px 0 8px'>{''.join(cells)}</div>",
        unsafe_allow_html=True,
    )
    # Day-of-week labels under the cells
    label_cells = "".join(
        f"<span style='flex:1;text-align:center'>{n}</span>" for n in dow
    )
    st.markdown(
        f"<div style='display:flex;gap:2px;font-size:0.72em;opacity:0.6'>"
        f"{label_cells}</div>",
        unsafe_allow_html=True,
    )
