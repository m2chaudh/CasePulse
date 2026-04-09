"""Email parsing utilities — HTML conversion, forwarded message detection."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional


def html_to_text(html: str) -> str:
    """Convert HTML email body to plain text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        # Remove script and style elements
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        # Collapse multiple blank lines
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)
    except Exception:
        # Fallback: strip tags with regex
        text = re.sub(r"<[^>]+>", "", html)
        return text.strip()


def detect_forwarded_content(subject: str, body_text: str,
                              headers: dict) -> tuple[bool, str, str]:
    """Detect if an email contains forwarded content and extract original sender/date.

    Returns:
        (is_forwarded, original_sender_email, original_date_str)
    """
    is_forwarded = False
    original_sender = ""
    original_date = ""

    # Check subject line
    subject_lower = subject.lower().strip()
    if subject_lower.startswith(("fw:", "fwd:", "forwarded:")):
        is_forwarded = True

    # Check for forwarded message markers in body
    fwd_patterns = [
        r"[-]+\s*Forwarded message\s*[-]+",
        r"[-]+\s*Original Message\s*[-]+",
        r"Begin forwarded message:",
        r"From:.*\nSent:.*\nTo:.*\nSubject:",
        r"From:.*\nDate:.*\nTo:.*\nSubject:",
    ]

    for pattern in fwd_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            is_forwarded = True
            # Try to extract original sender and date from the forwarded header block
            remaining = body_text[match.start():]
            original_sender = _extract_field(remaining, "From")
            original_date = _extract_field(remaining, "Date") or _extract_field(remaining, "Sent")
            break

    # Also check X-Forwarded-Message-Id header
    if headers.get("X-Forwarded-Message-Id"):
        is_forwarded = True

    return is_forwarded, original_sender, original_date


def _extract_field(text: str, field_name: str) -> str:
    """Extract a field value from forwarded message header block."""
    pattern = rf"^{field_name}:\s*(.+?)$"
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        value = match.group(1).strip()
        # If it's an email in "Name <email>" format, extract just the email
        if field_name.lower() == "from":
            email_match = re.search(r"<([^>]+)>", value)
            if email_match:
                return email_match.group(1).lower()
            # Might just be an email address
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", value)
            if email_match:
                return email_match.group(0).lower()
        return value
    return ""


def extract_embedded_messages(body_text: str) -> list[dict]:
    """Extract embedded/quoted messages from email body.

    Returns list of dicts with keys: sender, date, subject, body
    """
    messages = []

    # Pattern for forwarded message blocks
    fwd_markers = [
        (r"[-]{3,}\s*Forwarded message\s*[-]{3,}", "forwarded"),
        (r"[-]{3,}\s*Original Message\s*[-]{3,}", "original"),
        (r"Begin forwarded message:", "forwarded"),
    ]

    for pattern, msg_type in fwd_markers:
        for match in re.finditer(pattern, body_text, re.IGNORECASE):
            remaining = body_text[match.end():]
            msg = _parse_embedded_header_block(remaining)
            if msg:
                msg["type"] = msg_type
                messages.append(msg)

    return messages


def _parse_embedded_header_block(text: str) -> Optional[dict]:
    """Parse the header block of an embedded/forwarded message."""
    lines = text.strip().split("\n")
    result = {
        "sender": "",
        "sender_email": "",
        "date": "",
        "subject": "",
        "body": "",
    }

    header_end = 0
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            header_end = i + 1
            break

        lower = line.lower()
        if lower.startswith("from:"):
            value = line[5:].strip()
            result["sender"] = value
            email_match = re.search(r"<([^>]+)>", value)
            if email_match:
                result["sender_email"] = email_match.group(1).lower()
            else:
                email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", value)
                if email_match:
                    result["sender_email"] = email_match.group(0).lower()
        elif lower.startswith("date:") or lower.startswith("sent:"):
            result["date"] = line.split(":", 1)[1].strip()
        elif lower.startswith("subject:"):
            result["subject"] = line[8:].strip()
        else:
            # Unknown header or body start
            header_end = i
            break

    # Everything after headers is the body
    if header_end < len(lines):
        result["body"] = "\n".join(lines[header_end:]).strip()

    # Only return if we found meaningful content
    if result["sender_email"] or result["sender"]:
        return result
    return None


def parse_email_thread(body_text: str) -> list[dict]:
    """Parse an email thread/conversation into individual messages.

    Handles patterns like:
    - "On [date], [name] wrote:"
    - Lines starting with ">"
    - Forwarded message blocks
    """
    messages = []

    # Split by "On ... wrote:" pattern
    wrote_pattern = r"On\s+(.+?),?\s+(.+?)\s+wrote:"
    parts = re.split(wrote_pattern, body_text, flags=re.IGNORECASE)

    if len(parts) > 1:
        # First part is the newest message
        messages.append({
            "body": parts[0].strip(),
            "is_latest": True,
        })

        # Subsequent parts come in triples: (date, sender, body)
        i = 1
        while i + 2 < len(parts):
            messages.append({
                "date": parts[i].strip(),
                "sender": parts[i + 1].strip(),
                "body": _clean_quoted_text(parts[i + 2]),
                "is_latest": False,
            })
            i += 3
    else:
        # No thread structure detected
        messages.append({
            "body": body_text.strip(),
            "is_latest": True,
        })

    # Also extract any forwarded messages
    embedded = extract_embedded_messages(body_text)
    for emb in embedded:
        messages.append({
            "sender": emb.get("sender_email", emb.get("sender", "")),
            "date": emb.get("date", ""),
            "subject": emb.get("subject", ""),
            "body": emb.get("body", ""),
            "is_forwarded": True,
            "is_latest": False,
        })

    return messages


def _clean_quoted_text(text: str) -> str:
    """Remove quote markers (>) from text."""
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        # Remove leading > markers
        while line.startswith(">"):
            line = line[1:]
        cleaned.append(line.strip())
    return "\n".join(cleaned)
