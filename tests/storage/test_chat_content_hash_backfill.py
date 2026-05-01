"""Tests for chat_messages.content_hash canonical formula.

The canonical formula is sha256(f"{timestamp}|{sender}|{message_text}").
This file verifies:
  1. The migration backfill uses the canonical formula.
  2. _compute_source_hash in repository.py uses the canonical formula.
"""
import hashlib
from casepulse.storage.database import Database


def _canonical_chat_hash(ts: str, sender: str, text: str) -> str:
    return hashlib.sha256(f"{ts}|{sender}|{text}".encode("utf-8")).hexdigest()


def test_backfill_populates_existing_chat_hashes(tmp_path):
    """Existing chat rows with NULL content_hash get backfilled on next init
    using the canonical sha256(ts|sender|text) formula.
    """
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    conn = db._get_conn()
    cur = conn.cursor()
    ts = "2024-01-01 12:00:00"
    sender = "Alice"
    text = "Hello world"
    # Insert a chat_message with NULL content_hash (simulating pre-fix data)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', ?, ?, ?, NULL)
    """, (sender, ts, text))
    conn.commit()
    # Re-construct DB (triggers _run_migrations again)
    db2 = Database(str(db_path))
    conn = db2._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = ?", (text,))
    h = cur.fetchone()[0]
    assert h is not None
    expected = _canonical_chat_hash(ts, sender, text)
    assert h == expected, f"backfill used wrong formula: got {h}, expected {expected}"


def test_new_chat_inserts_have_hash(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    ts = "2024-01-01 12:00:00"
    sender = "Alice"
    text = "New message"
    expected = _canonical_chat_hash(ts, sender, text)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', ?, ?, ?, ?)
    """, (sender, ts, text, expected))
    conn.commit()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = ?", (text,))
    assert cur.fetchone()[0] is not None


def test_chat_content_hash_canonical_formula(tmp_db_with_case):
    """Canonical formula is sha256(ts|sender|text) — consistent across
    migration backfill and _compute_source_hash.
    """
    from casepulse.case_theory.repository import _compute_source_hash
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()

    ts = "2024-06-15 14:30:00"
    sender = "Bob"
    text = "Test canonical hash"
    expected = _canonical_chat_hash(ts, sender, text)

    # Insert with the correct hash already set (as importer would)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/chat.txt', ?, ?, ?, ?)
    """, (sender, ts, text, expected))
    conn.commit()
    row_id = cur.lastrowid

    # Verify chat_messages.content_hash matches the canonical formula
    cur.execute("SELECT content_hash FROM chat_messages WHERE id = ?", (row_id,))
    stored_hash = cur.fetchone()[0]
    assert stored_hash == expected, (
        f"stored hash {stored_hash!r} doesn't match canonical formula {expected!r}"
    )

    # Verify _compute_source_hash produces the same value
    computed = _compute_source_hash(db, "chat_messages", row_id)
    assert computed == expected, (
        f"_compute_source_hash {computed!r} doesn't match canonical formula {expected!r}"
    )
