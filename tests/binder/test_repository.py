import json
import pytest
from datetime import datetime
from casepulse.binder.models import (
    BinderCategory, CourtAppearanceMetadata, DisclosureMetadata,
    DisclosureKind, CounselCorrespondenceMetadata, CounselParty,
    PersonalEventMetadata, Forum,
)
from casepulse.binder.repository import (
    create_binder_entry, get_binder_entry, list_binder_entries_for_day,
    update_binder_entry, delete_binder_entry,
)


def test_create_court_appearance(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    md = CourtAppearanceMetadata(forum=Forum.CRIMINAL, court_name="OCJ", purpose="first_appearance")
    entry_id = create_binder_entry(
        db, case_id=case_id, date="2024-03-14", time="09:00",
        category=BinderCategory.COURT_APPEARANCE,
        title="First appearance", summary="OCJ Toronto",
        metadata=md,
    )
    assert entry_id > 0
    fetched = get_binder_entry(db, entry_id)
    assert fetched is not None
    assert fetched["category"] == "court_appearance"
    assert json.loads(fetched["metadata_json"])["court_name"] == "OCJ"


def test_list_for_day(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    md = PersonalEventMetadata(location="home")
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="19:30",
                       category=BinderCategory.PERSONAL_EVENT,
                       title="Dinner", summary="", metadata=md)
    create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                       category=BinderCategory.PERSONAL_EVENT,
                       title="No-time event", summary="", metadata=md)
    create_binder_entry(db, case_id=case_id, date="2024-03-15", time="",
                       category=BinderCategory.PERSONAL_EVENT,
                       title="Other day", summary="", metadata=md)
    rows = list_binder_entries_for_day(db, case_id=case_id, date="2024-03-14")
    titles = sorted(r["title"] for r in rows)
    assert titles == ["Dinner", "No-time event"]


def test_update(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    md = DisclosureMetadata(kind=DisclosureKind.CROWN, direction="received", page_count=10)
    entry_id = create_binder_entry(
        db, case_id=case_id, date="2024-03-14", time="",
        category=BinderCategory.DISCLOSURE,
        title="Initial disclosure", summary="", metadata=md,
    )
    md2 = DisclosureMetadata(kind=DisclosureKind.CROWN, direction="received",
                              page_count=47, completion_status="expecting_more")
    update_binder_entry(db, entry_id, title="Initial disclosure (47pp)", metadata=md2)
    fetched = get_binder_entry(db, entry_id)
    assert fetched["title"] == "Initial disclosure (47pp)"
    assert json.loads(fetched["metadata_json"])["page_count"] == 47


def test_delete(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    md = PersonalEventMetadata()
    entry_id = create_binder_entry(db, case_id=case_id, date="2024-03-14", time="",
                                   category=BinderCategory.PERSONAL_EVENT,
                                   title="x", summary="", metadata=md)
    delete_binder_entry(db, entry_id)
    assert get_binder_entry(db, entry_id) is None
