"""Tests for FTS5 one-time backfill of pre-existing rows."""
from casepulse.storage.database import Database


def test_fts_backfill_existing_emails(tmp_path):
    """Pre-existing emails get indexed when FTS5 backfill runs."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    # Insert emails BEFORE FTS triggers exist (simulate pre-W1 data)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'a@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Old subject', 'Old body about custody', 'a@x.com', '<m1>',
                'h1', ?)
    """, (acct_id,))
    conn.commit()
    # Remove the FTS entry to simulate pre-W1 state (contentless FTS5 can't use DELETE)
    # Use special FTS5 delete command for the row we just inserted
    email_id = cur.lastrowid
    cur.execute(
        "INSERT INTO emails_fts(emails_fts, rowid, subject, body_text) "
        "VALUES('delete', ?, 'Old subject', 'Old body about custody')",
        (email_id,)
    )
    conn.commit()
    # Re-init triggers backfill
    db2 = Database(str(db_path))
    conn = db2._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT rowid FROM emails_fts WHERE emails_fts MATCH 'custody'")
    assert len(cur.fetchall()) == 1
