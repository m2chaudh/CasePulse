"""One-shot migration: split bundled WhatsApp chat_messages rows.

The original WhatsApp ingest parser concatenated multiple message headers
into a single row's body when it hit unrecognised lines (e.g. media
markers, system messages). The result: rows whose `message_text` contains
embedded WhatsApp date headers like:

    Can I see the kids please
    2024-08-19, 18:50 - Manisha:
    2024-08-21, 19:07 - Manisha:
    ...

This script extracts each embedded sub-message into its own
`chat_messages` row with the correct timestamp/sender, and trims the
parent row to contain only its actual body (the text before the first
embedded header).

Usage:
    venv/bin/python -m casepulse.scripts.repair_chat_bundles --dry-run
    venv/bin/python -m casepulse.scripts.repair_chat_bundles --apply

Idempotent — uses content_hash to skip already-inserted sub-messages.
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
from casepulse.storage.database import Database


# Match WhatsApp date headers embedded in message_text:
#   2024-08-19, 18:50 - Manisha:
WA_HEADER_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}),\s*(\d{2}:\d{2})\s*-\s*([^:\n]+?):\s*(.*)$",
    re.MULTILINE,
)


def _content_hash(timestamp: str, sender: str, message_text: str) -> str:
    return hashlib.sha256(
        f"{timestamp or ''}|{sender or ''}|{message_text or ''}".encode("utf-8")
    ).hexdigest()


def _to_iso(date_s: str, time_s: str) -> str:
    """Turn '2024-08-19' + '18:50' into '2024-08-19T18:50:00'."""
    return f"{date_s}T{time_s}:00"


def _split_bundle(text: str):
    """Return (head_body, sub_messages) where head_body is the text before
    the first embedded header, and sub_messages is a list of
    {date, time, sender, body} dicts."""
    matches = list(WA_HEADER_RE.finditer(text))
    if not matches:
        return text, []
    first = matches[0]
    head = text[: first.start()].rstrip()

    subs = []
    for i, m in enumerate(matches):
        date_s = m.group(1)
        time_s = m.group(2)
        sender = m.group(3).strip()
        # Body of this sub-message = text from end of this header line
        # to the start of the next header (or end of string)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        subs.append({
            "date": date_s,
            "time": time_s,
            "sender": sender,
            "body": body or "(media or system message)",
        })
    return head, subs


def repair(db: Database, *, apply_changes: bool = False) -> dict:
    """Scan chat_messages and split bundled rows. Returns counts."""
    stats = {
        "scanned": 0,
        "bundle_parents_found": 0,
        "sub_messages_extracted": 0,
        "sub_messages_inserted": 0,
        "sub_messages_skipped_dup": 0,
        "parents_trimmed": 0,
    }

    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, source_type, source_file, platform, chat_name,
                      sender, sender_mapped_email, timestamp, message_text,
                      has_media, media_type, content_hash, is_system,
                      import_batch
               FROM chat_messages
               WHERE message_text LIKE '%-%:%'"""
        ).fetchall()
        stats["scanned"] = len(rows)

        for r in rows:
            text = r["message_text"] or ""
            # Skip rows that THEMSELVES start with a WA header — those are
            # the user's own message rows; we only re-split rows whose body
            # contains nested headers.
            head, subs = _split_bundle(text)
            if not subs:
                continue
            stats["bundle_parents_found"] += 1
            stats["sub_messages_extracted"] += len(subs)

            for sub in subs:
                ts = _to_iso(sub["date"], sub["time"])
                ch = _content_hash(ts, sub["sender"], sub["body"])
                exists = conn.execute(
                    "SELECT 1 FROM chat_messages WHERE content_hash=? LIMIT 1",
                    (ch,),
                ).fetchone()
                if exists:
                    stats["sub_messages_skipped_dup"] += 1
                    continue
                if apply_changes:
                    conn.execute(
                        """INSERT INTO chat_messages
                            (source_type, source_file, platform, chat_name,
                             sender, sender_mapped_email, timestamp,
                             message_text, has_media, media_type,
                             content_hash, is_system, import_batch)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            r["source_type"], r["source_file"], r["platform"],
                            r["chat_name"], sub["sender"],
                            r["sender_mapped_email"], ts, sub["body"],
                            r["has_media"], r["media_type"], ch,
                            1 if "media or system" in sub["body"] else r["is_system"],
                            r["import_batch"],
                        ),
                    )
                stats["sub_messages_inserted"] += 1

            # Trim the parent row to just its head body (text before
            # the first embedded header). If apply.
            new_head = head if head else "(empty)"
            if apply_changes:
                new_hash = _content_hash(r["timestamp"], r["sender"], new_head)
                conn.execute(
                    "UPDATE chat_messages SET message_text=?, content_hash=? WHERE id=?",
                    (new_head, new_hash, r["id"]),
                )
            stats["parents_trimmed"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Split bundled WhatsApp chat_messages.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Report what would change. No DB writes.")
    g.add_argument("--apply", action="store_true",
                   help="Apply the changes to the database.")
    args = parser.parse_args()

    db = Database()
    stats = repair(db, apply_changes=args.apply)

    print(f"Scanned: {stats['scanned']} chat_messages with possible WA headers")
    print(f"Bundle parents found: {stats['bundle_parents_found']}")
    print(f"Sub-messages extracted: {stats['sub_messages_extracted']}")
    print(f"Sub-messages newly {'inserted' if args.apply else 'would-insert'}: {stats['sub_messages_inserted']}")
    print(f"Sub-messages already present (dedup'd): {stats['sub_messages_skipped_dup']}")
    print(f"Parents {'trimmed' if args.apply else 'would-trim'}: {stats['parents_trimmed']}")

    if args.dry_run:
        print("\nDry run only. Re-run with --apply to commit changes.")
    else:
        print("\nDone.")


if __name__ == "__main__":
    main()
