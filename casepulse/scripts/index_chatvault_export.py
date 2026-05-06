"""Index a ChatVault export's `msg-N` anchors against `chat_messages`.

Reads `<source_dir>/index.html`, extracts each `<div class="message"
id="msg-N">` with its sender, timestamp, and body, then matches those
records against `chat_messages` rows for the same platform. Writes
match results into `chatvault_anchors`.

Matching key (in priority order):
  1. (timestamp_minute, sender, body_first_60_chars) — exact
  2. (timestamp_minute, sender) positional — used ONLY when the
     chat_messages body is empty or a placeholder like '[sent a photo]'.
     Stops false-positive anchors when bodies disagree on real text.

Idempotent — re-runs INSERT OR REPLACE the same anchor rows. Stale
anchors (from chat_messages rows that no longer exist or moved
content) are pruned at the end of each run.

Usage:
    venv/bin/python -m casepulse.scripts.index_chatvault_export <export_id>
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag

from casepulse.storage.database import Database
from casepulse.chatvault_integration import (
    get_export, set_indexed,
)


# How many characters of the body we use as part of the match fingerprint.
BODY_PREFIX_LEN = 60


def _norm_body(text: str) -> str:
    """Normalise a message body for fingerprint matching."""
    if not text:
        return ""
    # Collapse whitespace; lowercase; first BODY_PREFIX_LEN chars.
    s = re.sub(r"\s+", " ", text).strip().lower()
    return s[:BODY_PREFIX_LEN]


def _to_minute(ts) -> str:
    """Truncate a timestamp to 'YYYY-MM-DDTHH:MM' for matching.

    Accepts ISO strings, datetime objects, or empty values.
    """
    if not ts:
        return ""
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%dT%H:%M")
    s = str(ts).strip()
    # Already truncate to first 16 chars if it looks like an ISO string.
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", s):
        return s.replace(" ", "T")[:16]
    return s


def parse_chatvault_index(html_path: Path) -> list[dict]:
    """Extract anchor records from a ChatVault index.html.

    Returns [{anchor_id, sender, time, date, body, body_norm}, ...] in
    document order. `time` and `date` are raw strings — combine them at
    match time.
    """
    soup = BeautifulSoup(
        html_path.read_text(encoding="utf-8", errors="replace"), "lxml"
    )

    records: list[dict] = []
    current_date: Optional[str] = None

    # Walk the chat container; track date separators as we encounter them.
    chat_container = (
        soup.find(class_="chat")
        or soup.find(class_="messages")
        or soup.find("main")
        or soup.body
    )
    if not chat_container:
        return records

    for el in chat_container.descendants:
        if not isinstance(el, Tag):
            continue
        classes = el.get("class") or []

        # Date separator
        if any(c in classes for c in (
            "date-separator", "date-badge", "date-header", "date",
        )):
            txt = el.get_text(" ", strip=True)
            current_date = _parse_date_text(txt)
            continue

        # Message bubble: identified by id="msg-N"
        elem_id = el.get("id") or ""
        if not elem_id.startswith("msg-"):
            continue
        if "message" not in classes:
            # Some templates put the id on an inner div; check parent.
            parent_classes = (
                el.parent.get("class") or [] if el.parent else []
            )
            if "message" not in parent_classes:
                continue

        is_system = "system" in classes

        # Sender: usually in .sender-name (ChatVault) or .msg-sender (older)
        sender = ""
        sender_el = el.find(class_="sender-name") or el.find(class_="msg-sender")
        if sender_el:
            sender = sender_el.get_text(" ", strip=True)

        # Body text: prefer .msg-text; fall back to whole bubble text
        text = ""
        text_el = el.find(class_="msg-text") or el.find(class_="text")
        if text_el:
            text = text_el.get_text(" ", strip=True)
        else:
            # Strip sender + meta to leave the body
            full = el.get_text(" ", strip=True)
            if sender and full.startswith(sender):
                full = full[len(sender):].strip()
            text = full

        # Time: meta block at the bottom of the bubble (ChatVault renders
        # it via render_footer — first time-like token is the message time)
        meta = el.find(class_="meta") or el.find(class_="msg-time")
        time_str = ""
        if meta:
            mt = meta.get_text(" ", strip=True)
            tm = re.search(
                r"\b(\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp]\.?[Mm]\.?)?)",
                mt,
            )
            if tm:
                time_str = tm.group(1)

        records.append({
            "anchor_id": elem_id,
            "sender": sender,
            "date": current_date or "",
            "time": time_str,
            "body": text,
            "body_norm": _norm_body(text),
            "is_system": is_system,
        })
    return records


_DATE_FORMATS = [
    "%B %d, %Y",
    "%b %d, %Y",
    "%A, %B %d, %Y",
    "%a, %b %d, %Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
]


def _parse_date_text(text: str) -> Optional[str]:
    """Parse a date-separator string to 'YYYY-MM-DD' or None."""
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def _combine_minute(date_iso: str, time_str: str) -> str:
    """Combine a YYYY-MM-DD + 'H:MM AM' style time into 'YYYY-MM-DDTHH:MM'."""
    if not date_iso:
        return ""
    if not time_str:
        return date_iso
    s = time_str.strip().upper().replace(".", "")
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt)
            return f"{date_iso}T{t.hour:02d}:{t.minute:02d}"
        except ValueError:
            continue
    return date_iso


def index_export(db: Database, export_id: int) -> dict:
    """Index a registered export. Returns stats."""
    export = get_export(db, export_id)
    if not export:
        return {"error": f"export {export_id} not found"}
    src = Path(export["source_dir"])
    idx_path = src / "index.html"
    if not idx_path.exists():
        return {"error": f"no index.html at {idx_path}"}

    records = parse_chatvault_index(idx_path)
    platform = (export["platform"] or "").lower()

    # Build CV index: (minute_iso, sender, body_norm) → list[anchor_id] in order
    cv_by_key: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    cv_by_lax: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for r in records:
        minute = _combine_minute(r["date"], r["time"])
        cv_by_key[(minute, r["sender"], r["body_norm"])].append(r["anchor_id"])
        cv_by_lax[(minute, r["sender"])].append((r["anchor_id"], r["body_norm"]))

    # Pull candidate chat_messages rows for the same platform, in id order
    with db._get_conn() as conn:
        plat_filter = (
            "platform IN ('appclose','AppClose')" if platform == "appclose"
            else "platform IN ('whatsapp','WhatsApp')" if platform == "whatsapp"
            else "1=1"
        )
        cm_rows = conn.execute(
            f"""SELECT id, sender, timestamp, message_text
                FROM chat_messages WHERE {plat_filter}
                ORDER BY timestamp ASC, id ASC"""
        ).fetchall()

    # Track usage so duplicates pair off positionally
    used_exact: dict[tuple[str, str, str], int] = defaultdict(int)
    used_lax: dict[tuple[str, str], int] = defaultdict(int)

    matches: list[tuple[int, str]] = []   # (chat_message_id, anchor_id)
    unmatched_cm = 0

    for r in cm_rows:
        minute = _to_minute(r["timestamp"])
        sender = r["sender"] or ""
        body_norm = _norm_body(r["message_text"] or "")

        # Try exact body match first
        key = (minute, sender, body_norm)
        candidates = cv_by_key.get(key)
        if candidates:
            i = used_exact[key]
            if i < len(candidates):
                matches.append((r["id"], candidates[i]))
                used_exact[key] += 1
                # Also consume in lax bucket so positional fallback stays in sync
                used_lax[(minute, sender)] += 1
                continue

        # Lax fallback by (minute, sender), pair positionally. Only used
        # when this chat_messages body is empty or an action placeholder
        # ('[sent a photo]', '[sent attachment]', etc.) — the case where
        # ChatVault renders a media bubble with no text. For real text
        # bodies, a mismatch means we should NOT anchor blindly.
        body_text = (r["message_text"] or "").strip()
        is_placeholder = (
            not body_text
            or (body_text.startswith("[") and body_text.endswith("]"))
        )
        if is_placeholder:
            lax_candidates = cv_by_lax.get((minute, sender))
            if lax_candidates:
                i = used_lax[(minute, sender)]
                if i < len(lax_candidates):
                    matches.append((r["id"], lax_candidates[i][0]))
                    used_lax[(minute, sender)] += 1
                    continue

        unmatched_cm += 1

    matched_anchor_ids = {a for _, a in matches}
    unmatched_cv = sum(
        1 for r in records if r["anchor_id"] not in matched_anchor_ids
    )

    # Persist: replace anchors for THIS export only (idempotent; stale rows
    # whose underlying chat_messages content drifted get pruned).
    with db._get_conn() as conn:
        conn.execute(
            "DELETE FROM chatvault_anchors WHERE export_id = ?", (export_id,)
        )
        if matches:
            conn.executemany(
                "INSERT INTO chatvault_anchors "
                "(chat_message_id, export_id, anchor_id) VALUES (?, ?, ?)",
                [(cm_id, export_id, anchor) for cm_id, anchor in matches],
            )

    set_indexed(db, export_id, len(records))

    return {
        "export_id": export_id,
        "cv_messages": len(records),
        "cm_rows_scanned": len(cm_rows),
        "matched": len(matches),
        "unmatched_cv": unmatched_cv,
        "unmatched_cm": unmatched_cm,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Index a ChatVault export's anchors against chat_messages."
    )
    parser.add_argument("export_id", type=int,
                        help="chatvault_exports.id to index.")
    args = parser.parse_args()

    db = Database()
    stats = index_export(db, args.export_id)
    if "error" in stats:
        print(stats["error"])
        return 1
    print(f"ChatVault messages parsed: {stats['cv_messages']}")
    print(f"chat_messages scanned:    {stats['cm_rows_scanned']}")
    print(f"Anchors written:          {stats['matched']}")
    print(f"Unmatched in ChatVault:   {stats['unmatched_cv']}")
    print(f"Unmatched in chat_messages: {stats['unmatched_cm']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
