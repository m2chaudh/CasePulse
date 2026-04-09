"""Parse ChatVault HTML exports from WhatsApp."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup


def parse_chatvault_html(file_path: str) -> dict:
    """Parse a ChatVault HTML export.

    Returns:
        {
            messages: list[dict],
            chat_name: str,
            participants: list[str],
            media_dir: str or None,
        }
    """
    path = Path(file_path)
    html = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")

    # Extract chat name from title
    title_tag = soup.find("title")
    chat_name = ""
    if title_tag:
        # "Manisha — ChatVault" -> "Manisha"
        chat_name = title_tag.get_text().split("—")[0].strip().split("–")[0].strip()

    # Find media directory
    media_dir = None
    parent = path.parent / "media"
    if parent.exists():
        media_dir = str(parent)

    messages = []
    participants = set()

    # Find all message containers
    # ChatVault uses date headers and message bubbles
    current_date = ""

    # Look for date separator elements
    date_elements = soup.find_all(class_="date-separator")
    if not date_elements:
        date_elements = soup.find_all(class_="date-badge")
    if not date_elements:
        # Try to find date headers differently
        date_elements = soup.find_all(attrs={"data-date": True})

    # Parse messages by iterating through the chat container
    chat_container = soup.find(class_="chat") or soup.find(class_="messages") or soup.body

    if not chat_container:
        return {"messages": [], "chat_name": chat_name, "participants": [], "media_dir": media_dir}

    # Iterate through all elements in the chat
    for element in chat_container.find_all(True, recursive=True):
        classes = element.get("class", [])
        if not classes:
            continue

        # Date separators
        if any(c in classes for c in ["date-separator", "date-badge", "date-header"]):
            date_text = element.get_text(strip=True)
            current_date = _parse_chatvault_date(date_text)
            continue

        # Message bubbles - detect sent vs received
        is_message = False
        is_sent = False
        is_system = False

        if "sent" in classes or "msg-sent" in classes:
            is_message = True
            is_sent = True
        elif "received" in classes or "msg-received" in classes or "recv" in classes:
            is_message = True
            is_sent = False
        elif "system" in classes or "msg-system" in classes:
            is_system = True
            is_message = True

        if not is_message:
            continue

        # Skip if this is a child of a message we already processed
        # (avoid double counting nested elements)
        parent_msg = element.find_parent(class_=lambda c: c and any(
            x in (c if isinstance(c, list) else [c])
            for x in ["sent", "received", "recv", "msg-sent", "msg-received"]
        ))
        if parent_msg and parent_msg != element:
            continue

        # Extract sender name
        sender = ""
        sender_el = element.find(class_="msg-sender") or element.find(class_="sender")
        if sender_el:
            sender = sender_el.get_text(strip=True)

        # Extract message text
        text = ""
        text_el = element.find(class_="msg-text") or element.find(class_="text")
        if text_el:
            text = text_el.get_text(strip=True)
        elif not is_system:
            # Fallback: get all text content
            text = element.get_text(strip=True)
            # Remove sender and time from text if embedded
            if sender and text.startswith(sender):
                text = text[len(sender):].strip()

        if is_system:
            text = element.get_text(strip=True)

        # Extract time
        time_str = ""
        time_el = element.find(class_="msg-time") or element.find(class_="time")
        if time_el:
            time_str = time_el.get_text(strip=True)
            # Remove time from text if it got included
            if text.endswith(time_str):
                text = text[:-len(time_str)].strip()

        # Build timestamp
        timestamp = None
        if current_date and time_str:
            timestamp = _combine_date_time(current_date, time_str)
        elif current_date:
            timestamp = current_date

        # Check for media
        has_media = False
        media_path = ""
        media_type = ""

        img = element.find("img")
        if img and img.get("src"):
            has_media = True
            media_type = "image"
            src = img["src"]
            if media_dir and not src.startswith("http"):
                media_path = str(Path(path.parent) / src)

        video = element.find("video")
        if video:
            has_media = True
            media_type = "video"
            source = video.find("source")
            if source and source.get("src"):
                media_path = str(Path(path.parent) / source["src"])

        audio = element.find("audio")
        if audio:
            has_media = True
            media_type = "audio"

        if not text and not has_media and not is_system:
            continue

        if sender:
            participants.add(sender)

        messages.append({
            "timestamp": timestamp,
            "sender": sender,
            "message": text,
            "is_system": is_system,
            "has_media": has_media,
            "media_type": media_type,
            "media_path": media_path,
            "is_sent": is_sent,
        })

    return {
        "messages": messages,
        "chat_name": chat_name,
        "participants": sorted(participants),
        "media_dir": media_dir,
    }


def _parse_chatvault_date(date_text: str) -> Optional[datetime]:
    """Parse date from ChatVault date separator."""
    date_text = date_text.strip()

    formats = [
        "%B %d, %Y",       # "January 15, 2025"
        "%b %d, %Y",       # "Jan 15, 2025"
        "%m/%d/%Y",         # "01/15/2025"
        "%d/%m/%Y",         # "15/01/2025"
        "%Y-%m-%d",         # "2025-01-15"
        "%A, %B %d, %Y",   # "Wednesday, January 15, 2025"
        "%a, %b %d, %Y",   # "Wed, Jan 15, 2025"
    ]

    # Handle relative dates
    lower = date_text.lower()
    if lower in ("today", "yesterday"):
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for fmt in formats:
        try:
            return datetime.strptime(date_text, fmt)
        except ValueError:
            continue

    # Try to extract date with regex
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", date_text)
    if m:
        parts = [int(x) for x in m.groups()]
        if parts[2] < 100:
            parts[2] += 2000
        try:
            return datetime(parts[2], parts[0], parts[1])
        except ValueError:
            try:
                return datetime(parts[2], parts[1], parts[0])
            except ValueError:
                pass

    return None


def _combine_date_time(date_dt: datetime, time_str: str) -> Optional[datetime]:
    """Combine a date datetime with a time string like '2:30 PM' or '14:30'."""
    if not date_dt:
        return None

    time_str = time_str.strip().upper()

    time_formats = [
        "%I:%M %p",    # "2:30 PM"
        "%I:%M:%S %p", # "2:30:45 PM"
        "%H:%M",       # "14:30"
        "%H:%M:%S",    # "14:30:45"
    ]

    for fmt in time_formats:
        try:
            t = datetime.strptime(time_str, fmt)
            return date_dt.replace(hour=t.hour, minute=t.minute, second=t.second)
        except ValueError:
            continue

    return date_dt
