"""Renders a 1-line preview of an evidence source row across kinds."""
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


def _format_recipients(recipients: list[str], max_visible: int = 2) -> str:
    """Format a recipient list: 'r1, r2, +N more'."""
    if not recipients:
        return ""
    if len(recipients) <= max_visible:
        return ", ".join(recipients)
    visible = ", ".join(recipients[:max_visible])
    extra = len(recipients) - max_visible
    return f"{visible}, +{extra} more"


def format_one_line_meta(
    *, kind: str,
    date: Optional[str] = None,
    sender: Optional[str] = None,
    recipients: Optional[list[str]] = None,
    subject: Optional[str] = None,
    filename: Optional[str] = None,
    chat_name: Optional[str] = None,
) -> str:
    """Return a one-line metadata preview for an evidence source row.

    Format varies by kind:
    - email:      📧 [date] [sender] → [recipient1, recipient2, +N more] · [subject]
    - chat:       💬 [date] · [chat_name] · [sender] · [subject (message preview)]
    - attachment: 📎 [date] [filename] · from email of [sender]
    - document:   📄 [date] [filename]
    - photo:      📷 [date] [filename]
    - annotation: 📝 [date] [subject (preview)]
    """
    icon = icon_for(kind)
    if kind == "email":
        parts = []
        if date:
            parts.append(date[:16])
        if sender:
            who = sender
            if recipients:
                who = f"{sender} → {_format_recipients(recipients)}"
            parts.append(who)
        title = _truncate(subject or "", 60)
        line = f"{icon} {' · '.join(parts)}"
        if title:
            line += f" · {title}"
        return line

    if kind == "chat":
        parts = []
        if date:
            parts.append(date[:16])
        if chat_name:
            parts.append(chat_name)
        if sender:
            parts.append(sender)
        title = _truncate(subject or "", 80)
        line = f"{icon} {' · '.join(parts)}"
        if title:
            line += f" · {title}"
        return line

    if kind == "attachment":
        parts = []
        if date:
            parts.append(date[:16])
        if filename:
            parts.append(filename)
        line = f"{icon} {' · '.join(parts)}"
        if sender:
            line += f" · from email of {sender}"
        return line

    # document, photo, annotation, unknown
    parts = []
    if date:
        parts.append(date[:16])
    title = _truncate(subject or filename or "", 80)
    if title:
        parts.append(title)
    return f"{icon} {' · '.join(parts)}" if parts else icon
