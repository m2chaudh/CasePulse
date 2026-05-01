# tests/case_theory/test_evidence_resolver.py
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.evidence_resolver import resolve, ResolvedSource


def test_resolve_email(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id, date_received)
        VALUES ('Subject', 'Body content', 'a@x.com', '<m1>', 'h1', NULL,
                '2024-03-14 10:00')
    """)
    conn.commit()
    eid = cur.lastrowid
    e = Evidence(evidence_kind=EvidenceKind.EMAIL,
                 source_table="emails", source_row_id=eid)
    resolved = resolve(db, e)
    assert resolved.kind == "email"
    assert resolved.text == "Body content"
    assert resolved.metadata["subject"] == "Subject"
    assert resolved.metadata["sender_email"] == "a@x.com"
