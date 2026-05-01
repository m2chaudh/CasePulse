# tests/case_theory/test_audit_chain.py
import hashlib
from casepulse.case_theory.audit_chain import (
    log_chained, verify_chain, get_last_hash,
)


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
