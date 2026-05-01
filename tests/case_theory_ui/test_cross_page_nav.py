"""Cross-page navigation smoke tests — every modified/new page must load."""
import pytest


@pytest.mark.parametrize("page", [
    "pages/3_Timeline.py",
    "pages/6_Ask.py",
    "pages/11_Export.py",
    "pages/5_Documents.py",
    "pages/1_Case_Theory.py",
    "pages/2_Search.py",
])
def test_page_loads_without_error(page, page_test, tmp_db_with_case):
    db, case_id = tmp_db_with_case
    at = page_test(page)
    at.session_state.db = db
    at.run()
    assert not at.exception, f"{page} raised: {at.exception}"
