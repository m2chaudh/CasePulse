"""Header-based email-thread reconstruction.

Pure parsing functions for extracting the immediate parent's Message-ID
from RFC 2822 headers. Used both by the backfill migration (rebuild
parent_email_id across the existing DB) and by the fetchers (set
parent_email_id at insert time on new mail).

Convention: this module strips angle brackets so callers compare
against `emails.message_id`, which CasePulse stores in stripped form
(see Database.email_exists / insert_email; the fetchers feed
`headers["Message-ID"]` straight through).
"""
from __future__ import annotations

import re
from typing import Optional


# Match a Message-ID inside angle brackets, allowing whitespace.
_MSGID_RE = re.compile(r"<([^<>\s]+)>")


def _normalize_msgid(raw: str) -> str:
    """Strip angle brackets + surrounding whitespace from a single Message-ID."""
    return raw.strip().strip("<>").strip()


def _header_value(headers: dict, name: str) -> Optional[str]:
    """Case-insensitive header lookup."""
    if not headers:
        return None
    target = name.lower()
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == target:
            return v
    return None


def extract_parent_message_id(headers: dict) -> Optional[str]:
    """Best parent Message-ID for the email these headers describe.

    Priority:
      1. In-Reply-To header — the immediate parent.
      2. References header — last entry is the most recent ancestor.

    Returns the Message-ID with angle brackets stripped, or None when
    no usable header is present.
    """
    if not isinstance(headers, dict):
        return None

    irt = _header_value(headers, "In-Reply-To")
    if irt:
        # In-Reply-To occasionally has multiple message-ids (non-conformant
        # mail clients) — take the LAST one as the most-recent parent.
        ids = _MSGID_RE.findall(irt)
        if ids:
            return _normalize_msgid(ids[-1])
        # Some senders omit angle brackets entirely
        cleaned = _normalize_msgid(irt)
        if cleaned:
            return cleaned

    refs = _header_value(headers, "References")
    if refs:
        ids = _MSGID_RE.findall(refs)
        if ids:
            return _normalize_msgid(ids[-1])

    return None
