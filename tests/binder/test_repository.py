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
    create_filter_chip, list_filter_chips, delete_filter_chip,
    upsert_relevant_sender, list_relevant_senders,
    deactivate_relevant_sender,
    create_item_link, list_links_from, list_links_to, delete_item_link,
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


def test_filter_chip_roundtrip(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    chip_id = create_filter_chip(
        db, case_id=case_id, label="Witness mentions", emoji="★",
        filter_json={"witness_id": "any"}, pinned=True, sort_order=0,
    )
    chips = list_filter_chips(db, case_id=case_id)
    assert len(chips) == 1
    assert chips[0]["label"] == "Witness mentions"
    assert chips[0]["pinned"] == 1
    delete_filter_chip(db, chip_id)
    assert list_filter_chips(db, case_id=case_id) == []


def test_relevant_sender_upsert(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    sid = upsert_relevant_sender(
        db, case_id=case_id, address="doe@crown.on.ca",
        role="crown", display_name="A. Doe",
    )
    assert sid > 0
    sid2 = upsert_relevant_sender(
        db, case_id=case_id, address="doe@crown.on.ca",
        role="crown", display_name="Andrea Doe",
    )
    assert sid == sid2
    rows = list_relevant_senders(db, case_id=case_id)
    assert len(rows) == 1
    assert rows[0]["display_name"] == "Andrea Doe"


def test_relevant_sender_deactivate(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    sid = upsert_relevant_sender(db, case_id=case_id, address="x@y.com", role="other")
    deactivate_relevant_sender(db, sid)
    rows = list_relevant_senders(db, case_id=case_id, active_only=True)
    assert rows == []


def test_item_link_roundtrip(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    link_id = create_item_link(
        db, case_id=case_id,
        from_type="email", from_id=10,
        to_type="timeline_event", to_id=20,
        relationship="responds_to", note="reply chain",
    )
    assert link_id > 0
    out = list_links_from(db, case_id=case_id, from_type="email", from_id=10)
    assert len(out) == 1
    assert out[0]["relationship"] == "responds_to"
    inc = list_links_to(db, case_id=case_id, to_type="timeline_event", to_id=20)
    assert len(inc) == 1


def test_item_link_unique(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_item_link(db, case_id=case_id,
                     from_type="email", from_id=10,
                     to_type="timeline_event", to_id=20,
                     relationship="related")
    create_item_link(db, case_id=case_id,
                     from_type="email", from_id=10,
                     to_type="timeline_event", to_id=20,
                     relationship="related")
    out = list_links_from(db, case_id=case_id, from_type="email", from_id=10)
    assert len(out) == 1


def test_item_link_delete(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    link_id = create_item_link(db, case_id=case_id,
                               from_type="document", from_id=1,
                               to_type="timeline_event", to_id=2,
                               relationship="part_of")
    delete_item_link(db, link_id)
    assert list_links_from(db, case_id=case_id, from_type="document", from_id=1) == []
