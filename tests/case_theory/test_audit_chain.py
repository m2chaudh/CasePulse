# tests/case_theory/test_audit_chain.py
import hashlib
import threading
from casepulse.case_theory.audit_chain import (
    log_chained, verify_chain, get_last_hash,
)
from casepulse.storage.database import Database


def test_chained_inserts_link(tmp_db):
    log_chained(tmp_db, action="created_theme", details={"theme_id": 1})
    log_chained(tmp_db, action="created_argument", details={"argument_id": 5})
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, prev_hash, row_hash FROM audit_log ORDER BY id")
    rows = cur.fetchall()
    assert rows[0][1] is None  # genesis row has no prev_hash
    assert rows[0][2] is not None  # but has its own row_hash
    assert rows[1][1] == rows[0][2]  # second row's prev = first's row


def test_verify_chain_passes_unmodified(tmp_db):
    log_chained(tmp_db, action="a", details={})
    log_chained(tmp_db, action="b", details={})
    log_chained(tmp_db, action="c", details={})
    assert verify_chain(tmp_db) is True


def test_verify_chain_detects_tampering(tmp_db):
    log_chained(tmp_db, action="a", details={})
    log_chained(tmp_db, action="b", details={})
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE audit_log SET action = 'TAMPERED' WHERE id = 1")
    conn.commit()
    assert verify_chain(tmp_db) is False


def test_verify_chain_skips_pre_w1_legacy_rows(tmp_db):
    """Pre-W1 rows have NULL row_hash and possibly non-JSON details. They
    should be ignored by verify_chain rather than crashing JSON parse.
    """
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    # Simulate a pre-W1 row: NULL row_hash, plain-text details
    cur.execute(
        "INSERT INTO audit_log (action, details) VALUES (?, ?)",
        ("pre_w1_action", "Set PIN"),
    )
    conn.commit()
    # Now log a real chained row
    log_chained(tmp_db, action="post_w1", details={"id": 1})
    # Chain verification should pass — legacy row is skipped
    assert verify_chain(tmp_db) is True


def test_log_chained_concurrent(tmp_path):
    """8 threads × 5 log_chained calls must yield a valid chain of exactly 40 rows.

    Each thread opens its own Database instance (SQLite requires per-thread
    connections). BEGIN IMMEDIATE in log_chained serialises writers so the
    chain is never forked.
    """
    db_path = str(tmp_path / "concurrent.db")
    # Initialise schema by constructing one Database instance
    Database(db_path)

    errors = []

    def worker():
        thread_db = Database(db_path)
        try:
            for i in range(5):
                log_chained(thread_db, action="concurrent_write",
                             details={"thread": threading.get_ident(), "i": i})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors: {errors}"

    verify_db = Database(db_path)
    conn = verify_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM audit_log WHERE row_hash IS NOT NULL")
    count = cur.fetchone()[0]
    assert count == 40, f"Expected 40 chained rows, got {count}"
    assert verify_chain(verify_db) is True


def test_chain_survives_legacy_interleaving(tmp_db):
    """Chain remains valid when legacy db.log_action rows are interleaved.

    Sequence: chained row → raw INSERT (no row_hash) → chained row.
    The second chained row must link to the first chained row, not the
    legacy row whose row_hash is NULL.
    """
    # First chained row
    log_chained(tmp_db, action="first", details={"x": 1})

    # Legacy raw insert (simulates db.log_action — no row_hash column)
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (action, details) VALUES ('legacy', 'plain text')"
    )
    conn.commit()

    # Second chained row — must pick up hash from first chained row, not NULL
    log_chained(tmp_db, action="second", details={"x": 2})

    assert verify_chain(tmp_db) is True
