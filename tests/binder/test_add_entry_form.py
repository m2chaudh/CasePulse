import json
from casepulse.binder.add_entry_form import save_court_appearance
from casepulse.binder.repository import get_binder_entry


def test_save_court_appearance(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_court_appearance(
        db, case_id=case_id, date_str="2024-03-14", time_str="09:00",
        forum="criminal", court_name="OCJ Toronto", judge="Justice X",
        own_counsel="Smith", opposing_counsel="Doe",
        purpose="first_appearance", outcome="set date Mar 20",
        delay_attribution=None,
    )
    row = get_binder_entry(db, entry_id)
    assert row["category"] == "court_appearance"
    md = json.loads(row["metadata_json"])
    assert md["forum"] == "criminal"
    assert md["court_name"] == "OCJ Toronto"
    assert md["delay_attribution"] is None


def test_save_court_appearance_with_delay(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_court_appearance(
        db, case_id=case_id, date_str="2024-03-14", time_str="",
        forum="criminal", court_name="OCJ", judge="",
        own_counsel="", opposing_counsel="", purpose="set_date",
        outcome="",
        delay_attribution={"category": "crown", "days": 14, "note": ""},
    )
    md = json.loads(get_binder_entry(db, entry_id)["metadata_json"])
    assert md["delay_attribution"]["days"] == 14


from casepulse.binder.add_entry_form import save_disclosure


def test_save_disclosure(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_disclosure(
        db, case_id=case_id, date_str="2024-03-14", time_str="",
        kind="crown", direction="received", page_count=47,
        items="synopsis, police report",
        completion_status="expecting_more",
        expected_completion_date="2024-04-13",
        follow_up_email_id=None,
    )
    row = get_binder_entry(db, entry_id)
    md = json.loads(row["metadata_json"])
    assert md["kind"] == "crown"
    assert md["page_count"] == 47
    assert md["completion_status"] == "expecting_more"
    assert md["outstanding_flag"] is False


from casepulse.binder.add_entry_form import save_counsel_correspondence


def test_save_counsel_correspondence_no_email(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    entry_id = save_counsel_correspondence(
        db, case_id=case_id, date_str="2024-03-14", time_str="",
        party="opposing_counsel", linked_email_id=None,
        summary="Letter re Form 13",
        response_required=True, response_due_date="2024-04-01",
    )
    row = get_binder_entry(db, entry_id)
    md = json.loads(row["metadata_json"])
    assert md["party"] == "opposing_counsel"
    assert md["linked_email_id"] is None


def test_save_counsel_correspondence_with_email(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO emails (subject, sender_email, date_received)
               VALUES ('S','x@y','2024-03-14T10:00:00')""")
        eid = cur.lastrowid
    entry_id = save_counsel_correspondence(
        db, case_id=case_id, date_str="2024-03-14", time_str="10:00",
        party="crown", linked_email_id=eid, summary="Re disclosure",
        response_required=False, response_due_date=None,
    )
    md = json.loads(get_binder_entry(db, entry_id)["metadata_json"])
    assert md["linked_email_id"] == eid
    with db._get_conn() as conn:
        row = conn.execute(
            """SELECT legal_issue FROM evidence_tags
               WHERE item_type='email' AND item_id=? AND case_id=?""",
            (eid, case_id),
        ).fetchone()
    assert row["legal_issue"] == "counsel_correspondence"


from casepulse.binder.add_entry_form import save_personal_event
from casepulse.binder.repository import list_links_to


def test_save_personal_event_writes_item_links(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        # Seed a witness — adapt INSERT columns to actual witnesses schema if different
        wcur = conn.execute(
            """INSERT INTO witnesses (case_id, name, witness_type)
               VALUES (?, 'Sarah', 'fact')""", (case_id,))
        witness_id = wcur.lastrowid
        dcur = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES ('a.pdf','/tmp/a.pdf','h','2024-03-14T08:00:00')""")
        doc_id = dcur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('document', ?, ?)",
            (doc_id, case_id))

    entry_id = save_personal_event(
        db, case_id=case_id, date_str="2024-03-14", time_str="19:30",
        time_end="22:00", location="Sarah's residence",
        evidence_relevance="alibi",
        witness_ids=[witness_id], photo_metadata_ids=[],
        document_ids=[doc_id], attachment_ids=[], email_ids=[],
    )
    row = get_binder_entry(db, entry_id)
    md = json.loads(row["metadata_json"])
    assert "witness_ids" not in md
    assert "photo_metadata_ids" not in md
    in_links = list_links_to(db, case_id=case_id,
                              to_type="timeline_event", to_id=entry_id)
    types_ids = sorted((r["from_type"], r["from_id"]) for r in in_links)
    assert types_ids == sorted([("witness", witness_id), ("document", doc_id)])
    assert all(r["relationship"] == "part_of" for r in in_links)
