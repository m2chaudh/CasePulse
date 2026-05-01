# tests/case_theory_ui/test_source_row_card.py
from casepulse.case_theory.ui.source_row_card import (
    icon_for, format_one_line_meta,
)


def test_icon_for_each_kind():
    assert icon_for("email") == "📧"
    assert icon_for("chat") == "💬"
    assert icon_for("attachment") == "📎"
    assert icon_for("document") == "📄"
    assert icon_for("photo") == "📷"
    assert icon_for("annotation") == "📝"
    assert icon_for("unknown") == "•"


def test_format_one_line_email():
    line = format_one_line_meta(
        kind="email",
        date="2024-03-14 10:00",
        sender="alice@x.com",
        subject="Custody hearing",
    )
    assert "2024-03-14" in line
    assert "alice@x.com" in line
    assert "Custody hearing" in line


def test_format_one_line_truncates_long_subject():
    line = format_one_line_meta(
        kind="email", date="2024-01-01",
        sender="x@x", subject="A" * 200,
    )
    assert len(line) < 200  # truncated with ellipsis
    assert "…" in line or "..." in line
