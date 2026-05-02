"""One-shot migration: strip AppClose PDF-export boilerplate from
chat_messages bodies.

The AppClose ingest swept page footers, repeated header timestamps,
the export-summary preamble, and the bottom attachment listing into
each chat row's message_text. This script removes those patterns so
the actual conversation text reads cleanly.

Patterns stripped:
  - 'Generated: M/D/YYYY H:MM(AM|PM) Page N of M'         (page footer)
  - 'M/D/YYYY H:MM(AM|PM)' on its own line                (repeated timestamp)
  - 'AppClose Records Export Period: ... signed up on...' (preamble)
  - 'Attachment Img. <filename> to page N'                (attachment listing)
  - Lone '↪' marks (orphan thread arrows)
  - Excess blank lines

Each cleaned row's content_hash is recomputed. Idempotent — running
twice produces no changes the second time.

Usage:
    venv/bin/python -m casepulse.scripts.clean_appclose_chats --dry-run
    venv/bin/python -m casepulse.scripts.clean_appclose_chats --apply
"""
from __future__ import annotations
import argparse
import hashlib
import re
from casepulse.storage.database import Database


# Boilerplate regexes — applied per-line / per-block in this order
_PATTERNS = [
    # Page footer: "Generated: 3/26/2026 6:14AM Page 270 of 409"
    re.compile(
        r"Generated:\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?\s*"
        r"Page\s+\d+\s+of\s+\d+",
        re.IGNORECASE,
    ),
    # Export preamble: "AppClose Records Export Period: ... signed up on M/D/YYYY H:MMAM"
    re.compile(
        r"AppClose Records Export\s*"
        r"Period:[^\n]*\n*"
        r"Requested by:[^\n]*\n*"
        r"signed up on\s+\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?",
        re.IGNORECASE,
    ),
    # Attachment listing: "Attachment Img. foo.jpg to page 270"
    re.compile(
        r"Attachment\s+Img\.\s+\S[^\n]*?\s+to\s+page\s+\d+",
        re.IGNORECASE,
    ),
    # Repeated header timestamp on its own line: "9/16/2024 10:54AM"
    re.compile(
        r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)\s*$",
        re.MULTILINE,
    ),
    # Lone reply arrow on its own line
    re.compile(r"^\s*↪\s*$", re.MULTILINE),
]


_BLANK_RUNS = re.compile(r"\n{3,}")


def _clean(text: str) -> str:
    if not text:
        return text
    out = text
    for rx in _PATTERNS:
        out = rx.sub("", out)
    # Collapse runs of blank lines to a single blank line
    out = _BLANK_RUNS.sub("\n\n", out)
    return out.strip()


def _hash(timestamp: str, sender: str, message_text: str) -> str:
    return hashlib.sha256(
        f"{timestamp or ''}|{sender or ''}|{message_text or ''}".encode("utf-8")
    ).hexdigest()


def repair(db: Database, *, apply_changes: bool) -> dict:
    stats = {
        "scanned": 0,
        "would_clean": 0,
        "unchanged": 0,
    }

    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, sender, timestamp, message_text
               FROM chat_messages
               WHERE platform = 'appclose'
                  OR message_text LIKE '%Generated:%Page%of%'
                  OR message_text LIKE '%Attachment Img.%'
                  OR message_text LIKE '%AppClose Records Export%'"""
        ).fetchall()
        stats["scanned"] = len(rows)

        for r in rows:
            original = r["message_text"] or ""
            cleaned = _clean(original)
            if cleaned == original:
                stats["unchanged"] += 1
                continue
            stats["would_clean"] += 1
            if apply_changes:
                new_hash = _hash(r["timestamp"], r["sender"], cleaned)
                conn.execute(
                    "UPDATE chat_messages SET message_text=?, content_hash=? WHERE id=?",
                    (cleaned, new_hash, r["id"]),
                )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Strip AppClose PDF export boilerplate from chat_messages."
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Report what would change. No DB writes.")
    g.add_argument("--apply", action="store_true",
                   help="Apply the changes to the database.")
    args = parser.parse_args()

    db = Database()
    stats = repair(db, apply_changes=args.apply)

    print(f"Scanned: {stats['scanned']} chat_messages with possible AppClose boilerplate")
    print(f"Already clean: {stats['unchanged']}")
    print(f"Rows {'cleaned' if args.apply else 'would-clean'}: {stats['would_clean']}")
    if args.dry_run:
        print("\nDry run only. Re-run with --apply to commit changes.")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()
