"""Smoke tests for modified pages: Timeline, Ask, Documents, Export."""
import pytest


def test_timeline_loads(page_test, tmp_db_with_case):
    """Timeline page renders without errors."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/timeline.py")
    at.session_state.db = db
    at.run()
    assert not at.exception


def test_ask_loads(page_test, tmp_db_with_case):
    """Ask page renders without errors (no index built)."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/ask.py")
    at.session_state.db = db
    at.run()
    assert not at.exception


def test_export_loads(page_test, tmp_db_with_case):
    """Export page renders without errors."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/export.py")
    at.session_state.db = db
    at.run()
    assert not at.exception


def test_documents_loads(page_test, tmp_db_with_case):
    """Documents page renders without errors."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/documents.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
