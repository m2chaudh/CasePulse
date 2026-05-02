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


def _seed_chat(db, *, case_id, ts, sender, text):
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO chat_messages (source_type, platform, sender,
                                            timestamp, message_text)
               VALUES ('whatsapp', 'whatsapp', ?, ?, ?)""",
            (sender, ts, text),
        )
        cid = cur.lastrowid
        conn.execute(
            """INSERT INTO evidence_tags (item_type, item_id, case_id)
               VALUES ('chat', ?, ?)""",
            (cid, case_id),
        )
        return cid


def test_aggregate_includes_chats(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    _seed_chat(db, case_id=case_id, ts="2024-03-14T15:30:00",
                sender="Sarah", text="see you at 7")
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    chats = [it for it in items if it.source == "chat"]
    assert len(chats) == 1
    assert "Sarah" in chats[0].title


def _seed_doc(db, *, case_id, filename, content_hash, created_at):
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES (?, ?, ?, ?)""",
            (filename, f"/tmp/{filename}", content_hash, created_at),
        )
        did = cur.lastrowid
        conn.execute(
            """INSERT INTO evidence_tags (item_type, item_id, case_id)
               VALUES ('document', ?, ?)""",
            (did, case_id),
        )
        return did


def _seed_attachment(db, *, case_id, filename, created_at, email_id=None):
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO attachments (email_id, filename, created_at)
               VALUES (?, ?, ?)""",
            (email_id, filename, created_at),
        )
        aid = cur.lastrowid
        conn.execute(
            """INSERT INTO evidence_tags (item_type, item_id, case_id)
               VALUES ('attachment', ?, ?)""",
            (aid, case_id),
        )
        return aid


def test_aggregate_documents(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    _seed_doc(db, case_id=case_id, filename="affidavit.pdf",
              content_hash="abc", created_at="2024-03-14T08:00:00")
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    docs = [it for it in items if it.source == "document"]
    assert len(docs) == 1
    assert docs[0].title == "affidavit.pdf"


def test_aggregate_attachments(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    _seed_attachment(db, case_id=case_id, filename="brief.pdf",
                     created_at="2024-03-14T11:00:00")
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    atts = [it for it in items if it.source == "attachment"]
    assert len(atts) == 1
