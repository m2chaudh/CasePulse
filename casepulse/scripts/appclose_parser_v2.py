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


# A message header — anchored to start-of-line (re.MULTILINE) so the sender
# can't bleed in from the previous message's body. Sender is 1-4 capitalised
# words; the pre-clean step below merges "Manish\nChaudhary" and "9/16/2024\n
# 2:20PM" wraps so each header sits on a single line.
HEADER_RE = re.compile(
    r"^(?P<sender>[A-Z][\w'-]*(?:[^\S\n]+[A-Z][\w'-]*){0,3})[^\S\n]+on[^\S\n]+"
    r"(?P<sent>\d{1,2}/\d{1,2}/\d{4}[^\S\n]+\d{1,2}:\d{2}[^\S\n]*[APap][Mm])[^\S\n]+"
    r"(?P<action>texted|sent[^\S\n]+attachment|sent[^\S\n]+a[^\S\n]+photo|"
    r"sent[^\S\n]+a[^\S\n]+video|sent[^\S\n]+a[^\S\n]+file|"
    r"Received[^\S\n]+permission(?:[^\S\n]+to[^\n(]*?)?)"
    r"(?P<viewed>(?:[^\S\n]*\(viewed by[^\S\n]+[^)]+\))*)"
    r"[^\S\n]*:?[^\S\n]*$",
    re.MULTILINE,
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


def _normalize_senders(messages: list["ParsedMessage"]) -> None:
    """Two-pass cleanup: figure out the small set of real participants by
    frequency, then for any message whose sender starts with extra
    body-words (e.g. 'Thanks Manish Chaudhary' from 'Thanks' bleeding
    in from the previous body), peel them off via suffix-match against
    the participant list. Mutates messages in place."""
    from collections import Counter

    # First pass: every detected sender
    counts = Counter(m.sender for m in messages if "\n" not in m.sender)
    if not counts:
        return
    # Treat any sender appearing >= 1% as a real participant
    threshold = max(2, len(messages) // 100)
    participants = sorted(
        (s for s, n in counts.items() if n >= threshold and len(s.split()) <= 3),
        key=lambda s: -counts[s],
    )
    # Second pass: normalise each message's sender to the longest matching
    # participant suffix
    for m in messages:
        # Try longest match first so "Manish Chaudhary" wins over "Chaudhary"
        matched = False
        for p in sorted(participants, key=len, reverse=True):
            if m.sender.endswith(p):
                m.sender = p
                matched = True
                break
        if matched:
            continue
        # The sender might be a name FRAGMENT (just the surname). If exactly
        # one participant ends with this fragment, use that participant.
        candidates = [p for p in participants if p.endswith(m.sender)]
        if len(candidates) == 1:
            m.sender = candidates[0]


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

    # Pre-clean step 1 — un-wrap names. PDF text extraction breaks lines mid-name
    # (e.g. the line is just "Manish" then "Chaudhary on 9/16/2024 ..."
    # on the next line). Merge ONLY when the previous line is a SINGLE
    # capitalised word (a name fragment) — re.MULTILINE anchors `^` to
    # line start so previous-message body words can't get glued in.
    full_text = re.sub(
        r"^([A-Z][\w'-]*)\n([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)?\s+on\s+\d{1,2}/\d{1,2}/\d{4})",
        r"\1 \2",
        full_text,
        flags=re.MULTILINE,
    )

    # Pre-clean step 2 — un-wrap dates. "9/16/2024\n2:20PM" → "9/16/2024 2:20PM"
    full_text = re.sub(
        r"(\d{1,2}/\d{1,2}/\d{4})\s*\n\s*(\d{1,2}:\d{2}\s*[APap][Mm])",
        r"\1 \2",
        full_text,
    )

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

    _normalize_senders(messages)
    return messages
