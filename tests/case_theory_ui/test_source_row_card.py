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


def test_format_one_line_email_with_sender_recipients():
    line = format_one_line_meta(
        kind="email", date="2024-03-14 10:00",
        sender="alice@x.com",
        recipients=["bob@y.com", "charlie@z.com"],
        subject="Custody hearing",
    )
    assert "alice@x.com" in line
    assert "bob@y.com" in line
    assert "charlie@z.com" in line or "+1" in line  # may truncate to +1


def test_format_one_line_email_truncates_recipients():
    line = format_one_line_meta(
        kind="email", date="2024-01-01",
        sender="alice@x", recipients=["a@x", "b@x", "c@x", "d@x", "e@x"],
        subject="topic",
    )
    assert "+3 more" in line or "+4 more" in line  # accept either threshold


def test_format_one_line_chat_with_chat_name():
    line = format_one_line_meta(
        kind="chat", date="2024-03-14 14:02",
        sender="Sarah", chat_name="Mom & Manisha",
        subject="message preview here",
    )
    assert "Mom & Manisha" in line
    assert "Sarah" in line


def test_format_one_line_attachment_with_parent_email():
    line = format_one_line_meta(
        kind="attachment", date="2024-03-14",
        sender="alice@x.com", filename="affidavit.pdf",
    )
    assert "affidavit.pdf" in line
    assert "alice@x.com" in line or "alice" in line
