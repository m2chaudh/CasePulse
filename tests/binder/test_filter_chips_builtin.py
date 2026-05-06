from datetime import date
from casepulse.binder.models import (
    BinderCategory, ChipFilter, PersonalEventMetadata,
    CourtAppearanceMetadata, Forum,
)
from casepulse.binder.repository import create_binder_entry
from casepulse.binder.aggregator import aggregate
from casepulse.binder.filter_chips_builtin import (
    BUILTIN_CHIPS, chip_to_filter,
)


def test_chip_ids():
    ids = [c["id"] for c in BUILTIN_CHIPS]
    assert ids == ["all", "court", "disclosure", "counsel", "personal",
                   "emails", "chats", "photos", "docs"]


def test_court_chip_filter_only_court_entries(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                        category=BinderCategory.COURT_APPEARANCE,
                        title="Court", summary="",
                        metadata=CourtAppearanceMetadata(forum=Forum.CRIMINAL))
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="Dinner", summary="",
                        metadata=PersonalEventMetadata())
    chip = chip_to_filter("court")
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14),
                      chip_filter=chip)
    assert [it.title for it in items] == ["Court"]


def test_emails_chip_filter_only_emails(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO emails (subject, sender_email, date_received)
               VALUES ('S', 'x@y', '2024-03-14T10:00:00')""")
        eid = cur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('email', ?, ?)",
            (eid, case_id))
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                        category=BinderCategory.PERSONAL_EVENT,
                        title="Dinner", summary="",
                        metadata=PersonalEventMetadata())
    chip = chip_to_filter("emails")
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14),
                      chip_filter=chip)
    sources = {it.source for it in items}
    assert sources == {"email"}
