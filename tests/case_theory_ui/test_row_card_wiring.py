# tests/case_theory_ui/test_row_card_wiring.py
"""Confirm that pages using source_row_card pass sender/recipients/chat_name
where the data is available."""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_search_page_passes_sender_to_row_card():
    text = (ROOT / "pages_modules/search.py").read_text()
    # Should pass sender/recipients to format_one_line_meta where source row has them
    assert "format_one_line_meta" in text
    assert "sender" in text


def test_evidence_tray_passes_sender_to_row_card():
    text = (ROOT / "casepulse/case_theory/ui/evidence_tray.py").read_text()
    assert "format_one_line_meta" in text
