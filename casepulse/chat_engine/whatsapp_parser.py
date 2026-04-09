"""Parse WhatsApp chat exports (.txt and .zip with media)."""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.config import get_data_dir

# WhatsApp timestamp patterns — covers iOS, Android, and regional variants
# iOS:    [1/15/25, 2:30:45 PM] Sender: message
# Android: 1/15/25, 2:30 PM - Sender: message
# EU:     15/01/2025, 14:30 - Sender: message
# Bracket: [15/01/2025, 14:30:45] Sender: message
TIMESTAMP_PATTERNS = [
    # [M/D/YY, H:MM:SS AM/PM] Sender: msg  (iOS)
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[APap][Mm]?)\]\s+"
        r"(.+?):\s(.+)"
    ),
    # M/D/YY, H:MM AM/PM - Sender: msg  (Android)
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?\s*[APap][Mm]?)\s*-\s+"
        r"(.+?):\s(.+)"
    ),
    # D/M/YYYY, HH:MM - Sender: msg  (EU 24h)
    re.compile(
        r"^(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?)\s*-\s+"
        r"(.+?):\s(.+)"
    ),
    # [D/M/YYYY, HH:MM:SS] Sender: msg  (bracket 24h)
    re.compile(
        r"^\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?)\]\s+"
        r"(.+?):\s(.+)"
    ),
    # YYYY-MM-DD, HH:MM - Sender: msg  (ISO-ish)
    re.compile(
        r"^(\d{4}-\d{2}-\d{2},\s*\d{1,2}:\d{2}(?::\d{2})?)\s*-\s+"
        r"(.+?):\s(.+)"
    ),
]

# System message patterns (no sender)
SYSTEM_PATTERNS = [
    re.compile(r"^\[(.+?)\]\s+(.+)$"),
    re.compile(r"^(.+?)\s*-\s+(.+)$"),
]

# Date parsing formats to try
DATE_FORMATS = [
    "%m/%d/%y, %I:%M:%S %p",
    "%m/%d/%y, %I:%M %p",
    "%m/%d/%Y, %I:%M:%S %p",
    "%m/%d/%Y, %I:%M %p",
    "%d/%m/%y, %H:%M:%S",
    "%d/%m/%y, %H:%M",
    "%d/%m/%Y, %H:%M:%S",
    "%d/%m/%Y, %H:%M",
    "%m/%d/%y, %H:%M:%S",
    "%m/%d/%y, %H:%M",
    "%Y-%m-%d, %H:%M:%S",
    "%Y-%m-%d, %H:%M",
]

MEDIA_OMITTED_PATTERNS = [
    "<Media omitted>",
    "<media omitted>",
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "document omitted",
    "GIF omitted",
    "Contact card omitted",
]


def parse_timestamp(ts_str: str) -> Optional[datetime]:
    """Try multiple date formats to parse a WhatsApp timestamp."""
    ts_str = ts_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def parse_whatsapp_txt(file_path: str) -> list[dict]:
    """Parse a WhatsApp chat export .txt file.

    Returns list of message dicts:
    {
        timestamp: datetime,
        sender: str,
        message: str,
        is_system: bool,
        has_media: bool,
        media_ref: str (filename reference if media attached),
    }
    """
    path = Path(file_path)
    # Try common encodings
    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            content = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, ValueError):
            continue

    if not content:
        return []

    lines = content.split("\n")
    messages = []
    current_msg = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to match as a new message
        matched = False
        for pattern in TIMESTAMP_PATTERNS:
            m = pattern.match(line)
            if m:
                # Save previous message
                if current_msg:
                    messages.append(current_msg)

                ts_str, sender, msg_text = m.group(1), m.group(2), m.group(3)
                timestamp = parse_timestamp(ts_str)

                # Check for media
                has_media = False
                media_ref = ""
                for omit in MEDIA_OMITTED_PATTERNS:
                    if omit.lower() in msg_text.lower():
                        has_media = True
                        break
                # Check for attached file reference (e.g., "IMG-20250115-WA0001.jpg (file attached)")
                file_match = re.search(r"([\w\-]+\.\w{3,4})\s*\(file attached\)", msg_text)
                if file_match:
                    has_media = True
                    media_ref = file_match.group(1)

                current_msg = {
                    "timestamp": timestamp,
                    "timestamp_raw": ts_str,
                    "sender": sender.strip(),
                    "message": msg_text.strip(),
                    "is_system": False,
                    "has_media": has_media,
                    "media_ref": media_ref,
                }
                matched = True
                break

        if not matched:
            # Check if it's a system message (encryption notice, group changes, etc.)
            is_system = False
            for sp in SYSTEM_PATTERNS:
                m = sp.match(line)
                if m and any(kw in line.lower() for kw in [
                    "encryption", "created group", "added", "removed",
                    "left", "changed", "security code", "messages and calls",
                ]):
                    if current_msg:
                        messages.append(current_msg)
                    current_msg = {
                        "timestamp": parse_timestamp(m.group(1)) if len(m.groups()) > 1 else None,
                        "timestamp_raw": m.group(1) if len(m.groups()) > 1 else "",
                        "sender": "__system__",
                        "message": line,
                        "is_system": True,
                        "has_media": False,
                        "media_ref": "",
                    }
                    is_system = True
                    break

            if not is_system and current_msg:
                # Continuation of previous message (multi-line)
                current_msg["message"] += "\n" + line

    # Don't forget the last message
    if current_msg:
        messages.append(current_msg)

    return messages


def parse_whatsapp_zip(zip_path: str, extract_dir: Optional[str] = None) -> tuple[list[dict], list[str]]:
    """Parse a WhatsApp chat export .zip file (includes media).

    Returns (messages, media_files) where media_files are extracted file paths.
    """
    zip_path = Path(zip_path)
    if extract_dir is None:
        extract_dir = get_data_dir() / "attachments" / f"whatsapp_{zip_path.stem}"
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    media_files = []
    messages = []

    with zipfile.ZipFile(str(zip_path), "r") as zf:
        zf.extractall(str(extract_dir))

        # Find the chat .txt file
        txt_files = [f for f in zf.namelist() if f.endswith(".txt") and "chat" in f.lower()]
        if not txt_files:
            txt_files = [f for f in zf.namelist() if f.endswith(".txt")]

        if txt_files:
            chat_file = extract_dir / txt_files[0]
            messages = parse_whatsapp_txt(str(chat_file))

        # Catalog media files
        for name in zf.namelist():
            if not name.endswith(".txt"):
                media_path = extract_dir / name
                if media_path.exists():
                    media_files.append(str(media_path))

    # Link media references in messages to actual files
    for msg in messages:
        if msg["media_ref"]:
            for mf in media_files:
                if msg["media_ref"] in mf:
                    msg["media_path"] = mf
                    break

    return messages, media_files


def detect_chat_name(messages: list[dict]) -> str:
    """Try to detect the chat/conversation name from messages."""
    senders = set()
    for msg in messages:
        if not msg["is_system"] and msg["sender"] != "__system__":
            senders.add(msg["sender"])
    if len(senders) == 2:
        return " & ".join(sorted(senders))
    elif len(senders) > 2:
        return f"Group ({len(senders)} participants)"
    elif len(senders) == 1:
        return list(senders)[0]
    return "Unknown Chat"


def get_participants(messages: list[dict]) -> list[str]:
    """Get unique participants from parsed messages."""
    return sorted(set(
        msg["sender"] for msg in messages
        if not msg["is_system"] and msg["sender"] != "__system__"
    ))
