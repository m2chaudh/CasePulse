# casepulse/case_theory/ui/source_row_card.py
"""Renders a 1-line preview of an evidence source row across kinds.

The same renderer is used by:
- Evidence Tray result rows
- Search result rows
- Attached-evidence list under an Argument
- Timeline rows when keyword filter highlights matches
"""
from typing import Optional


_ICONS = {
    "email": "📧",
    "chat": "💬",
    "attachment": "📎",
    "document": "📄",
    "photo": "📷",
    "annotation": "📝",
}


def icon_for(kind: str) -> str:
    return _ICONS.get(kind, "•")


def _truncate(s: str, limit: int = 80) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def format_one_line_meta(
    *, kind: str,
    date: Optional[str] = None,
    sender: Optional[str] = None,
    subject: Optional[str] = None,
    filename: Optional[str] = None,
    chat_name: Optional[str] = None,
) -> str:
    """Return a single line of compact metadata for a source-row card."""
    icon = icon_for(kind)
    parts = []
    if date:
        parts.append(date[:16])  # ISO YYYY-MM-DD HH:MM
    if sender:
        parts.append(sender)
    if chat_name:
        parts.append(chat_name)
    title = subject or filename or ""
    title = _truncate(title, 80)
    line = f"{icon} {' · '.join(parts)}"
    if title:
        line += f" — {title}"
    return line
