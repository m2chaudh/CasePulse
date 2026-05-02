"""Wrapper around streamlit-calendar for the month/week/day views."""

from __future__ import annotations
from typing import Optional
from streamlit_calendar import calendar
from casepulse.binder.models import AggregatedItem


FC_VIEW_FOR = {
    "month": "dayGridMonth",
    "week":  "timeGridWeek",
    "day":   "timeGridDay",
}


_TIMELINE_EVENT_EMOJI = {
    "court_appearance":       "📅",
    "disclosure":             "📥",
    "counsel_correspondence": "📨",
    "personal_event":         "🗓",
}


_OTHER_SOURCE_EMOJI = {
    "email":      "📧",
    "chat":       "💬",
    "document":   "📄",
    "attachment": "📎",
    "photo":      "📷",
}


_COLORS = {
    "court_appearance":       "#92400e",
    "disclosure":             "#14532d",
    "counsel_correspondence": "#831843",
    "personal_event":         "#7f1d1d",
    "email":                  "#5b21b6",
    "chat":                   "#3730a3",
    "document":               "#44403c",
    "attachment":             "#44403c",
    "photo":                  "#155e75",
}


def _emoji_for(item: AggregatedItem) -> str:
    if item.source == "timeline_event":
        return _TIMELINE_EVENT_EMOJI.get(item.category, "📅")
    return _OTHER_SOURCE_EMOJI.get(item.source, "•")


def item_color_key(it: AggregatedItem) -> str:
    if it.source == "timeline_event":
        return it.category
    return it.source


def items_to_fc_events(items: list[AggregatedItem]) -> list[dict]:
    """Convert aggregator output into FullCalendar event dicts."""
    out: list[dict] = []
    for it in items:
        color = _COLORS.get(item_color_key(it), "#475569")
        out.append({
            "title": f"{_emoji_for(it)} {it.title}",
            "start": it.when.isoformat(),
            "end":   it.when.isoformat(),
            "backgroundColor": color,
            "borderColor":     color,
            "extendedProps": {
                "source": it.source,
                "source_id": it.source_id,
                "category": it.category,
            },
        })
    return out


def render_calendar(
    items: list[AggregatedItem], *,
    view: str,
    initial_date: str,
    selected_date: Optional[str] = None,
) -> Optional[str]:
    """Render the calendar. Returns the clicked date (YYYY-MM-DD) if any.

    `selected_date` (YYYY-MM-DD) renders a red highlight on that day so
    the user can see which day the drawer below is showing."""
    fc_view = FC_VIEW_FOR[view]
    options = {
        "initialView": fc_view,
        "initialDate": initial_date,
        "headerToolbar": False,
        "selectable": True,
        "navLinks": True,
        "dayMaxEvents": 4,
        "height": 720,
    }
    events = items_to_fc_events(items)

    # Phantom 'background' event on the selected day → renders as a
    # tinted overlay with a red border, so the user sees their selection.
    if selected_date:
        events.append({
            "id": "binder-selected-day-marker",
            "start": selected_date,
            "end": selected_date,
            "display": "background",
            "backgroundColor": "rgba(220, 50, 47, 0.18)",
            "borderColor": "#dc322f",
        })

    state = calendar(events=events, options=options, key=f"binder_cal_{view}")
    if not state:
        return None

    # streamlit-calendar's state shape varies between versions:
    #   - older: state["callback"] = "dateClick", state["dateClick"] = {...}
    #   - newer: state["dateClick"] = {...} populated directly without "callback"
    # Handle both. Also handle "select" (drag-select) and "eventClick"
    # (clicking an event chip — return that day too).
    def _coerce_date(val):
        if not val:
            return None
        if isinstance(val, str):
            return val[:10]
        if isinstance(val, dict):
            for k in ("date", "start", "dateStr"):
                if val.get(k):
                    return str(val[k])[:10]
        return None

    for key in ("dateClick", "select", "eventClick"):
        payload = state.get(key)
        if not payload:
            continue
        d = _coerce_date(payload)
        if d:
            return d
    return None
