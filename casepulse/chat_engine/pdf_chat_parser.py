"""Parse chat exports saved as PDF files.

Handles various chat app PDF exports (iMessage, Messenger, Telegram, etc.)
by extracting text and attempting to identify message boundaries.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.config import get_data_dir


# Common patterns for timestamps in chat PDFs
CHAT_PDF_PATTERNS = [
    # "Jan 15, 2025, 2:30 PM" or "January 15, 2025 at 2:30 PM"
    re.compile(
        r"(\w{3,9}\s+\d{1,2},?\s+\d{4},?\s*(?:at\s+)?\d{1,2}:\d{2}(?::\d{2})?\s*[APap][Mm]?)"
    ),
    # "2025-01-15 14:30" or "2025-01-15T14:30:00"
    re.compile(
        r"(\d{4}-\d{2}-\d{2}[T\s]\d{1,2}:\d{2}(?::\d{2})?)"
    ),
    # "15/01/2025 14:30" or "01/15/2025 2:30 PM"
    re.compile(
        r"(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?\s*[APap]?[Mm]?)"
    ),
    # "Mon, Jan 15, 2025"
    re.compile(
        r"(\w{3},\s+\w{3}\s+\d{1,2},\s+\d{4})"
    ),
]

# Date formats to try when parsing extracted timestamps
PDF_DATE_FORMATS = [
    "%b %d, %Y, %I:%M %p",
    "%b %d, %Y %I:%M %p",
    "%B %d, %Y at %I:%M %p",
    "%B %d, %Y, %I:%M %p",
    "%b %d, %Y, %I:%M:%S %p",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %I:%M:%S %p",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%a, %b %d, %Y",
]


def parse_pdf_chat(file_path: str, platform_hint: str = "auto") -> dict:
    """Parse a chat PDF export.

    Args:
        file_path: Path to the PDF file
        platform_hint: 'auto', 'imessage', 'messenger', 'telegram', 'generic'

    Returns:
        {
            messages: list[dict],
            platform: str,
            images: list[str],   # extracted image paths
            raw_text: str,       # full extracted text for fallback
            page_count: int,
        }
    """
    path = Path(file_path)
    result = {
        "messages": [],
        "platform": platform_hint,
        "images": [],
        "raw_text": "",
        "page_count": 0,
    }

    # Extract text from PDF
    import pdfplumber
    all_text = []
    images_extracted = []

    img_dir = get_data_dir() / "attachments" / f"pdf_chat_{path.stem}"
    img_dir.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(str(path)) as pdf:
        result["page_count"] = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                all_text.append(page_text)

            # Extract images from the page
            try:
                for img_idx, img in enumerate(page.images):
                    # pdfplumber gives image metadata but not raw bytes easily
                    # Save image coordinates for reference
                    images_extracted.append({
                        "page": page_num + 1,
                        "bbox": (img.get("x0"), img.get("top"), img.get("x1"), img.get("bottom")),
                    })
            except Exception:
                pass

    full_text = "\n".join(all_text)
    result["raw_text"] = full_text

    # Try to extract images using a different approach
    try:
        import fitz  # PyMuPDF — optional, better for image extraction
        doc = fitz.open(str(path))
        for page_num in range(len(doc)):
            page = doc[page_num]
            for img_idx, img in enumerate(page.get_images()):
                xref = img[0]
                pix = fitz.Pixmap(doc, xref)
                if pix.n < 5:  # GRAY or RGB
                    img_path = img_dir / f"page{page_num + 1}_img{img_idx + 1}.png"
                    pix.save(str(img_path))
                    result["images"].append(str(img_path))
                pix = None
        doc.close()
    except ImportError:
        # PyMuPDF not installed — that's fine, we have the text
        pass
    except Exception:
        pass

    # Detect platform if auto
    if platform_hint == "auto":
        result["platform"] = _detect_platform(full_text)

    # Parse messages from text
    result["messages"] = _parse_messages_from_text(full_text, result["platform"])

    return result


def _detect_platform(text: str) -> str:
    """Try to detect which chat platform the PDF came from."""
    text_lower = text.lower()

    if "imessage" in text_lower or "messages" in text_lower and "apple" in text_lower:
        return "imessage"
    elif "messenger" in text_lower or "facebook" in text_lower:
        return "messenger"
    elif "telegram" in text_lower:
        return "telegram"
    elif "whatsapp" in text_lower:
        return "whatsapp"
    elif "signal" in text_lower:
        return "signal"

    return "generic"


def _parse_messages_from_text(text: str, platform: str) -> list[dict]:
    """Parse individual messages from extracted PDF text."""
    messages = []
    lines = text.split("\n")

    # Strategy: find timestamp patterns and use them as message boundaries
    current_msg = None
    last_timestamp = None
    last_sender = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try to find a timestamp in this line
        timestamp = None
        ts_end = 0
        for pattern in CHAT_PDF_PATTERNS:
            m = pattern.search(line)
            if m:
                ts_str = m.group(1)
                parsed = _parse_pdf_timestamp(ts_str)
                if parsed:
                    timestamp = parsed
                    ts_end = m.end()
                    break

        if timestamp:
            # Save previous message
            if current_msg:
                messages.append(current_msg)

            # Extract sender and message from remaining text
            remaining = line[ts_end:].strip().lstrip("-:").strip()
            sender, message = _extract_sender_message(remaining)

            if not sender and last_sender:
                sender = last_sender

            current_msg = {
                "timestamp": timestamp,
                "sender": sender,
                "message": message,
                "is_system": False,
                "has_media": False,
                "media_ref": "",
            }
            last_timestamp = timestamp
            if sender:
                last_sender = sender
        elif current_msg:
            # Continuation of previous message
            current_msg["message"] += "\n" + line
        else:
            # Before any timestamp found — could be header/metadata
            # Try to extract as a message anyway
            sender, message = _extract_sender_message(line)
            if sender and message:
                current_msg = {
                    "timestamp": None,
                    "sender": sender,
                    "message": message,
                    "is_system": False,
                    "has_media": False,
                    "media_ref": "",
                }

    if current_msg:
        messages.append(current_msg)

    return messages


def _parse_pdf_timestamp(ts_str: str) -> Optional[datetime]:
    """Try to parse a timestamp string from a PDF."""
    ts_str = ts_str.strip().rstrip(",")
    for fmt in PDF_DATE_FORMATS:
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _extract_sender_message(text: str) -> tuple[str, str]:
    """Try to split 'Sender: message' or 'Sender message'."""
    # Pattern: "Name: message"
    m = re.match(r"^([A-Z][\w\s.'-]{1,30}):\s+(.+)", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Pattern: "Name\nmessage" (name on its own line)
    parts = text.split("\n", 1)
    if len(parts) == 2 and len(parts[0]) < 40 and not any(c in parts[0] for c in ".!?"):
        return parts[0].strip(), parts[1].strip()

    # Can't determine sender
    return "", text


def parse_generic_text_chat(file_path: str) -> list[dict]:
    """Parse any generic text-based chat export.

    Tries to detect message boundaries by looking for timestamp patterns.
    Falls back to treating each non-empty line as a message.
    """
    path = Path(file_path)
    content = ""
    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
        try:
            content = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, ValueError):
            continue

    if not content:
        return []

    # First try WhatsApp format
    from casepulse.chat_engine.whatsapp_parser import parse_whatsapp_txt
    wa_messages = parse_whatsapp_txt(file_path)
    if wa_messages and len(wa_messages) > 2:
        return wa_messages

    # Try generic timestamp-based parsing
    return _parse_messages_from_text(content, "generic")
