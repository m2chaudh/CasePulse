"""Hand-rolled year view: heat strip + 12 mini-calendars + stats sidebar."""

from __future__ import annotations
from datetime import date
import streamlit as st
from casepulse.storage.database import Database
from casepulse.binder.aggregator import BINDER_CATEGORIES


_CATEGORY_PRIORITY = (
    "court_appearance", "disclosure",
    "counsel_correspondence", "personal_event",
)
_CATEGORY_COLORS = {
    "court_appearance":      "#fef3c7",  # amber
    "disclosure":            "#dcfce7",  # green
    "counsel_correspondence":"#fce7f3",  # pink
    "personal_event":        "#fee2e2",  # red
}


def day_category_color(categories: set[str]) -> str:
    """Pick the primary color for a day given the categories present."""
    for c in _CATEGORY_PRIORITY:
        if c in categories:
            return _CATEGORY_COLORS[c]
    return ""


def week_activity_counts(db: Database, *, case_id: int, year: int) -> list[int]:
    """Return a 54-length list of activity counts indexed by ISO week 1..53.
    Counts include binder entries + emails + chats + documents + photos."""
    counts = [0] * 54  # 1-indexed; index 0 unused
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT date FROM timeline_events
               WHERE case_id=? AND substr(date,1,4)=?""",
            (case_id, str(year))).fetchall()
        for r in rows:
            counts[_iso_week(r["date"])] += 1
        for sql in (
            # Match the aggregator's rule: items show on this case unless
            # explicitly tagged to a different case.
            """SELECT substr(e.date_received,1,10) AS d FROM emails e
               WHERE substr(e.date_received,1,4)=?
                 AND e.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='email' AND case_id != ?
                 )""",
            """SELECT substr(c.timestamp,1,10) AS d FROM chat_messages c
               WHERE substr(c.timestamp,1,4)=?
                 AND c.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='chat' AND case_id != ?
                 )""",
            """SELECT substr(d.created_at,1,10) AS d FROM documents d
               WHERE substr(d.created_at,1,4)=?
                 AND d.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='document' AND case_id != ?
                 )""",
        ):
            rows = conn.execute(sql, (str(year), case_id)).fetchall()
            for r in rows:
                if r["d"]:
                    counts[_iso_week(r["d"])] += 1
    return counts


def year_stats(db: Database, *, case_id: int, year: int) -> dict:
    out: dict = {c: 0 for c in BINDER_CATEGORIES}
    out.update({"total_entries": 0, "emails": 0, "chats": 0,
                "documents": 0, "photos": 0})
    with db._get_conn() as conn:
        for cat in BINDER_CATEGORIES:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM timeline_events
                   WHERE case_id=? AND category=? AND substr(date,1,4)=?""",
                (case_id, cat, str(year))).fetchone()
            out[cat] = row["n"]
            out["total_entries"] += row["n"]
        for label, sql in (
            ("emails",
             """SELECT COUNT(*) n FROM emails e
                WHERE substr(e.date_received,1,4)=?
                  AND e.id NOT IN (
                    SELECT item_id FROM evidence_tags
                     WHERE item_type='email' AND case_id != ?
                  )"""),
            ("chats",
             """SELECT COUNT(*) n FROM chat_messages c
                WHERE substr(c.timestamp,1,4)=?
                  AND c.id NOT IN (
                    SELECT item_id FROM evidence_tags
                     WHERE item_type='chat' AND case_id != ?
                  )"""),
            ("documents",
             """SELECT COUNT(*) n FROM documents d
                WHERE substr(d.created_at,1,4)=?
                  AND d.id NOT IN (
                    SELECT item_id FROM evidence_tags
                     WHERE item_type='document' AND case_id != ?
                  )"""),
            ("photos",
             """SELECT COUNT(*) n FROM photo_metadata p
                WHERE substr(p.taken_at,1,4)=?
                  AND NOT EXISTS (
                    SELECT 1 FROM evidence_tags t
                     WHERE t.item_type = p.source_table
                       AND t.item_id = p.source_row_id
                       AND t.case_id != ?
                  )"""),
        ):
            row = conn.execute(sql, (str(year), case_id)).fetchone()
            out[label] = row["n"]
    return out


def _iso_week(date_str: str) -> int:
    try:
        return date.fromisoformat(date_str[:10]).isocalendar().week
    except (ValueError, TypeError):
        return 0


