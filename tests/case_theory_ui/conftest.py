# tests/case_theory_ui/conftest.py
"""Streamlit AppTest fixtures for UI smoke tests."""
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def page_test():
    """Build an AppTest for a given page. Caller passes the page path
    relative to project root, e.g. 'pages/11_Case_Theory.py'."""
    def _build(page_path: str, *, default_timeout: float = 5.0):
        return AppTest.from_file(page_path, default_timeout=default_timeout)
    return _build
