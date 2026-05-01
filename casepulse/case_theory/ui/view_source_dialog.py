# casepulse/case_theory/ui/view_source_dialog.py
"""Renders the full source content for an Evidence row.

Emails: rendered via email_renderer (pre-wrap, blockquotes, thread collapse).
Other types: rendered as plain text inside <pre> with snippet highlighting.

Optional char_start/char_end: highlight the cited span via <mark id="cited-highlight">
and inject a JS scroll-into-view script so the dialog opens already scrolled to it.
"""
from html import escape
from typing import Optional
import streamlit as st

from casepulse.case_theory.evidence_resolver import resolve
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.ui.email_renderer import render_html as render_email_html
from casepulse.case_theory.ui.snippet_link import (
    wrap_with_mark, build_scroll_script,
)


def _resolve_for_display(db, *, source_table: str, source_row_id: int):
    e = Evidence(
        evidence_kind=EvidenceKind.EMAIL,  # placeholder; resolver dispatches on source_table
        source_table=source_table,
        source_row_id=source_row_id,
    )
    return resolve(db, e)


def render_source_panel(db, *, source_table: str, source_row_id: int,
                         inline: bool = False,
                         char_start: Optional[int] = None,
                         char_end: Optional[int] = None) -> str:
    """Render the source panel.

    Returns the rendered string (for tests via inline=True; in normal use,
    invoked from inside @st.dialog).
    """
    rs = _resolve_for_display(
        db, source_table=source_table, source_row_id=source_row_id,
    )
    parts = [f"<h3>{rs.kind.title()}</h3>"]
    for k, v in rs.metadata.items():
        if v is None or v == "":
            continue
        parts.append(f"<p><strong>{k}:</strong> {v}</p>")

    text = rs.text or ""

    if rs.kind == "email":
        rendered = render_email_html(text)
        # Apply highlight to the 'current' section if char range falls within it
        current_html = rendered["current"]
        if char_start is not None and char_end is not None:
            # Highlight in the raw text, then re-render
            highlighted_text = wrap_with_mark(text, char_start=char_start, char_end=char_end)
            # Use highlighted_text in place of the email_renderer output if the
            # mark wrap actually produced a <mark>
            if "<mark" in highlighted_text:
                # Email body is mostly the 'current' part; re-render with mark
                marked_html = highlighted_text + build_scroll_script()
                parts.append(f'<div class="reading-content"><pre>{marked_html}</pre></div>')
            else:
                parts.append(f'<div class="reading-content">{current_html}</div>')
                if rendered["earlier"]:
                    parts.append(
                        f'<details><summary>Show earlier replies</summary>'
                        f'<div class="reading-content">{rendered["earlier"]}</div>'
                        f'</details>'
                    )
        else:
            parts.append(f'<div class="reading-content">{current_html}</div>')
            if rendered["earlier"]:
                parts.append(
                    f'<details><summary>Show earlier replies</summary>'
                    f'<div class="reading-content">{rendered["earlier"]}</div>'
                    f'</details>'
                )
    else:
        # Non-email: plain text with optional mark
        if char_start is not None and char_end is not None and "<mark" in wrap_with_mark(
            text, char_start=char_start, char_end=char_end,
        ):
            highlighted = wrap_with_mark(text, char_start=char_start, char_end=char_end)
            parts.append(
                f'<div class="reading-content"><pre>{highlighted}'
                f'{build_scroll_script()}</pre></div>'
            )
        else:
            parts.append(
                f'<div class="reading-content"><pre>{escape(text)}</pre></div>'
            )

    rendered_html = "\n".join(parts)
    if inline:
        return rendered_html
    st.markdown(rendered_html, unsafe_allow_html=True)
    return rendered_html


@st.dialog("Source")
def show(db, *, source_table: str, source_row_id: int,
          char_start: Optional[int] = None,
          char_end: Optional[int] = None):
    render_source_panel(
        db, source_table=source_table, source_row_id=source_row_id,
        char_start=char_start, char_end=char_end,
    )
