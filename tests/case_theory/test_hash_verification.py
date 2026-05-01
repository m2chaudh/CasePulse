# tests/case_theory/test_hash_verification.py
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.repository import (
    create_evidence, verify_evidence_hash,
)


def test_hash_verifies(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO accounts (provider, email) VALUES ('gmail', 'a@x.com')")
    conn.commit()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('S', 'Original body', 'a@x', '<m>', 'h', 1)
    """)
    conn.commit()
    eid = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=eid,
    ))
    assert verify_evidence_hash(db, e.id) is True


def test_hash_mismatch_detected(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO accounts (provider, email) VALUES ('gmail', 'b@x.com')")
    conn.commit()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('S', 'Original body', 'a@x', '<m>', 'h', 1)
    """)
    conn.commit()
    eid = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=eid,
    ))
    cur.execute("UPDATE emails SET body_text = 'TAMPERED' WHERE id = ?", (eid,))
    conn.commit()
    assert verify_evidence_hash(db, e.id) is False
