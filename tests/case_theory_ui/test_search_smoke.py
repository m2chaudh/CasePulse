"""Smoke tests for the Search page (pages/12_Search.py)."""
import pytest


def test_search_page_renders(page_test, tmp_db_with_case):
    """Page renders without errors when no query entered."""
    db, case_id = tmp_db_with_case
    at = page_test("pages/12_Search.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "search" in text.lower()


def test_search_page_shows_caption_on_empty_query(page_test, tmp_db_with_case):
    """When no query is entered the page shows the 'enter a search' caption."""
    db, case_id = tmp_db_with_case
    at = page_test("pages/12_Search.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    caption_texts = [c.value or "" for c in at.caption]
    assert any("search" in t.lower() for t in caption_texts)
