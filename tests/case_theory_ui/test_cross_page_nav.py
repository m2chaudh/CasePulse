"""Cross-page navigation smoke tests — every modified/new page must load."""
import pytest


@pytest.mark.parametrize("page", [
    "pages_modules/timeline.py",
    "pages_modules/ask.py",
    "pages_modules/export.py",
    "pages_modules/documents.py",
    "pages_modules/case_theory.py",
    "pages_modules/search.py",
])
def test_page_loads_without_error(page, page_test, tmp_db_with_case):
    db, case_id = tmp_db_with_case
    at = page_test(page)
    at.session_state.db = db
    at.run()
    assert not at.exception, f"{page} raised: {at.exception}"
