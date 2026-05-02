import pytest
from datetime import date, datetime
from casepulse.binder.models import (
    BinderCategory, PersonalEventMetadata, ChipFilter,
    CourtAppearanceMetadata, Forum,
)
from casepulse.binder.repository import create_binder_entry
from casepulse.binder.aggregator import aggregate


def test_aggregate_timeline_events_only(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="09:00",
                        category=BinderCategory.COURT_APPEARANCE,
                        title="OCJ first appearance", summary="",
                        metadata=CourtAppearanceMetadata(forum=Forum.CRIMINAL))
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="19:30",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="Dinner", summary="",
                        metadata=PersonalEventMetadata(location="home"))
    create_binder_entry(db, case_id=case_id, date="2024-03-15", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="Other day", summary="",
                        metadata=PersonalEventMetadata())

    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    titles = [it.title for it in items]
    assert titles == ["OCJ first appearance", "Dinner"]
    assert items[0].when.hour == 9
    assert items[1].when.hour == 19


def test_aggregate_other_case_excluded(tmp_db):
    db = tmp_db
    case_a = db.create_case(name="A", case_type="family")
    case_b = db.create_case(name="B", case_type="criminal")
    create_binder_entry(db, case_id=case_a, date="2024-03-14", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="A's event", summary="",
                        metadata=PersonalEventMetadata())
    create_binder_entry(db, case_id=case_b, date="2024-03-14", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="B's event", summary="",
                        metadata=PersonalEventMetadata())
    items = aggregate(db, case_id=case_a,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    assert [it.title for it in items] == ["A's event"]
