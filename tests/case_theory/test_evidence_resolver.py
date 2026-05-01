# tests/case_theory/test_evidence_resolver.py
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.evidence_resolver import resolve, ResolvedSource


# ── Happy-path tests ──────────────────────────────────────────────────────────

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


def test_resolve_chat(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, platform, chat_name,
                                    sender, timestamp, message_text, content_hash)
        VALUES ('whatsapp_txt', '/tmp/chat.txt', 'WhatsApp', 'Family Chat',
                'Alice', '2024-01-10 09:30:00', 'Hello there', 'h_chat1')
    """)
    conn.commit()
    row_id = cur.lastrowid
    e = Evidence(evidence_kind=EvidenceKind.CHAT,
                 source_table="chat_messages", source_row_id=row_id)
    resolved = resolve(db, e)
    assert resolved.kind == "chat"
    assert resolved.text == "Hello there"
    assert resolved.metadata["sender"] == "Alice"
    assert resolved.metadata["chat_name"] == "Family Chat"
    assert resolved.metadata["platform"] == "WhatsApp"


def test_resolve_attachment(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    # Need an email row first (FK)
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Att Test', '', 'b@x.com', '<m2>', 'h2', NULL)
    """)
    conn.commit()
    email_id = cur.lastrowid
    cur.execute("""
        INSERT INTO attachments (email_id, filename, content_type, size_bytes,
                                  file_path, extracted_text, content_hash)
        VALUES (?, 'report.pdf', 'application/pdf', 1024, '/data/report.pdf',
                'Extracted PDF text', 'h_att1')
    """, (email_id,))
    conn.commit()
    att_id = cur.lastrowid
    e = Evidence(evidence_kind=EvidenceKind.ATTACHMENT,
                 source_table="attachments", source_row_id=att_id)
    resolved = resolve(db, e)
    assert resolved.kind == "attachment"
    assert resolved.text == "Extracted PDF text"
    assert resolved.metadata["filename"] == "report.pdf"
    assert resolved.metadata["content_type"] == "application/pdf"
    assert resolved.file_path == "/data/report.pdf"


def test_resolve_document(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_type, size_bytes,
                                content_hash, extracted_text, timeline_date)
        VALUES ('contract.pdf', '/docs/contract.pdf', 'application/pdf', 2048,
                'h_doc1', 'Contract text here', '2024-06-01')
    """)
    conn.commit()
    doc_id = cur.lastrowid
    e = Evidence(evidence_kind=EvidenceKind.DOCUMENT,
                 source_table="documents", source_row_id=doc_id)
    resolved = resolve(db, e)
    assert resolved.kind == "document"
    assert resolved.text == "Contract text here"
    assert resolved.metadata["filename"] == "contract.pdf"
    assert resolved.metadata["date"] == "2024-06-01"
    assert resolved.file_path == "/docs/contract.pdf"


def test_resolve_annotation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO annotations (item_type, item_id, case_id, note_text)
        VALUES ('email', 5, ?, 'Important note about this email')
    """, (case_id,))
    conn.commit()
    ann_id = cur.lastrowid
    # EvidenceKind has no ANNOTATION; use EMAIL kind with annotations table
    # (resolver dispatches on source_table, not evidence_kind)
    e = Evidence(evidence_kind=EvidenceKind.EMAIL,
                 source_table="annotations", source_row_id=ann_id)
    resolved = resolve(db, e)
    assert resolved.kind == "annotation"
    assert resolved.text == "Important note about this email"
    assert resolved.metadata["item_type"] == "email"
    assert resolved.metadata["item_id"] == 5


# ── Deleted-source sentinel tests ─────────────────────────────────────────────

def test_resolve_deleted_email(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Del', 'body', 'c@x.com', '<m3>', 'h3', NULL)
    """)
    conn.commit()
    eid = cur.lastrowid
    # Delete the source row
    cur.execute("DELETE FROM emails WHERE id = ?", (eid,))
    conn.commit()
    e = Evidence(evidence_kind=EvidenceKind.EMAIL,
                 source_table="emails", source_row_id=eid)
    resolved = resolve(db, e)
    assert resolved.metadata["deleted"] is True
    assert resolved.metadata["source_table"] == "emails"
    assert resolved.metadata["source_row_id"] == eid


def test_resolve_deleted_chat(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp_txt', '/tmp/x.txt', 'Bob', '2024-01-01 10:00',
                'Bye', 'h_chat2')
    """)
    conn.commit()
    row_id = cur.lastrowid
    cur.execute("DELETE FROM chat_messages WHERE id = ?", (row_id,))
    conn.commit()
    e = Evidence(evidence_kind=EvidenceKind.CHAT,
                 source_table="chat_messages", source_row_id=row_id)
    resolved = resolve(db, e)
    assert resolved.metadata["deleted"] is True
    assert resolved.metadata["source_table"] == "chat_messages"


def test_resolve_deleted_attachment(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Att Del', '', 'd@x.com', '<m4>', 'h4', NULL)
    """)
    conn.commit()
    email_id = cur.lastrowid
    cur.execute("""
        INSERT INTO attachments (email_id, filename, content_type, size_bytes,
                                  file_path, content_hash)
        VALUES (?, 'gone.pdf', 'application/pdf', 0, '/gone.pdf', 'h_att2')
    """, (email_id,))
    conn.commit()
    att_id = cur.lastrowid
    cur.execute("DELETE FROM attachments WHERE id = ?", (att_id,))
    conn.commit()
    e = Evidence(evidence_kind=EvidenceKind.ATTACHMENT,
                 source_table="attachments", source_row_id=att_id)
    resolved = resolve(db, e)
    assert resolved.metadata["deleted"] is True
    assert resolved.metadata["source_table"] == "attachments"


def test_resolve_deleted_document(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_hash)
        VALUES ('old.pdf', '/old.pdf', 'h_doc2')
    """)
    conn.commit()
    doc_id = cur.lastrowid
    cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    e = Evidence(evidence_kind=EvidenceKind.DOCUMENT,
                 source_table="documents", source_row_id=doc_id)
    resolved = resolve(db, e)
    assert resolved.metadata["deleted"] is True
    assert resolved.metadata["source_table"] == "documents"


def test_resolve_deleted_annotation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO annotations (item_type, item_id, case_id, note_text)
        VALUES ('email', 99, ?, 'Ephemeral note')
    """, (case_id,))
    conn.commit()
    ann_id = cur.lastrowid
    cur.execute("DELETE FROM annotations WHERE id = ?", (ann_id,))
    conn.commit()
    # EvidenceKind has no ANNOTATION; use EMAIL kind — resolver dispatches on source_table
    e = Evidence(evidence_kind=EvidenceKind.EMAIL,
                 source_table="annotations", source_row_id=ann_id)
    resolved = resolve(db, e)
    assert resolved.metadata["deleted"] is True
    assert resolved.metadata["source_table"] == "annotations"
