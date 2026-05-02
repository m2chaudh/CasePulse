from pathlib import Path

PAGES_DIR = Path(__file__).parent.parent.parent / "pages_modules"
HOME = Path(__file__).parent.parent.parent / "Home.py"


def test_home_uses_page_help():
    # page_help.render("home") lives in dashboard.py (extracted from old Home.py)
    text = (PAGES_DIR / "dashboard.py").read_text()
    assert "page_help" in text
    assert 'page_help.render("home")' in text or 'page_help.render(\'home\')' in text


def test_every_page_uses_page_help():
    expected = {
        "case_theory.py": "case_theory",
        "search.py": "search",
        "timeline.py": "timeline",
        "cases.py": "cases",
        "witnesses.py": "witnesses",
        "documents.py": "documents",
        "ask.py": "ask",
        "import_chats.py": "import_chats",
        "discover_senders.py": "discover_senders",
        "fetch_emails.py": "fetch_emails",
        "accounts.py": "accounts",
        "export.py": "export",
        "contradictions.py": "contradictions",
        "setup.py": "setup",
    }
    for filename, page_key in expected.items():
        page = PAGES_DIR / filename
        text = page.read_text()
        assert "page_help" in text, f"{filename} missing page_help import"
        assert (
            f'page_help.render("{page_key}")' in text
            or f"page_help.render('{page_key}')" in text
        ), f"{filename} missing page_help.render('{page_key}')"
