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


def _seed_email(db, *, case_id, date_received, sender, subject):
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO emails (subject, sender_email, sender_name,
                                    date_received, date_sent, body_text)
               VALUES (?, ?, ?, ?, ?, '')""",
            (subject, sender, sender, date_received, date_received),
        )
        eid = cur.lastrowid
        conn.execute(
            """INSERT INTO evidence_tags (item_type, item_id, case_id)
               VALUES ('email', ?, ?)""",
            (eid, case_id),
        )
        return eid


def test_aggregate_includes_case_scoped_emails(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    _seed_email(db, case_id=case_id,
                 date_received="2024-03-14T10:14:00",
                 sender="doe@crown.on.ca", subject="Re: disclosure")
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO emails (subject, sender_email, date_received)
               VALUES ('untagged', 'x@y', '2024-03-14T11:00:00')""",
        )
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    sources = [it.source for it in items]
    assert "email" in sources
    assert sum(1 for s in sources if s == "email") == 1


def test_aggregate_email_other_case_excluded(tmp_db):
    db = tmp_db
    case_a = db.create_case(name="A", case_type="family")
    case_b = db.create_case(name="B", case_type="criminal")
    _seed_email(db, case_id=case_b,
                 date_received="2024-03-14T10:00:00",
                 sender="x@y", subject="B email")
    items = aggregate(db, case_id=case_a,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    assert items == []
