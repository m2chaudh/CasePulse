"""Backfill emails.parent_email_id from RFC 2822 headers.

Resolves the In-Reply-To (or last References entry) header for each
email to a Message-ID we already store, then sets parent_email_id and
flips is_reply=1 on success. Idempotent — already-correct rows are
skipped.

Usage:
    venv/bin/python -m casepulse.scripts.backfill_email_parents --dry-run
    venv/bin/python -m casepulse.scripts.backfill_email_parents --apply

Returns stats so a UI / fetcher can surface what changed:
    {
      'total': N,            # rows scanned
      'linked': N,           # parent_email_id set this run
      'already_linked': N,   # already had correct parent
      'no_header': N,        # no In-Reply-To / References available
      'parent_missing': N,   # header points to a Message-ID not in our DB
      'self_reference': N,   # header points to email's own Message-ID
    }
"""
from __future__ import annotations

import argparse
import json

from casepulse.email_engine.threading import extract_parent_message_id
from casepulse.storage.database import Database


def backfill(db: Database, *, apply_changes: bool) -> dict:
    stats = {
        "total": 0, "linked": 0, "already_linked": 0,
        "no_header": 0, "parent_missing": 0, "self_reference": 0,
    }

    with db._get_conn() as conn:
        # message_id → emails.id map. Empty / NULL message_ids excluded
        # so they can't accidentally become a "parent".
        msg_id_map: dict[str, int] = {}
        for r in conn.execute(
            "SELECT id, message_id FROM emails "
            "WHERE message_id IS NOT NULL AND message_id != ''"
        ).fetchall():
            mid = r["message_id"].strip().strip("<>")
            if mid:
                msg_id_map[mid] = r["id"]

        rows = conn.execute(
            "SELECT id, message_id, raw_headers, parent_email_id, is_reply "
            "FROM emails"
        ).fetchall()
        stats["total"] = len(rows)

        updates: list[tuple[int, int]] = []  # (email_id, parent_email_id)

        for r in rows:
            raw = r["raw_headers"]
            if not raw:
                stats["no_header"] += 1
                continue
            try:
                headers = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                stats["no_header"] += 1
                continue

            parent_msg_id = extract_parent_message_id(headers)
            if not parent_msg_id:
                stats["no_header"] += 1
                continue

            own_msg_id = (r["message_id"] or "").strip().strip("<>")
            if parent_msg_id == own_msg_id:
                stats["self_reference"] += 1
                continue

            parent_db_id = msg_id_map.get(parent_msg_id)
            if not parent_db_id:
                stats["parent_missing"] += 1
                continue

            if r["parent_email_id"] == parent_db_id:
                stats["already_linked"] += 1
                continue

            updates.append((r["id"], parent_db_id))

        stats["linked"] = len(updates)

        if apply_changes and updates:
            conn.executemany(
                "UPDATE emails SET parent_email_id = ?, is_reply = 1 "
                "WHERE id = ?",
                [(parent_id, email_id) for email_id, parent_id in updates],
            )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill emails.parent_email_id from RFC 2822 headers."
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Report what would change. No DB writes.")
    g.add_argument("--apply", action="store_true",
                   help="Apply the linking to the database.")
    args = parser.parse_args()

    db = Database()
    stats = backfill(db, apply_changes=args.apply)
    print(f"Total emails scanned:   {stats['total']}")
    print(f"Linked this run:        {stats['linked']}")
    print(f"Already linked:         {stats['already_linked']}")
    print(f"No header / unparseable:{stats['no_header']}")
    print(f"Parent not in DB:       {stats['parent_missing']}")
    print(f"Self-reference skipped: {stats['self_reference']}")
    if args.dry_run:
        print("\nDry run only. Re-run with --apply to commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