def render_year_view(db: Database, *, case_id: int, year: int) -> None:
    """Render the year view to Streamlit."""
    counts = week_activity_counts(db, case_id=case_id, year=year)
    stats = year_stats(db, case_id=case_id, year=year)

    # Single heat strip — 52 clickable buttons, type=primary when the
    # week is above 30% of peak intensity (gives a 2-tone visual hint),
    # secondary otherwise. Click any cell → jumps to that week's first
    # day in Month view. Hover tooltip shows the week number + count.
    st.caption(f"Activity density · {year} — click any week to jump to its month")
    max_count = max(counts) or 1
    heat_cols = st.columns(52, gap="small")
    for i, w in enumerate(range(1, 53)):
        intensity = counts[w] / max_count if max_count else 0
        btype = "primary" if intensity > 0.3 else "secondary"
        with heat_cols[i]:
            if st.button(
                "·",
                key=f"yr_heat_{year}_{w}",
                use_container_width=True,
                type=btype,
                help=f"Week {w} of {year} — {counts[w]} items",
            ):
                from datetime import datetime as _dt
                try:
                    first_day = _dt.fromisocalendar(year, w, 1).date()
                except ValueError:
                    first_day = date(year, 1, 1)
                st.session_state["binder_anchor_date"] = first_day.isoformat()
                st.session_state["_binder_view_pending"] = "month"
                st.rerun()
    # Month labels under the strip — line up with weeks
    month_labels = (
        "<div style='display:flex;justify-content:space-between;"
        "font-size:0.7em;opacity:0.6;margin-top:2px'>"
        + "".join(f"<span>{m}</span>" for m in
                   ["Jan","Feb","Mar","Apr","May","Jun",
                    "Jul","Aug","Sep","Oct","Nov","Dec"])
        + "</div>"
    )
    st.markdown(month_labels, unsafe_allow_html=True)

    st.caption(
        "12 mini-calendars · click a month name to jump to its Month view, "
        "or a day to select it"
    )
    day_cats = _day_categories_for_year(db, case_id, year)
    cols = st.columns(4)
    for m in range(1, 13):
        with cols[(m - 1) % 4]:
            _render_mini_month_clickable(year, m, day_cats)

    with st.sidebar:
        st.markdown(f"### {year} stats")
        st.metric("Total entries", stats["total_entries"])
        st.write(f"📅 Court: {stats['court_appearance']}")
        st.write(f"📥 Disclosure: {stats['disclosure']}")
        st.write(f"📨 Counsel: {stats['counsel_correspondence']}")
        st.write(f"🗓 Personal: {stats['personal_event']}")
        st.write(f"📧 Emails: {stats['emails']}")
        st.write(f"💬 Chats: {stats['chats']}")
        st.write(f"📷 Photos: {stats['photos']}")
        st.write(f"📄 Documents: {stats['documents']}")


def _density_color(t: float) -> str:
    if t == 0:
        return "#e2e8f0"
    if t < 0.25:
        return "#cbd5e1"
    if t < 0.5:
        return "#94a3b8"
    if t < 0.75:
        return "#475569"
    return "#1e293b"


def _day_categories_for_year(db, case_id, year) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT date, category FROM timeline_events
               WHERE case_id=? AND substr(date,1,4)=? AND category IN
                   ('court_appearance','disclosure','counsel_correspondence','personal_event')""",
            (case_id, str(year))).fetchall()
    for r in rows:
        out.setdefault(r["date"], set()).add(r["category"])
    return out


def _render_mini_month_clickable(year: int, month: int, day_cats: dict[str, set[str]]):
    """Render a clickable mini-month — month name jumps to month view,
    each day cell selects that day and switches to month view.

    Uses a flat 7-column grid (not week-by-week) so columns align
    perfectly across all rows of the month."""
    import calendar as cal
    # Month-name button
    if st.button(f"**{cal.month_name[month]}**",
                  key=f"yr_month_{year}_{month}",
                  use_container_width=True):
        st.session_state["binder_anchor_date"] = f"{year:04d}-{month:02d}-01"
        st.session_state["_binder_view_pending"] = "month"
        st.rerun()

    cal_obj = cal.Calendar(firstweekday=6)
    weeks = cal_obj.monthdayscalendar(year, month)

    # Flatten into a single sequence of cells (header + days), padded with
    # blanks to maintain exact 7-column alignment.
    cells: list[tuple[str, str | int]] = []
    for dow in ["S", "M", "T", "W", "T", "F", "S"]:
        cells.append(("dow", dow))
    for week in weeks:
        for day in week:
            cells.append(("day" if day else "blank", day))

    # Render in a 7-wide grid — Streamlit creates one column-grid per row;
    # because every row is exactly 7 cells with no breaks, each column
    # has the same width and they line up vertically.
    for row_start in range(0, len(cells), 7):
        row = cells[row_start:row_start + 7]
        cols = st.columns(7)
        for col, (kind, val) in zip(cols, row):
            with col:
                if kind == "dow":
                    st.markdown(
                        f"<div style='text-align:center;opacity:0.5;font-size:0.72em;line-height:1.2'>{val}</div>",
                        unsafe_allow_html=True,
                    )
                elif kind == "day":
                    iso = f"{year:04d}-{month:02d}-{val:02d}"
                    categories = day_cats.get(iso, set())
                    btn_type = "primary" if categories else "secondary"
                    if st.button(str(val), key=f"yr_day_{iso}",
                                  use_container_width=True, type=btn_type):
                        st.session_state["binder_selected_date"] = iso
                        st.session_state["binder_anchor_date"] = iso
                        st.session_state["_binder_view_pending"] = "month"
                        st.rerun()
                else:
                    st.markdown("<div>&nbsp;</div>", unsafe_allow_html=True)


def _render_mini_month(year: int, month: int, day_cats: dict[str, set[str]]):
    """Legacy HTML mini-month — kept for tests and back-compat. Not clickable."""
    import calendar as cal
    st.markdown(f"**{cal.month_name[month]}**")
    cal_obj = cal.Calendar(firstweekday=6)
    weeks = cal_obj.monthdayscalendar(year, month)
    cells = "<table style='width:100%;font-size:0.7em;border-collapse:collapse'>"
    for week in weeks:
        cells += "<tr>"
        for day in week:
            if day == 0:
                cells += "<td></td>"
                continue
            iso = f"{year:04d}-{month:02d}-{day:02d}"
            color = day_category_color(day_cats.get(iso, set()))
            style = f"background:{color};" if color else ""
            cells += f"<td style='text-align:center;padding:2px;{style}'>{day}</td>"
        cells += "</tr>"
    cells += "</table>"
    st.markdown(cells, unsafe_allow_html=True)
