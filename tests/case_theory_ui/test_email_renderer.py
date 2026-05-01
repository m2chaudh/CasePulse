# tests/case_theory_ui/test_email_renderer.py
from casepulse.case_theory.ui.email_renderer import (
    detect_thread_boundary, split_quoted_lines, render_html,
)


def test_detect_thread_boundary_outlook_format():
    body = (
        "Hi there,\n"
        "Quick question.\n"
        "\n"
        "On Mon, Mar 14, 2024 at 10:00 AM, Jane Doe <jane@x.com> wrote:\n"
        "> earlier message\n"
    )
    boundary_idx = detect_thread_boundary(body)
    assert boundary_idx is not None
    assert "On Mon" in body[boundary_idx:]


def test_detect_thread_boundary_no_match():
    body = "Just a single message with no replies attached.\n"
    assert detect_thread_boundary(body) is None


def test_split_quoted_lines_groups_blockquotes():
    body = (
        "Reply text here.\n"
        "> first quoted\n"
        "> second quoted\n"
        "Back to reply.\n"
    )
    out = split_quoted_lines(body)
    assert "<blockquote>" in out
    assert "first quoted" in out
    assert "second quoted" in out
    assert "Back to reply." in out


def test_render_html_simple_no_quote():
    body = "Plain email\n\nWith two paragraphs."
    result = render_html(body)
    assert isinstance(result, dict)
    assert "<pre" in result["current"]
    assert "Plain email" in result["current"]
    assert "With two paragraphs." in result["current"]
    assert result["earlier"] is None


def test_render_html_with_thread_separates_current_and_earlier():
    body = (
        "Current message body.\n\n"
        "On Mon, Mar 14 2024, Jane wrote:\n"
        "> ancient quoted line\n"
    )
    result = render_html(body)
    # Should return a dict with 'current' (HTML) and 'earlier' (HTML or None)
    assert isinstance(result, dict)
    assert "current" in result
    assert "earlier" in result
    assert "Current message body." in result["current"]
    assert "ancient quoted line" in (result["earlier"] or "")


def test_render_html_empty_body():
    result = render_html("")
    assert result["current"] == "<pre>[empty body]</pre>"
    assert result["earlier"] is None
