"""Tests for schema migrations in database.py."""
import pytest
import sqlite3


def test_migrations_run_idempotently(tmp_db):
    """Running migrations twice does not error or duplicate state."""
    tmp_db._init_schema()  # second run after fixture's first run
    # Check core tables still exist
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert 'emails' in tables
    assert 'cases' in tables


def test_themes_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(themes)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'title', 'description', 'display_order', 'created_at'}


def test_themes_unique_per_case(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO themes(case_id, title) VALUES (?, ?)", (case_id, "T1"))
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO themes(case_id, title) VALUES (?, ?)", (case_id, "T1"))


def test_allegations_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(allegations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'title', 'claim_text', 'claimed_date',
                    'source_evidence_id', 'status', 'notes', 'created_at'}


def test_contradictions_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(contradictions)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'headline', 'status', 'theme_id',
                    'display_order', 'notes', 'created_at', 'updated_at'}


def test_contradiction_allegations_bridge(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(contradiction_allegations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'contradiction_id', 'allegation_id'}


def test_arguments_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(arguments)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'contradiction_id', 'title', 'reasoning_text',
                    'argument_type', 'strength', 'sequence',
                    'created_at', 'updated_at'}


def test_argument_evidence_bridge(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(argument_evidence)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'argument_id', 'evidence_id', 'role',
                    'display_order', 'notes', 'added_at'}


def test_evidence_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(evidence)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'evidence_kind', 'source_table', 'source_row_id',
                    'char_start', 'char_end', 'snippet', 'source_hash',
                    'created_at'}


def test_photo_metadata_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(photo_metadata)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'source_table', 'source_row_id', 'taken_at',
                    'camera_make', 'camera_model', 'lens', 'software',
                    'gps_lat', 'gps_lon', 'gps_accuracy', 'orientation',
                    'width', 'height', 'exif_present', 'detected_at'}


def test_metadata_attestations_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(metadata_attestations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'photo_metadata_id', 'field_name', 'status',
                    'reason', 'attestation_text', 'attested_by',
                    'attested_at', 'created_at'}


def test_cases_has_case_type_column(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(cases)")
    cols = {row[1] for row in cur.fetchall()}
    assert 'case_type' in cols


def test_cases_default_case_type_is_family(tmp_db):
    case_id = tmp_db.create_case(name="Test", case_number="T1")
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT case_type FROM cases WHERE id = ?", (case_id,))
    assert cur.fetchone()[0] == 'family'
