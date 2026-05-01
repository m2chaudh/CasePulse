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
