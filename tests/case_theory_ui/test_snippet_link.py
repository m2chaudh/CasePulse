# tests/case_theory_ui/test_snippet_link.py
from casepulse.case_theory.ui.snippet_link import (
    wrap_with_mark, build_scroll_script, render_marked_body,
)


def test_wrap_with_mark_inserts_mark_at_offsets():
    body = "Hello world this is a long body."
    out = wrap_with_mark(body, char_start=6, char_end=11)
    assert '<mark id="cited-highlight">world</mark>' in out
    assert "Hello " in out
    assert " this is a long body." in out


def test_wrap_with_mark_offset_overflow_returns_full_body_no_mark():
    body = "short body"
    out = wrap_with_mark(body, char_start=999, char_end=1000)
    # Out of range — return body without mark
    assert "<mark" not in out
    assert "short body" in out


def test_wrap_with_mark_zero_length_range():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=5, char_end=5)
    # Empty mark — render full body without mark
    assert "<mark" not in out
    assert "Hello world" in out


def test_wrap_with_mark_negative_start():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=-3, char_end=5)
    # Negative start — treat as 0
    assert '<mark id="cited-highlight">Hello</mark>' in out


def test_wrap_with_mark_no_offsets_returns_body():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=None, char_end=None)
    assert out == "Hello world"


def test_build_scroll_script_targets_anchor():
    s = build_scroll_script()
    assert "<script>" in s
    assert "cited-highlight" in s
    assert "scrollIntoView" in s


def test_render_marked_body_combines_wrap_and_script():
    body = "Hello world"
    out = render_marked_body(body, char_start=6, char_end=11)
    assert '<mark id="cited-highlight">world</mark>' in out
    assert "scrollIntoView" in out
