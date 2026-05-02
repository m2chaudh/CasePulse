from datetime import date
from casepulse.binder.year_view import (
    week_activity_counts, year_stats, day_category_color,
)
from casepulse.binder.repository import create_binder_entry
from casepulse.binder.models import (
    BinderCategory, PersonalEventMetadata, CourtAppearanceMetadata, Forum,
)


def test_week_activity_counts(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="x", summary="",
                        metadata=PersonalEventMetadata())
    counts = week_activity_counts(db, case_id=case_id, year=2024)
    assert len(counts) >= 52
    assert sum(counts) >= 1


def test_year_stats(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                        category=BinderCategory.COURT_APPEARANCE,
                        title="x", summary="",
                        metadata=CourtAppearanceMetadata(forum=Forum.CRIMINAL))
    stats = year_stats(db, case_id=case_id, year=2024)
    assert stats["court_appearance"] == 1


def test_day_category_color():
    assert day_category_color({"court_appearance"}) == "#fef3c7"
    assert day_category_color({"personal_event"}) == "#fee2e2"
    assert day_category_color({"disclosure"}) == "#dcfce7"
    assert day_category_color({"counsel_correspondence"}) == "#fce7f3"
    assert day_category_color({"court_appearance", "personal_event"}) == "#fef3c7"
