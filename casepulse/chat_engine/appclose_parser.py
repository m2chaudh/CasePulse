"""Parse AppClose co-parenting app PDF exports."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# Pattern: "Name on M/D/YYYY H:MMAM/PM texted (viewed by Other on M/D/YYYY H:MMAM/PM):"
# Also: "Name on M/D/YYYY H:MMAM/PM Received permission to..."
# Also: "Name on M/D/YYYY H:MMAM/PM sent a photo"
# Note: names may be split across lines in PDF extraction
MSG_PATTERN = re.compile(
    r"([\w][\w\s]*?)\s+on\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm])\s+"
    r"(?:texted\s*(?:\(viewed by\s+[^)]+\))?|sent\s+\w+|Received\s+\w+|Incoming|Outgoing)(?:\s*:)?",
)

# Date header pattern: standalone date like "9/16/2024"
DATE_HEADER = re.compile(r"^(\d{1,2}/\d{1,2}/\d{4})$", re.MULTILINE)

# Header that repeats on every page
PAGE_HEADER = re.compile(
    r"AppClose Records Export\s*\n"
    r"Period:.*?\n"
    r"Requested by:.*?(?:\n.*?signed up on.*?\n)",
    re.DOTALL
)


def parse_appclose_pdf(file_path: str) -> list[dict]:
    """Parse an AppClose PDF export into structured messages.

    Returns list of {timestamp, sender, message, is_system, has_media, media_ref}
    """
    import pdfplumber

    # Extract all text
    all_text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text.append(text)

    full_text = "\n".join(all_text)

    # Fix PDF line breaks in names — "Manish\nChaudhary on" → "Manish Chaudhary on"
    # Replace newlines that split a name before "on DATE"
    full_text = re.sub(
        r"(\w)\n(\w+(?:\s+\w+)*\s+on\s+\d{1,2}/\d{1,2}/\d{4})",
        r"\1 \2",
        full_text
    )

    # Also fix "Manisha\nChoudhary on" patterns
    full_text = re.sub(r"\n(Choudhary|Chaudhary)", r" \1", full_text)

    # Remove repeating page headers
    full_text = PAGE_HEADER.sub("", full_text)

    # Remove the initial header/preamble
    full_text = re.sub(r"^\s*Conversations\s*$", "", full_text, flags=re.MULTILINE)
    full_text = re.sub(r"^\*This screen will display.*$", "", full_text, flags=re.MULTILINE)

    messages = []

    # Find all message starts
    matches = list(MSG_PATTERN.finditer(full_text))

    for i, match in enumerate(matches):
        sender = match.group(1).strip()
        date_str = match.group(2).strip()

        # Parse timestamp
        timestamp = None
        try:
            timestamp = datetime.strptime(date_str, "%m/%d/%Y %I:%M%p")
        except ValueError:
            try:
                timestamp = datetime.strptime(date_str, "%m/%d/%Y %I:%M %p")
            except ValueError:
                pass

        # Extract message body — everything between this match end and next match start
        msg_start = match.end()
        # Skip the colon and whitespace after the pattern
        while msg_start < len(full_text) and full_text[msg_start] in ":\n ":
            msg_start += 1

        if i + 1 < len(matches):
            msg_end = matches[i + 1].start()
        else:
            msg_end = len(full_text)

        body = full_text[msg_start:msg_end].strip()

        # Clean up body — remove date headers that appear inline
        body = DATE_HEADER.sub("", body).strip()

        # Detect system messages
        is_system = False
        has_media = False
        full_match = match.group(0)
        if "Received permission" in full_match:
            is_system = True
            body = full_match.split("Received", 1)[1].strip() if "Received" in full_match else body
            body = f"Received {body}"
        elif "sent a photo" in full_match or "sent a video" in full_match:
            has_media = True
            body = body or "[Media sent]"
        elif "sent a file" in full_match:
            has_media = True

        if not body and not is_system:
            continue

        messages.append({
            "timestamp": timestamp,
            "sender": sender,
            "message": body,
            "is_system": is_system,
            "has_media": has_media,
            "media_ref": "",
        })

    return messages


def get_participants(messages: list[dict]) -> list[str]:
    """Get unique participants."""
    return sorted(set(
        m["sender"] for m in messages
        if not m["is_system"] and m["sender"]
    ))
