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
