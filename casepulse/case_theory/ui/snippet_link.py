# casepulse/case_theory/ui/snippet_link.py
"""Clickable snippet → source view with highlighted span and auto-scroll.

This module provides:
- wrap_with_mark: wraps a substring at (char_start, char_end) in <mark id="cited-highlight">
- build_scroll_script: returns a <script> tag that scrolls the highlight into view
- render_marked_body: combines the above into one HTML block ready for st.markdown(unsafe_allow_html=True)

The Streamlit caller uses these in the View source dialog to render the source body
with the cited span highlighted and auto-scrolled into view on dialog open.
"""
from html import escape
from typing import Optional


def wrap_with_mark(body: str, *, char_start: Optional[int],
                    char_end: Optional[int]) -> str:
    """Return body with the (char_start, char_end) range wrapped in <mark>.

    Edge cases:
    - char_start or char_end is None: return body unchanged
    - char_start < 0: clamp to 0
    - char_end > len(body): return body without <mark> (data drift)
    - char_end <= char_start: return body without <mark> (zero-length)
    """
    if char_start is None or char_end is None:
        return body
    if char_end <= char_start:
        return body
    if char_end > len(body):
        return body
    start = max(0, char_start)
    before = escape(body[:start])
    middle = escape(body[start:char_end])
    after = escape(body[char_end:])
    return f"{before}<mark id=\"cited-highlight\">{middle}</mark>{after}"


def build_scroll_script() -> str:
    """Return a <script> that scrolls the #cited-highlight element into view."""
    return (
        "<script>"
        "(function(){"
        "var el = document.getElementById('cited-highlight');"
        "if (el) { el.scrollIntoView({block: 'center', behavior: 'smooth'}); }"
        "})();"
        "</script>"
    )


def render_marked_body(body: str, *, char_start: Optional[int],
                        char_end: Optional[int]) -> str:
    """Return an HTML block with the cited span highlighted and a scroll script.

    Suitable for st.markdown(..., unsafe_allow_html=True).
    """
    marked = wrap_with_mark(body, char_start=char_start, char_end=char_end)
    return marked + build_scroll_script()
