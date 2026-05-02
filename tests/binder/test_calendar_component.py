from datetime import datetime
from casepulse.binder.models import AggregatedItem
from casepulse.binder.calendar_component import (
    items_to_fc_events, FC_VIEW_FOR,
)


def _item(when, source, title, category):
    return AggregatedItem(
        when=when, source=source, source_id=1,
        category=category, title=title,
    )


def test_items_to_fc_events_groups_by_day():
    items = [
        _item(datetime(2024, 3, 14, 9, 0), "timeline_event",
              "OCJ first appearance", "court_appearance"),
        _item(datetime(2024, 3, 14, 19, 30), "timeline_event",
              "Dinner", "personal_event"),
        _item(datetime(2024, 3, 15, 10, 0), "email", "Sender · subject", "email"),
    ]
    events = items_to_fc_events(items)
    assert len(events) == 3
    titles = [e["title"] for e in events]
    assert any("📅" in t and "OCJ" in t for t in titles)
    assert any("📧" in t for t in titles)


def test_fc_view_for_mapping():
    assert FC_VIEW_FOR["month"] == "dayGridMonth"
    assert FC_VIEW_FOR["week"] == "timeGridWeek"
    assert FC_VIEW_FOR["day"] == "timeGridDay"
