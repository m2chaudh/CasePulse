"""Verify the SQL allowlists reject unknown identifiers.

These are dynamic-SQL paths where the identifier (table or column
name) is interpolated via f-string because SQLite can't parameterise
those. The allowlist is the only defence — a future caller passing a
free-form string MUST be rejected.
"""
import pytest

from casepulse.case_theory.repository import _compute_source_hash


def test_compute_source_hash_returns_none_for_unknown_table(tmp_db):
    """An unrecognised source_table is treated as missing — no SQL is
    issued. Previously this f-string'd whatever the caller passed."""
    out = _compute_source_hash(tmp_db, "non_existent_table", 1)
    assert out is None


def test_compute_source_hash_returns_none_for_injection_attempt(tmp_db):
    """A nasty string can't be smuggled through to the f-string."""
    out = _compute_source_hash(
        tmp_db, "emails; DROP TABLE emails; --", 1,
    )
    assert out is None


def test_compute_source_hash_works_for_allowed_table(tmp_db):
    """Sanity: legitimate table names still resolve correctly."""
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO emails (message_id, subject, body_text) VALUES "
            "('m1@x', 'test', 'hello world')"
        )
        email_id = conn.execute(
            "SELECT id FROM emails ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
    h = _compute_source_hash(tmp_db, "emails", email_id)
    assert h and len(h) == 64  # sha256 hex


def test_fts_backfill_rejects_unknown_fts_table(tmp_db):
    """_backfill_fts_if_empty refuses an fts_table not in its
    allowlist. Tested through a direct call since the helper is
    internal to _run_migrations."""
    with tmp_db._get_conn() as conn:
        cur = conn.cursor()
        with pytest.raises(ValueError, match="unknown fts_table"):
            tmp_db._backfill_fts_if_empty(
                cur, "not_a_table_fts", "emails", ["body_text"],
            )


def test_fts_backfill_rejects_wrong_source_table(tmp_db):
    """An fts_table can't be paired with a source_table other than the
    one it was built for."""
    with tmp_db._get_conn() as conn:
        cur = conn.cursor()
        with pytest.raises(ValueError, match="does not match allowlist"):
            tmp_db._backfill_fts_if_empty(
                cur, "emails_fts", "chat_messages", ["body_text"],
            )


def test_fts_backfill_rejects_unknown_column(tmp_db):
    """Even the right (fts_table, source_table) pair rejects column
    names that aren't on the allowed list — so an attacker who can
    influence column names still can't execute arbitrary SQL fragments."""
    with tmp_db._get_conn() as conn:
        cur = conn.cursor()
        with pytest.raises(ValueError, match="not in allowlist"):
            tmp_db._backfill_fts_if_empty(
                cur, "emails_fts", "emails",
                ["body_text; DROP TABLE emails;"],
            )
