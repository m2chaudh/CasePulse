# tests/case_theory_ui/test_page_help.py
import pytest
from casepulse.case_theory.ui.page_help import (
    PAGE_HELP, get_help, render_help_markdown,
)


def test_registry_contains_required_keys_for_each_page():
    expected_pages = {
        "home", "case_theory", "search", "timeline", "cases",
        "witnesses", "documents", "ask", "import_chats",
        "discover_senders", "fetch_emails", "accounts",
        "export", "contradictions", "setup",
    }
    assert set(PAGE_HELP.keys()) == expected_pages


def test_each_entry_has_required_fields():
    for key, entry in PAGE_HELP.items():
        assert "title" in entry, f"{key} missing title"
        assert "description" in entry, f"{key} missing description"
        assert "what_to_do" in entry, f"{key} missing what_to_do"
        assert isinstance(entry["title"], str) and entry["title"]
        assert isinstance(entry["description"], str) and entry["description"]
        assert isinstance(entry["what_to_do"], str) and entry["what_to_do"]


def test_get_help_returns_entry():
    h = get_help("case_theory")
    assert h["title"] == "Case Theory Workbench"


def test_get_help_returns_none_for_missing():
    assert get_help("nonexistent_page") is None


def test_render_help_markdown_includes_description_and_what_to_do():
    out = render_help_markdown("case_theory")
    assert "Case Theory Workbench" in out
    assert "Build" in out  # from description
    assert "**What to do here**" in out


def test_render_help_markdown_missing_returns_empty():
    assert render_help_markdown("nonexistent_page") == ""
