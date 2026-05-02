"""AppClose PDF v2 parser — captures Sent + Viewed-by timestamps + page
numbers per message. Pure parsing, no DB writes; intended to feed the
dry-run preview UI on the Data Repairs page so the user can verify
sender / sent / viewed accuracy BEFORE any migration runs.

Distinct from `casepulse/chat_engine/appclose_parser.py` (the original
ingest path) — keeps that one untouched. A future migration can
consume this v2 output to rebuild the chat_messages rows cleanly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# A message header line: "Manish Chaudhary on 9/16/2024 5:21PM texted (viewed by Manisha on 9/16/2024 5:35PM):"
# - Sender + 'on' + sent date+time
# - Action verb: texted | sent a photo | sent a video | sent a file | Received permission ...
# - Optional 1+ '(viewed by NAME on DATE TIME)' clauses — group threads can have multiple
HEADER_RE = re.compile(
    r"(?P<sender>[\w][\w\s'-]*?)\s+on\s+"
    r"(?P<sent>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm])\s+"
    r"(?P<action>texted|sent\s+\w+|Received\s+\w+)"
    r"(?P<viewed>(?:\s*\(viewed by\s+[^)]+\))*)"
    r"\s*:?",
)

# Inside the (viewed by ...) clause — extract recipient + their viewed time.
VIEWED_RE = re.compile(
    r"viewed by\s+(?P<recipient>[^()]+?)\s+on\s+"
    r"(?P<viewed_ts>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm])",
)

# AppClose page footer: "Generated: M/D/YYYY H:MMAM Page N of M"
PAGE_FOOTER_RE = re.compile(
    r"Generated:\s*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm]\s+"
    r"Page\s+(?P<page>\d+)\s+of\s+(?P<total>\d+)",
)

# Header preamble (export metadata)
PREAMBLE_RE = re.compile(
    r"AppClose Records Export\s*\n"
    r"Period:[^\n]*\n*"
    r"Requested by:[^\n]*\n*"
    r"signed up on\s+\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm]",
    re.IGNORECASE,
)

# "Attachment Img. <filename> to page N" — bottom of the export
ATTACHMENT_REF_RE = re.compile(
    r"Attachment\s+Img\.\s+(?P<filename>\S[^\n]*?)\s+to\s+page\s+(?P<page>\d+)",
    re.IGNORECASE,
)


def _parse_dt(s: str) -> Optional[datetime]:
    s = s.strip().replace("  ", " ")
    for fmt in ("%m/%d/%Y %I:%M%p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


@dataclass
class Viewed:
    recipient: str
    viewed_at: Optional[datetime]
    raw: str  # the literal '(viewed by NAME on DATE TIME)' substring from PDF


@dataclass
class ParsedMessage:
    sender: str
    sent_at: Optional[datetime]
    sent_at_raw: str       # literal date/time from PDF
    action: str            # 'texted' | 'sent a photo' | etc.
    body: str              # body text with page footers stripped
    viewed: list[Viewed] = field(default_factory=list)
    page: Optional[int] = None      # source PDF page where the header lives
    raw_header: str = ""            # the literal header line from the PDF
    raw_body_excerpt: str = ""      # first 300 chars of the original body chunk before strip
    attachment_refs: list[dict] = field(default_factory=list)  # filenames mentioned 'to page N'


def _strip_page_footers(text: str) -> str:
    """Remove 'Generated: ... Page N of M' lines and isolated 'M/D/YYYY H:MMAM/PM'
    repeats."""
    text = PAGE_FOOTER_RE.sub("", text)
    text = re.sub(
        r"^\s*\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[APap][Mm]\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    return text


def _build_page_index(pages_text: list[str]) -> list[tuple[int, int]]:
    """Return [(page_number, char_offset_in_full_text)] sorted by offset.
    Used to map a header position back to its source PDF page."""
    offsets = []
    cursor = 0
    for i, t in enumerate(pages_text, start=1):
        offsets.append((i, cursor))
        cursor += len(t) + 1  # +1 for the join newline
    return offsets


def _page_for_offset(offset: int, page_index: list[tuple[int, int]]) -> int:
    last_page = 1
    for p, off in page_index:
        if off <= offset:
            last_page = p
        else:
            break
    return last_page


def parse_appclose_pdf(file_path: str) -> list[ParsedMessage]:
    """Parse an AppClose PDF export into structured ParsedMessage records.

    Sender, sent_at, viewed_by timestamps, body, page number, and
    attachment-image references are all preserved verbatim from the PDF.
    No DB writes — caller decides what to do with the result.
    """
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            pages_text.append(t)

    full_text = "\n".join(pages_text)
    page_index = _build_page_index(pages_text)

    # Pre-clean — fix PDF line-break-in-names so the regex matches:
    # "Manish\nChaudhary on" → "Manish Chaudhary on"
    full_text = re.sub(
        r"(\w)\n(\w+(?:\s+\w+)*\s+on\s+\d{1,2}/\d{1,2}/\d{4})",
        r"\1 \2",
        full_text,
    )
    full_text = re.sub(r"\n(Choudhary|Chaudhary)", r" \1", full_text)

    # Remove preamble + "Conversations" / "*This screen…" blank-state lines
    full_text = PREAMBLE_RE.sub("", full_text)
    full_text = re.sub(r"^\s*Conversations\s*$", "", full_text, flags=re.MULTILINE)
    full_text = re.sub(r"^\*This screen will display.*$", "", full_text, flags=re.MULTILINE)

    # Walk message headers in order
    headers = list(HEADER_RE.finditer(full_text))
    messages: list[ParsedMessage] = []

    for i, m in enumerate(headers):
        sender = m.group("sender").strip()
        sent_raw = m.group("sent").strip()
        action = m.group("action").strip()
        viewed_raw = m.group("viewed") or ""

        viewed: list[Viewed] = []
        for v in VIEWED_RE.finditer(viewed_raw):
            recipient = v.group("recipient").strip()
            v_ts_raw = v.group("viewed_ts").strip()
            viewed.append(Viewed(
                recipient=recipient,
                viewed_at=_parse_dt(v_ts_raw),
                raw=v.group(0),
            ))

        # Body is everything between this header end and the next header start
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(full_text)
        body_raw = full_text[body_start:body_end]
        body_excerpt = body_raw[:300]

        # Strip page footers + isolated repeat timestamps from the body
        body = _strip_page_footers(body_raw)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        # Find any 'Attachment Img.' references inside this body
        attachment_refs = []
        for a in ATTACHMENT_REF_RE.finditer(body_raw):
            attachment_refs.append({
                "filename": a.group("filename").strip(),
                "page": int(a.group("page")),
            })
        # And remove them from the body so they don't pollute the message text
        body = ATTACHMENT_REF_RE.sub("", body).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)

        messages.append(ParsedMessage(
            sender=sender,
            sent_at=_parse_dt(sent_raw),
            sent_at_raw=sent_raw,
            action=action,
            body=body,
            viewed=viewed,
            page=_page_for_offset(m.start(), page_index),
            raw_header=m.group(0),
            raw_body_excerpt=body_excerpt,
            attachment_refs=attachment_refs,
        ))

    return messages
