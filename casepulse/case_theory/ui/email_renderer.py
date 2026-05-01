# casepulse/case_theory/ui/email_renderer.py
"""Email body rendering — pre-wrap, blockquote styling for quoted lines,
and a separated 'earlier replies' section for forwarded chains.

Output is a dict with two HTML strings: 'current' (the current message)
and 'earlier' (the forwarded chain, or None if there's no boundary).
The caller renders 'current' inline and 'earlier' inside an expander.
"""
import re
from html import escape
from typing import Optional


# Outlook / Gmail / Apple Mail style boundary
_THREAD_BOUNDARY_RE = re.compile(
    r"^On\s+.{4,200}\s+wrote:\s*$",
    re.MULTILINE,
)


def detect_thread_boundary(body: str) -> Optional[int]:
    """Return the character index of the first 'On ... wrote:' boundary, or None."""
    if not body:
        return None
    m = _THREAD_BOUNDARY_RE.search(body)
    return m.start() if m else None


def split_quoted_lines(body: str) -> str:
    """HTML-escape body and wrap consecutive quoted lines (lines starting with '> ')
    in a single <blockquote> block. Returns HTML."""
    if not body:
        return ""
    lines = body.split("\n")
    out_parts: list[str] = []
    in_quote = False
    quote_buf: list[str] = []
    for line in lines:
        is_quoted = line.startswith("> ") or line.startswith(">")
        if is_quoted:
            if not in_quote:
                in_quote = True
                quote_buf = []
            # Strip the leading '> ' or '>'
            stripped = line[2:] if line.startswith("> ") else line[1:]
            quote_buf.append(escape(stripped))
        else:
            if in_quote:
                out_parts.append(
                    "<blockquote>" + "\n".join(quote_buf) + "</blockquote>"
                )
                in_quote = False
                quote_buf = []
            out_parts.append(escape(line))
    if in_quote:
        out_parts.append(
            "<blockquote>" + "\n".join(quote_buf) + "</blockquote>"
        )
    return "\n".join(out_parts)


def render_html(body: str) -> dict:
    """Render an email body as HTML.

    Returns:
        {
            "current": "<pre>...</pre>",
            "earlier": "<pre>...</pre>" or None,
        }

    'current' is the visible part — the most recent message in the thread.
    'earlier' is everything after the first 'On ... wrote:' boundary, intended
    to be wrapped in a 'Show earlier replies' expander by the caller.
    """
    if not body:
        return {"current": "<pre>[empty body]</pre>", "earlier": None}

    boundary = detect_thread_boundary(body)
    if boundary is None:
        return {
            "current": f"<pre>{split_quoted_lines(body)}</pre>",
            "earlier": None,
        }

    current = body[:boundary].rstrip()
    earlier = body[boundary:].rstrip()
    return {
        "current": f"<pre>{split_quoted_lines(current)}</pre>",
        "earlier": f"<pre>{split_quoted_lines(earlier)}</pre>",
    }
