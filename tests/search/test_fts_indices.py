"""Tests for FTS5 virtual tables and triggers."""
import pytest


def test_emails_fts_table_exists(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE name='emails_fts'")
    assert cur.fetchone() is not None


def test_emails_fts_index_on_insert(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    # Insert an account so FK is satisfied
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'alice@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("Test subject", "Body about custody hearing", "alice@x.com",
          "<m1@x>", "hash1", acct_id))
    conn.commit()
    cur.execute("""
        SELECT rowid FROM emails_fts WHERE emails_fts MATCH 'custody'
    """)
    rows = cur.fetchall()
    assert len(rows) == 1


def test_chat_messages_fts_search(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x', 'Alice', '2024-01-01', 'meeting at 3pm',
                'h1')
    """)
    conn.commit()
    cur.execute("SELECT rowid FROM chat_messages_fts WHERE chat_messages_fts MATCH 'meeting'")
    assert len(cur.fetchall()) == 1


def test_attachments_fts_search(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'b@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Subject', 'body', 'a@x.com', '<m2>', 'h2', ?)
    """, (acct_id,))
    email_id = cur.lastrowid
    cur.execute("""
        INSERT INTO attachments (email_id, filename, extracted_text, content_hash)
        VALUES (?, 'report.pdf', 'Financial statement balance sheet', 'h3')
    """, (email_id,))
    conn.commit()
    cur.execute(
        "SELECT rowid FROM attachments_fts WHERE attachments_fts MATCH 'financial'"
    )
    assert len(cur.fetchall()) == 1


def test_documents_fts_search(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_hash, extracted_text)
        VALUES ('contract.pdf', '/tmp/contract.pdf', 'h4', 'contract terms agreement')
    """)
    conn.commit()
    cur.execute(
        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH 'contract'"
    )
    assert len(cur.fetchall()) == 1


def test_annotations_fts_search(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO annotations (item_type, item_id, note_text)
        VALUES ('email', 1, 'Important note about visitation rights')
    """)
    conn.commit()
    cur.execute(
        "SELECT rowid FROM annotations_fts WHERE annotations_fts MATCH 'visitation'"
    )
    assert len(cur.fetchall()) == 1
