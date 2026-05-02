import json
from casepulse.binder.attach_to_day import attach_item_to_day
from casepulse.binder.repository import list_links_to, get_binder_entry


def test_attach_creates_anchor_and_link(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES ('a.pdf','/tmp/a.pdf','h','2024-03-10T08:00:00')""")
        doc_id = cur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('document', ?, ?)",
            (doc_id, case_id))
    anchor_id = attach_item_to_day(
        db, case_id=case_id, day="2024-03-14",
        item_type="document", item_id=doc_id,
    )
    row = get_binder_entry(db, anchor_id)
    md = json.loads(row["metadata_json"])
    assert md["is_day_anchor"] is True
    inc = list_links_to(db, case_id=case_id,
                       to_type="timeline_event", to_id=anchor_id)
    assert any(r["from_type"] == "document" and r["from_id"] == doc_id
               and r["relationship"] == "part_of" for r in inc)


def test_attach_reuses_existing_anchor(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        c1 = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES ('a.pdf','/tmp/a.pdf','h','2024-03-10T08:00:00')""")
        d1 = c1.lastrowid
        c2 = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES ('b.pdf','/tmp/b.pdf','h2','2024-03-10T09:00:00')""")
        d2 = c2.lastrowid
        for d in (d1, d2):
            conn.execute(
                "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('document', ?, ?)",
                (d, case_id))
    a1 = attach_item_to_day(db, case_id=case_id, day="2024-03-14",
                            item_type="document", item_id=d1)
    a2 = attach_item_to_day(db, case_id=case_id, day="2024-03-14",
                            item_type="document", item_id=d2)
    assert a1 == a2
