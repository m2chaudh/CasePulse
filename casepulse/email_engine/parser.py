"""Email parsing utilities — HTML conversion, forwarded message detection."""
from __future__ import annotations

import re


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
        # Outlook-style: From/Sent/To/Subject on separate lines with values on next line
        r"From:\s*\n.+\nSent:\s*\n",
        r"From:\s*\n.+\nDate:\s*\n",
    ]

    for pattern in fwd_patterns:
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            is_forwarded = True
            remaining = body_text[match.start():]
            original_sender = _extract_field(remaining, "From")
            original_date = _extract_field(remaining, "Date") or _extract_field(remaining, "Sent")

            # Outlook multi-line format: "From:\nName\nSent:\nDate\nTo:\nemail"
            if not original_sender:
                original_sender = _extract_field_multiline(remaining, "From")
            if not original_date:
                original_date = _extract_field_multiline(remaining, "Sent") or _extract_field_multiline(remaining, "Date")

            break

    # Also check X-Forwarded-Message-Id header
    if headers.get("X-Forwarded-Message-Id"):
        is_forwarded = True

    return is_forwarded, original_sender, original_date


def _extract_field_multiline(text: str, field_name: str) -> str:
    """Extract a field value where the value is on the NEXT line after the label.

    Handles Outlook-style:
        From:
        Leah Simeone
        Sent:
        July 8, 2025 11:31 AM
        To:
        singh_imanisha@hotmail.com
    """
    pattern = rf"^{field_name}:\s*$\n(.+?)$"
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        value = match.group(1).strip()
        if field_name.lower() in ("from", "to"):
            # Try to extract email
            email_match = re.search(r"<([^>]+)>", value)
            if email_match:
                return email_match.group(1).lower()
            email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", value)
            if email_match:
                return email_match.group(0).lower()
            # Just a name — return it
            return value
        return value
    return ""


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


