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


def test_aggregate_includes_case_scoped_and_untagged_emails(tmp_db_with_case):
    """Auto-aggregation design: emails tagged to this case AND untagged
    emails BOTH show on the calendar. Only items explicitly tagged to a
    *different* case are excluded (see test_aggregate_email_other_case_excluded).
    """
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
    assert sum(1 for s in sources if s == "email") == 2


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


from casepulse.binder.repository import create_item_link


def test_cross_refs_from_item_links(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    eid = _seed_email(db, case_id=case_id,
                       date_received="2024-03-14T10:14:00",
                       sender="x@y", subject="reply")
    tl_id = create_binder_entry(
        db, case_id=case_id, date="2024-03-14", time="09:00",
        category=BinderCategory.COURT_APPEARANCE,
        title="OCJ", summary="",
        metadata=CourtAppearanceMetadata(forum=Forum.CRIMINAL),
    )
    create_item_link(db, case_id=case_id,
                     from_type="email", from_id=eid,
                     to_type="timeline_event", to_id=tl_id,
                     relationship="responds_to")

    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    email_item = next(it for it in items if it.source == "email")
    assert any(cr.target_id == tl_id and cr.relationship == "responds_to"
               for cr in email_item.cross_refs)


def test_cross_refs_from_argument_evidence(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    eid = _seed_email(db, case_id=case_id,
                       date_received="2024-03-14T10:14:00",
                       sender="x@y", subject="hi")
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO contradictions (case_id, headline, status)
               VALUES (?, 'C', 'draft')""", (case_id,))
        contradiction_id = cur.lastrowid
        cur = conn.execute(
            """INSERT INTO arguments (contradiction_id, title, argument_type, strength)
               VALUES (?, 'A', 'documentary', 'moderate')""",
            (contradiction_id,))
        arg_id = cur.lastrowid
        # evidence table holds the source pointer; argument_evidence links argument -> evidence
        cur = conn.execute(
            """INSERT INTO evidence (evidence_kind, source_table, source_row_id)
               VALUES ('email', 'emails', ?)""",
            (eid,))
        ev_id = cur.lastrowid
        conn.execute(
            """INSERT INTO argument_evidence (argument_id, evidence_id, role)
               VALUES (?, ?, 'supports')""",
            (arg_id, ev_id))
    items = aggregate(db, case_id=case_id,
                      date_start=date(2024, 3, 14), date_end=date(2024, 3, 14))
    email_item = next(it for it in items if it.source == "email")
    arg_refs = [cr for cr in email_item.cross_refs if cr.target_type == "argument"]
    assert len(arg_refs) == 1
    assert arg_refs[0].relationship == "supports"
