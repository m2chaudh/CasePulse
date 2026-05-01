"""Tests for BM25 search over FTS5 virtual tables."""
from casepulse.search.fts import bm25_search


def test_bm25_returns_citations(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'a@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Custody hearing', 'Discussion about access schedule',
                'a@x.com', '<m1>', 'h1', ?)
    """, (acct_id,))
    conn.commit()
    hits = bm25_search(db, "custody", k=10)
    assert len(hits) == 1
    assert hits[0].citation.table == "emails"
    assert hits[0].citation.row_id == 1
    assert "Custody" in hits[0].citation.snippet


def test_bm25_facet_source_type(tmp_db_with_case):
    """Source type filter restricts to one FTS table."""
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'a@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Email subject', 'banana', 'a@x.com', '<m1>', 'h1', ?)
    """, (acct_id,))
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x', 'A', '2024-01-01', 'banana', 'h2')
    """)
    conn.commit()
    hits = bm25_search(db, "banana", k=10, source_types=["chat_messages"])
    assert len(hits) == 1
    assert hits[0].citation.table == "chat_messages"
