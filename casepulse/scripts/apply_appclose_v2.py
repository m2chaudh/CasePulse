"""One-shot migration: rewrite chat_messages from the AppClose v2 parser.

The original AppClose ingest produced rows with sender bleed
('2025 Manish Chaudhary', 'Thanks Manisha Choudhary', etc.) and missed
roughly half the conversation due to header-regex misses. The v2 parser
in `casepulse.scripts.appclose_parser_v2` correctly handles both, so
this migration replaces the v1-imported rows with v2 output for a given
source PDF.

Strategy: per source_file, DELETE all existing AppClose chat_messages
rows and INSERT fresh ones from the v2 parser. The chat_imports row is
updated to reflect the new message_count and date range. Row IDs are
not preserved (this was deliberately accepted — see resume note).

Idempotency: running twice produces the same final state. A "needs
apply?" check compares the current row set's content fingerprint against
the v2 parser output and reports `would_change=False` when in sync.

Usage:
    venv/bin/python -m casepulse.scripts.apply_appclose_v2 --dry-run
    venv/bin/python -m casepulse.scripts.apply_appclose_v2 --apply
    venv/bin/python -m casepulse.scripts.apply_appclose_v2 --apply --pdf /path/to/Conversations.pdf
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from casepulse.storage.database import Database
from casepulse.scripts.appclose_parser_v2 import (
    ParsedMessage, parse_appclose_pdf,
)


# AppClose action → (media_type, is_system) mapping
_ACTION_MEDIA_TYPE = {
    "sent a photo": "image",
    "sent a video": "video",
    "sent a file": "document",
    "sent attachment": "",
}


def _content_hash(timestamp: str, sender: str, message_text: str) -> str:
    return hashlib.sha256(
        f"{timestamp or ''}|{sender or ''}|{message_text or ''}".encode("utf-8")
    ).hexdigest()


def _row_from_parsed(m: ParsedMessage, source_file: str, batch_id: str) -> dict:
    """Convert a ParsedMessage to a chat_messages row dict."""
    ts = m.sent_at.isoformat() if m.sent_at else ""
    body = m.body if m.body else f"[{m.action}]"
    is_system = m.action.lower().startswith("received permission")
    media_type = _ACTION_MEDIA_TYPE.get(m.action.lower(), "")
    has_media = bool(media_type) or bool(m.attachment_refs)
    return {
        "source_type": "appclose",
        "source_file": source_file,
        "platform": "AppClose",
        "chat_name": "AppClose",
        "sender": m.sender,
        "sender_mapped_email": None,
        "timestamp": ts,
        "message_text": body,
        "has_media": int(has_media),
        "media_type": media_type,
        "media_path": None,
        "content_hash": _content_hash(ts, m.sender, body),
        "is_system": int(is_system),
        "import_batch": batch_id,
    }


def _existing_hashes(db: Database, source_file: str) -> set[str]:
    """Set of content_hashes for current AppClose rows from this PDF."""
    with db._get_conn() as conn:
        rows = conn.execute(
            "SELECT content_hash FROM chat_messages "
            "WHERE source_file = ? AND platform IN ('appclose', 'AppClose') "
            "  AND content_hash IS NOT NULL",
            (source_file,),
        ).fetchall()
    return {r["content_hash"] for r in rows if r["content_hash"]}


def _resolve_source_pdf(db: Database, override: Optional[str]) -> Optional[str]:
    """Pick the AppClose source PDF: explicit override, else latest from
    chat_imports."""
    if override:
        return override
    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT source_file FROM chat_imports "
            "WHERE platform IN ('appclose','AppClose') "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row["source_file"] if row else None


def apply_v2(
    db: Database,
    pdf_path: str,
    *,
    apply_changes: bool,
    parsed: Optional[list[ParsedMessage]] = None,
) -> dict:
    """Run (or dry-run) the v2-apply migration for a given PDF.

    Args:
        db: Database handle.
        pdf_path: AppClose PDF path; rows with this source_file will be
            replaced.
        apply_changes: If False, no DB writes (dry-run).
        parsed: Pre-parsed v2 messages (skip re-parsing the PDF). Used by
            the UI dry-run preview to avoid re-running pdfplumber.

    Returns a stats dict.
    """
    if parsed is None:
        if not Path(pdf_path).exists():
            return {"error": f"PDF not found: {pdf_path}"}
        parsed = parse_appclose_pdf(pdf_path)

    new_hashes = set()
    senders = {}
    actions = {}
    date_start = ""
    date_end = ""
    rows_to_insert = []

    batch_id = (
        f"appclose_v2_{Path(pdf_path).stem}_"
        f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    for m in parsed:
        row = _row_from_parsed(m, pdf_path, batch_id)
        rows_to_insert.append(row)
        new_hashes.add(row["content_hash"])
        senders[row["sender"]] = senders.get(row["sender"], 0) + 1
        actions[m.action] = actions.get(m.action, 0) + 1
        ts = row["timestamp"]
        if ts:
            if not date_start or ts < date_start:
                date_start = ts
            if not date_end or ts > date_end:
                date_end = ts

    old_hashes = _existing_hashes(db, pdf_path)
    with db._get_conn() as conn:
        old_count = conn.execute(
            "SELECT COUNT(*) AS c FROM chat_messages "
            "WHERE source_file = ? AND platform IN ('appclose','AppClose')",
            (pdf_path,),
        ).fetchone()["c"]

    in_sync = (old_hashes == new_hashes) and (old_count == len(rows_to_insert))

    stats = {
        "pdf": pdf_path,
        "old_rows": old_count,
        "new_rows": len(rows_to_insert),
        "would_change": not in_sync,
        "senders": senders,
        "actions": actions,
        "date_start": date_start,
        "date_end": date_end,
        "batch_id": batch_id,
        "applied": False,
    }

    if not apply_changes:
        return stats

    if in_sync:
        # Already up-to-date — no-op.
        stats["applied"] = True
        return stats

    with db._get_conn() as conn:
        conn.execute(
            "DELETE FROM chat_messages "
            "WHERE source_file = ? AND platform IN ('appclose','AppClose')",
            (pdf_path,),
        )
        cols = list(rows_to_insert[0].keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_list = ", ".join(cols)
        conn.executemany(
            f"INSERT INTO chat_messages ({col_list}) VALUES ({placeholders})",
            [tuple(r[c] for c in cols) for r in rows_to_insert],
        )

        # Update chat_imports row for this PDF (if present)
        existing_import = conn.execute(
            "SELECT id FROM chat_imports WHERE source_file = ? "
            "AND platform IN ('appclose','AppClose') ORDER BY id DESC LIMIT 1",
            (pdf_path,),
        ).fetchone()
        if existing_import:
            conn.execute(
                "UPDATE chat_imports SET message_count = ?, "
                "date_start = ?, date_end = ? WHERE id = ?",
                (len(rows_to_insert), date_start, date_end,
                 existing_import["id"]),
            )

    stats["applied"] = True
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite chat_messages from the AppClose v2 parser."
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Report what would change. No DB writes.")
    g.add_argument("--apply", action="store_true",
                   help="Apply the migration to the database.")
    parser.add_argument("--pdf", default=None,
                        help="AppClose PDF path. If omitted, uses the latest "
                             "AppClose source from chat_imports.")
    args = parser.parse_args()

    db = Database()
    pdf_path = _resolve_source_pdf(db, args.pdf)
    if not pdf_path:
        print("No AppClose source PDF found. Pass --pdf <path> or import one.")
        return 1
    if not Path(pdf_path).exists():
        print(f"PDF not found at {pdf_path}.")
        return 1

    print(f"PDF: {pdf_path}")
    stats = apply_v2(db, pdf_path, apply_changes=args.apply)
    if "error" in stats:
        print(stats["error"])
        return 1

    print(f"Old rows: {stats['old_rows']}")
    print(f"New rows: {stats['new_rows']}")
    print(f"Date range: {stats['date_start']} → {stats['date_end']}")
    print(f"Senders: {stats['senders']}")
    print(f"Actions: {stats['actions']}")
    if stats["would_change"]:
        print("Status: changes pending"
              + (" — APPLIED." if stats["applied"] else " (dry-run only)."))
    else:
        print("Status: already in sync (no-op).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
