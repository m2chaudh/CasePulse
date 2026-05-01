"""Tests for chat_messages.content_hash backfill migration."""
import hashlib
from casepulse.storage.database import Database


def test_backfill_populates_existing_chat_hashes(tmp_path):
    """Existing chat rows with NULL content_hash get backfilled on next init."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    conn = db._get_conn()
    cur = conn.cursor()
    # Insert a chat_message with NULL content_hash (simulating pre-fix data)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', 'Alice', '2024-01-01 12:00:00',
                'Hello world', NULL)
    """)
    conn.commit()
    # Re-construct DB (triggers _run_migrations again)
    db2 = Database(str(db_path))
    conn = db2._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = 'Hello world'")
    h = cur.fetchone()[0]
    assert h is not None
    expected = hashlib.sha256(b'Hello world').hexdigest()
    assert h == expected


def test_new_chat_inserts_have_hash(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', 'Alice', '2024-01-01 12:00:00',
                'New message', ?)
    """, (hashlib.sha256(b'New message').hexdigest(),))
    conn.commit()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = 'New message'")
    assert cur.fetchone()[0] is not None
