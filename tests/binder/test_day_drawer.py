from datetime import datetime
from casepulse.binder.models import AggregatedItem, CrossRef
from casepulse.binder.day_drawer import (
    format_time_label, source_badge, format_cross_ref,
)


def test_format_time_label_with_hhmm():
    it = AggregatedItem(when=datetime(2024, 3, 14, 9, 0),
                        source="timeline_event", source_id=1,
                        category="court_appearance", title="x")
    assert format_time_label(it) == "09:00"


def test_format_time_label_midnight_means_no_time():
    it = AggregatedItem(when=datetime(2024, 3, 14, 0, 0),
                        source="timeline_event", source_id=1,
                        category="personal_event", title="x")
    assert format_time_label(it) == "—"


def test_source_badge_has_emoji():
    it = AggregatedItem(when=datetime(2024, 3, 14, 9, 0),
                        source="email", source_id=1,
                        category="email", title="x")
    badge = source_badge(it)
    assert "📧" in badge


def test_format_cross_ref_argument():
    cr = CrossRef(target_type="argument", target_id=2,
                  relationship="supports", label="Argument #2")
    label = format_cross_ref(cr)
    assert ("supports" in label.lower()) or ("in argument" in label.lower())
