import sqlite3
from casepulse.storage.database import Database


def _table_exists(db, name):
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        return row is not None


def _column_exists(db, table, col):
    with db._get_conn() as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return col in {r[1] for r in rows}


def test_timeline_events_has_metadata_json(tmp_db):
    assert _column_exists(tmp_db, "timeline_events", "metadata_json")


def test_binder_filter_chips_table(tmp_db):
    assert _table_exists(tmp_db, "binder_filter_chips")


def test_case_relevant_senders_table(tmp_db):
    assert _table_exists(tmp_db, "case_relevant_senders")


def test_item_links_table(tmp_db):
    assert _table_exists(tmp_db, "item_links")


def test_binder_suggestions_table(tmp_db):
    assert _table_exists(tmp_db, "binder_suggestions")


def test_indexes_present(tmp_db):
    with tmp_db._get_conn() as conn:
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()}
    assert "idx_emails_date_received" in names
    assert "idx_chat_messages_timestamp" in names
    assert "idx_documents_created_at" in names
    assert "idx_timeline_date_case" in names
    assert "idx_evidence_tags_case_type" in names
    assert "idx_binder_filter_chips_case" in names
    assert "idx_case_senders_case" in names
    assert "idx_case_senders_addr" in names
    assert "idx_item_links_from" in names
    assert "idx_item_links_to" in names
    assert "idx_binder_suggestions_pending" in names


def test_migration_is_idempotent(tmp_db):
    tmp_db._run_migrations()
    tmp_db._run_migrations()
    assert _column_exists(tmp_db, "timeline_events", "metadata_json")
