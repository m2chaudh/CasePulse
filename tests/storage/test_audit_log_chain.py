"""Tests for the audit_log tamper-evident hash chain.

The chain is what allows CasePulse to claim the audit log hasn't been
edited after the fact. Each row stores `prev_hash` (the previous row's
`row_hash`) and `row_hash = sha256(prev_hash | action | details |
created_at)`. Editing any row breaks the chain at that row.
"""
import hashlib

import pytest


def _expected_hash(prev: str, action: str, details: str, created_at: str) -> str:
    payload = f"{prev}|{action}|{details}|{created_at}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_first_log_action_has_empty_prev_and_set_row_hash(tmp_db):
    tmp_db.log_action("import", "first")
    with tmp_db._get_conn() as conn:
        row = conn.execute(
            "SELECT prev_hash, row_hash, action, details, created_at "
            "FROM audit_log ORDER BY id ASC LIMIT 1"
        ).fetchone()
    assert row["prev_hash"] == ""
    assert row["row_hash"] == _expected_hash(
        "", row["action"], row["details"], row["created_at"],
    )


def test_subsequent_rows_chain_back(tmp_db):
    tmp_db.log_action("import", "one")
    tmp_db.log_action("export", "two")
    tmp_db.log_action("tag", "three")
    with tmp_db._get_conn() as conn:
        rows = conn.execute(
            "SELECT prev_hash, row_hash FROM audit_log ORDER BY id ASC"
        ).fetchall()
    assert rows[0]["prev_hash"] == ""
    assert rows[1]["prev_hash"] == rows[0]["row_hash"]
    assert rows[2]["prev_hash"] == rows[1]["row_hash"]


def test_verify_chain_on_clean_log_passes(tmp_db):
    for i in range(5):
        tmp_db.log_action(f"action_{i}", f"details_{i}")
    result = tmp_db.verify_audit_chain()
    assert result["valid"] is True
    assert result["rows_checked"] == 5
    assert result["first_bad_id"] is None


def test_verify_chain_detects_edited_details(tmp_db):
    tmp_db.log_action("import", "original")
    tmp_db.log_action("export", "next")
    # Tamper: edit the details of row 1
    with tmp_db._get_conn() as conn:
        conn.execute(
            "UPDATE audit_log SET details = 'tampered' WHERE id = 1"
        )
    result = tmp_db.verify_audit_chain()
    assert result["valid"] is False
    assert result["first_bad_id"] == 1


def test_verify_chain_detects_deleted_row(tmp_db):
    tmp_db.log_action("a", "1")
    tmp_db.log_action("b", "2")
    tmp_db.log_action("c", "3")
    # Tamper: delete the middle row — row 3's prev_hash no longer
    # matches row 1's row_hash.
    with tmp_db._get_conn() as conn:
        conn.execute("DELETE FROM audit_log WHERE id = 2")
    result = tmp_db.verify_audit_chain()
    assert result["valid"] is False
    assert result["first_bad_id"] == 3


def test_verify_chain_on_empty_log_passes(tmp_db):
    result = tmp_db.verify_audit_chain()
    assert result["valid"] is True
    assert result["rows_checked"] == 0


def test_backfill_legacy_rows_with_null_hash(tmp_db):
    """Rows inserted before the hash-chain was wired (legacy data) get
    backfilled on next Database() construction so verify_audit_chain
    starts succeeding from then on."""
    # Simulate legacy rows: INSERT directly with NULL hash columns
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (action, details, created_at, "
            "prev_hash, row_hash) VALUES "
            "('legacy_a', 'one', '2024-01-01 10:00:00', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO audit_log (action, details, created_at, "
            "prev_hash, row_hash) VALUES "
            "('legacy_b', 'two', '2024-01-01 10:00:01', NULL, NULL)"
        )
    # Re-construct DB → triggers _run_migrations backfill
    from casepulse.storage.database import Database
    db2 = Database(tmp_db.db_path)
    result = db2.verify_audit_chain()
    assert result["valid"] is True
    assert result["rows_checked"] == 2


def test_log_action_after_backfill_continues_chain(tmp_db):
    """After legacy backfill, new log_action calls correctly chain on
    top of the backfilled row_hash."""
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_log (action, details, created_at, "
            "prev_hash, row_hash) VALUES "
            "('legacy', 'pre', '2024-01-01 10:00:00', NULL, NULL)"
        )
    from casepulse.storage.database import Database
    db2 = Database(tmp_db.db_path)
    db2.log_action("new", "post-backfill")
    assert db2.verify_audit_chain()["valid"] is True
