from pathlib import Path

PAGES_DIR = Path(__file__).parent.parent.parent / "pages"
HOME = Path(__file__).parent.parent.parent / "Home.py"


def test_home_uses_page_help():
    text = HOME.read_text()
    assert "page_help" in text
    assert 'page_help.render("home")' in text or 'page_help.render(\'home\')' in text


def test_every_page_uses_page_help():
    expected = {
        "1_Case_Theory.py": "case_theory",
        "2_Search.py": "search",
        "3_Timeline.py": "timeline",
        "4_Cases.py": "cases",
        "4A_Witnesses.py": "witnesses",
        "5_Documents.py": "documents",
        "6_Ask.py": "ask",
        "7_Import_Chats.py": "import_chats",
        "8_Discover_Senders.py": "discover_senders",
        "9_Fetch_Emails.py": "fetch_emails",
        "10_Accounts.py": "accounts",
        "11_Export.py": "export",
        "12_Contradictions.py": "contradictions",
        "13_Setup.py": "setup",
    }
    for filename, page_key in expected.items():
        page = PAGES_DIR / filename
        text = page.read_text()
        assert "page_help" in text, f"{filename} missing page_help import"
        assert (
            f'page_help.render("{page_key}")' in text
            or f"page_help.render('{page_key}')" in text
        ), f"{filename} missing page_help.render('{page_key}')"
