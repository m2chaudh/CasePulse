"""Stateless aggregator for the Case Binder calendar."""

from __future__ import annotations
from datetime import date, datetime, time
from typing import Optional
import json
from casepulse.binder.models import AggregatedItem, ChipFilter
from casepulse.storage.database import Database


def _format_recipients_inline(raw, *, limit: int = 4) -> str:
    """Turn a recipients/cc JSON string into 'Alice, Bob, +2 more'."""
    if not raw:
        return ""
    try:
        people = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw)[:80]
    if not isinstance(people, list):
        return str(raw)[:80]
    names = []
    for p in people:
        if not isinstance(p, dict):
            continue
        name = (p.get("name") or "").strip()
        email = (p.get("email") or "").strip()
        names.append(name or email)
    if not names:
        return ""
    if len(names) <= limit:
        return ", ".join(names)
    return ", ".join(names[:limit]) + f", +{len(names) - limit} more"

BINDER_CATEGORIES = (
    "court_appearance", "disclosure",
    "counsel_correspondence", "personal_event",
)


def aggregate(
    db: Database, *,
    case_id: int,
    date_start: date,
    date_end: date,
    chip_filter: Optional[ChipFilter] = None,
) -> list[AggregatedItem]:
    items: list[AggregatedItem] = []
    items.extend(_query_timeline_events(db, case_id, date_start, date_end))
    items.extend(_query_emails(db, case_id, date_start, date_end))
    items.extend(_query_chats(db, case_id, date_start, date_end))
    items.extend(_query_documents(db, case_id, date_start, date_end))
    items.extend(_query_attachments(db, case_id, date_start, date_end))
    items.extend(_query_photos(db, case_id, date_start, date_end))
    items.extend(_query_attached_via_links(db, case_id, date_start, date_end))
    if chip_filter is not None and chip_filter.categories:
        wanted = set(chip_filter.categories)
        items = [it for it in items if it.category in wanted]
    items.sort(key=lambda it: it.when)
    _populate_cross_refs(db, case_id, items)
    return items


def _query_timeline_events(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, date, time, category, description AS title,
                      notes AS summary, metadata_json
               FROM timeline_events
               WHERE case_id=? AND date BETWEEN ? AND ?
               ORDER BY date, time, id""",
            (case_id, ds.isoformat(), de.isoformat()),
        ).fetchall()
    for r in rows:
        when = _combine(r["date"], r["time"])
        out.append(AggregatedItem(
            when=when,
            source="timeline_event",
            source_id=r["id"],
            category=r["category"],
            title=r["title"] or "",
            summary=r["summary"] or "",
            metadata=json.loads(r["metadata_json"] or "{}"),
        ))
    return out


def _combine(date_str: str, time_str: str) -> datetime:
    """Combine a YYYY-MM-DD date string and an optional HH:MM time string
    into a datetime. Empty time → midnight."""
    d = date.fromisoformat(date_str)
    if time_str:
        try:
            hh, mm = time_str.split(":")[:2]
            return datetime.combine(d, time(int(hh), int(mm)))
        except (ValueError, TypeError):
            pass
    return datetime.combine(d, time(0, 0))


def _query_emails(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    """Emails on the calendar — show everything except items the user has
    explicitly tagged to a *different* case. So untagged items + items
    tagged to this case both show; cases the user actively buckets stay
    isolated. This matches the auto-aggregation expectation."""
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT e.id, e.subject, e.sender_email, e.sender_name,
                      e.recipients, e.date_received, e.date_sent,
                      e.has_attachments
               FROM emails e
               WHERE COALESCE(e.date_received, e.date_sent, '') BETWEEN ? AND ?
                 AND e.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='email' AND case_id != ?
                 )
               ORDER BY e.date_received""",
            (f"{ds.isoformat()}T00:00:00", f"{de.isoformat()}T23:59:59", case_id),
        ).fetchall()
    for r in rows:
        when = _parse_dt(r["date_received"] or r["date_sent"] or "")
        if when is None:
            continue
        sender = r["sender_name"] or r["sender_email"] or ""
        title = f"{sender} · {r['subject'] or '(no subject)'}"
        recipients = _format_recipients_inline(r["recipients"])
        summary = f"to {recipients}" if recipients else ""
        out.append(AggregatedItem(
            when=when,
            source="email",
            source_id=r["id"],
            category="email",
            title=title,
            summary=summary,
            metadata={"sender_email": r["sender_email"]},
            has_attachment=bool(r["has_attachments"]),
        ))
    return out


def _parse_dt(s: str):
    """Parse our common ISO-ish datetime formats. Return None on failure.

    Handles UTC suffix 'Z', explicit timezone offsets, microseconds, and
    plain date-only strings. Always returns a NAIVE datetime (tz stripped)
    because the rest of the codebase compares naive datetimes."""
    if not s:
        return None
    s = s.strip()
    # Python 3.11+ datetime.fromisoformat handles Z, +offsets, microseconds, etc.
    # Pre-3.11 versions need Z replaced with +00:00.
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00") if s.endswith("Z") else s)
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _query_chats(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.platform, c.chat_name, c.sender, c.timestamp,
                      c.message_text, c.has_media, c.media_type
               FROM chat_messages c
               WHERE c.timestamp BETWEEN ? AND ?
                 AND c.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='chat' AND case_id != ?
                 )
               ORDER BY c.timestamp""",
            (f"{ds.isoformat()}T00:00:00", f"{de.isoformat()}T23:59:59", case_id),
        ).fetchall()
    for r in rows:
        when = _parse_dt(r["timestamp"] or "")
        if when is None:
            continue
        platform = r["platform"] or "chat"
        sender = r["sender"] or "?"
        text = (r["message_text"] or "").strip()
        # Day drawer renders this as a bubble cluster — keep the FULL text
        # (no truncation) plus platform/sender/chat_name in metadata.
        out.append(AggregatedItem(
            when=when,
            source="chat",
            source_id=r["id"],
            category="chat",
            title=f"{platform} / {sender}",
            summary=text,
            metadata={
                "chat_name": r["chat_name"] or "",
                "platform": platform,
                "sender": sender,
                "has_media": bool(r["has_media"]),
                "media_type": r["media_type"] or "",
            },
            has_attachment=bool(r["has_media"]),
        ))
    return out


def _query_documents(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT d.id, d.filename, d.created_at, d.content_hash
               FROM documents d
               WHERE COALESCE(d.created_at, '') BETWEEN ? AND ?
                 AND d.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='document' AND case_id != ?
                 )
               ORDER BY d.created_at""",
            (f"{ds.isoformat()}T00:00:00", f"{de.isoformat()}T23:59:59", case_id),
        ).fetchall()
    for r in rows:
        when = _parse_dt(r["created_at"] or "")
        if when is None:
            continue
        out.append(AggregatedItem(
            when=when, source="document", source_id=r["id"],
            category="document", title=r["filename"] or "(unnamed)",
            summary="", metadata={"content_hash": r["content_hash"] or ""},
        ))
    return out


def _query_attachments(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT a.id, a.filename, a.created_at, a.email_id
               FROM attachments a
               WHERE COALESCE(a.created_at, '') BETWEEN ? AND ?
                 AND a.id NOT IN (
                   SELECT item_id FROM evidence_tags
                    WHERE item_type='attachment' AND case_id != ?
                 )
               ORDER BY a.created_at""",
            (f"{ds.isoformat()}T00:00:00", f"{de.isoformat()}T23:59:59", case_id),
        ).fetchall()
    for r in rows:
        when = _parse_dt(r["created_at"] or "")
        if when is None:
            continue
        out.append(AggregatedItem(
            when=when, source="attachment", source_id=r["id"],
            category="attachment", title=r["filename"] or "(unnamed)",
            summary="", metadata={"email_id": r["email_id"]},
        ))
    return out


def _query_photos(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    """Photos pulled from photo_metadata when their taken_at falls in
    the window. Excluded only if the source row is explicitly tagged to
    a *different* case. NOTE: schema uses source_row_id (not source_id)
    and taken_at (not captured_at)."""
    out: list[AggregatedItem] = []
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT pm.id, pm.source_table, pm.source_row_id,
                       pm.taken_at
                FROM photo_metadata pm
                WHERE COALESCE(pm.taken_at, '') BETWEEN ? AND ?
                  AND NOT EXISTS (
                    SELECT 1 FROM evidence_tags t
                     WHERE t.item_type = pm.source_table
                       AND t.item_id = pm.source_row_id
                       AND t.case_id != ?
                  )
                ORDER BY pm.taken_at""",
            (f"{ds.isoformat()}T00:00:00", f"{de.isoformat()}T23:59:59", case_id),
        ).fetchall()
    for r in rows:
        when = _parse_dt(r["taken_at"] or "")
        if when is None:
            continue
        out.append(AggregatedItem(
            when=when, source="photo", source_id=r["id"],
            category="photo", title="(photo)", summary="",
            metadata={"source_table": r["source_table"],
                      "source_id": r["source_row_id"]},
        ))
    return out


def _populate_cross_refs(
    db: Database, case_id: int, items: list[AggregatedItem],
) -> None:
    if not items:
        return
    from casepulse.binder.models import CrossRef
    by_key: dict[tuple[str, int], list] = {(it.source, it.source_id): [] for it in items}

    with db._get_conn() as conn:
        # Outgoing item_links — one query per from_type for clarity.
        for ft in {it.source for it in items}:
            ids = [it.source_id for it in items if it.source == ft]
            if not ids:
                continue
            placeholders = ",".join("?" for _ in ids)
            rows = conn.execute(
                f"""SELECT from_type, from_id, to_type, to_id, relationship
                    FROM item_links
                    WHERE case_id=? AND from_type=? AND from_id IN ({placeholders})""",
                (case_id, ft, *ids),
            ).fetchall()
            for r in rows:
                key = (r["from_type"], r["from_id"])
                if key in by_key:
                    by_key[key].append(CrossRef(
                        target_type=r["to_type"], target_id=r["to_id"],
                        relationship=r["relationship"],
                    ))

        # argument_evidence rows. The actual schema uses evidence_id that
        # references the evidence table, which holds source_table/source_row_id.
        # Map each AggregatedItem.source to its db table name.
        source_map = {
            "email": "emails",
            "chat": "chat_messages",
            "document": "documents",
            "attachment": "attachments",
            "photo": "photo_metadata",
            "timeline_event": "timeline_events",
        }
        for it in items:
            db_table = source_map.get(it.source)
            if not db_table:
                continue
            rows = conn.execute(
                """SELECT ae.argument_id, ae.role
                   FROM argument_evidence ae
                   JOIN evidence ev ON ev.id = ae.evidence_id
                   WHERE ev.source_table = ? AND ev.source_row_id = ?""",
                (db_table, it.source_id),
            ).fetchall()
            for r in rows:
                by_key[(it.source, it.source_id)].append(CrossRef(
                    target_type="argument", target_id=r["argument_id"],
                    relationship=r["role"] or "supports",
                ))

    for it in items:
        it.cross_refs = by_key[(it.source, it.source_id)]


def _query_attached_via_links(
    db: Database, case_id: int, ds: date, de: date,
) -> list[AggregatedItem]:
    """Items linked via item_links (relationship='part_of') TO any
    timeline_event in [ds, de]. They render on the anchor's date even
    when their natural date differs — this is what makes the
    '+ Attach to this day' shortcut visible on the calendar."""
    out: list[AggregatedItem] = []
    ds_iso, de_iso = ds.isoformat(), de.isoformat()
    with db._get_conn() as conn:
        # Emails attached to a day-anchor or any timeline_event in range
        rows = conn.execute(
            """SELECT e.id, e.subject, e.sender_email, e.sender_name, e.recipients,
                      e.has_attachments,
                      te.date AS anchor_date, te.time AS anchor_time
               FROM item_links il
               JOIN timeline_events te ON te.id = il.to_id AND il.to_type = 'timeline_event'
               JOIN emails e ON e.id = il.from_id
               WHERE il.case_id = ? AND il.relationship = 'part_of'
                 AND il.from_type = 'email'
                 AND te.date BETWEEN ? AND ?""",
            (case_id, ds_iso, de_iso),
        ).fetchall()
        for r in rows:
            when = _combine(r["anchor_date"], r["anchor_time"])
            sender = r["sender_name"] or r["sender_email"] or ""
            title = f"{sender} · {r['subject'] or '(no subject)'}"
            recipients = _format_recipients_inline(r["recipients"])
            base = f"to {recipients}" if recipients else ""
            summary = f"(attached to this day) {base}".strip()
            out.append(AggregatedItem(
                when=when, source="email", source_id=r["id"],
                category="email", title=title,
                summary=summary,
                metadata={"sender_email": r["sender_email"], "attached": True},
                has_attachment=bool(r["has_attachments"]),
            ))

        # Chats
        rows = conn.execute(
            """SELECT c.id, c.platform, c.chat_name, c.sender, c.message_text,
                      c.has_media,
                      te.date AS anchor_date, te.time AS anchor_time
               FROM item_links il
               JOIN timeline_events te ON te.id = il.to_id AND il.to_type = 'timeline_event'
               JOIN chat_messages c ON c.id = il.from_id
               WHERE il.case_id = ? AND il.relationship = 'part_of'
                 AND il.from_type = 'chat'
                 AND te.date BETWEEN ? AND ?""",
            (case_id, ds_iso, de_iso),
        ).fetchall()
        for r in rows:
            when = _combine(r["anchor_date"], r["anchor_time"])
            text = (r["message_text"] or "").strip().replace("\n", " ")
            if len(text) > 140:
                text = text[:137] + "…"
            out.append(AggregatedItem(
                when=when, source="chat", source_id=r["id"],
                category="chat",
                title=f"{r['platform'] or 'chat'} / {r['sender'] or '?'}",
                summary=f"(attached to this day) {text}",
                metadata={"chat_name": r["chat_name"] or "", "attached": True},
                has_attachment=bool(r["has_media"]),
            ))

        # Documents
        rows = conn.execute(
            """SELECT d.id, d.filename, d.content_hash,
                      te.date AS anchor_date, te.time AS anchor_time
               FROM item_links il
               JOIN timeline_events te ON te.id = il.to_id AND il.to_type = 'timeline_event'
               JOIN documents d ON d.id = il.from_id
               WHERE il.case_id = ? AND il.relationship = 'part_of'
                 AND il.from_type = 'document'
                 AND te.date BETWEEN ? AND ?""",
            (case_id, ds_iso, de_iso),
        ).fetchall()
        for r in rows:
            when = _combine(r["anchor_date"], r["anchor_time"])
            out.append(AggregatedItem(
                when=when, source="document", source_id=r["id"],
                category="document", title=r["filename"] or "(unnamed)",
                summary="(attached to this day)",
                metadata={"content_hash": r["content_hash"] or "", "attached": True},
            ))

        # Attachments
        rows = conn.execute(
            """SELECT a.id, a.filename, a.email_id,
                      te.date AS anchor_date, te.time AS anchor_time
               FROM item_links il
               JOIN timeline_events te ON te.id = il.to_id AND il.to_type = 'timeline_event'
               JOIN attachments a ON a.id = il.from_id
               WHERE il.case_id = ? AND il.relationship = 'part_of'
                 AND il.from_type = 'attachment'
                 AND te.date BETWEEN ? AND ?""",
            (case_id, ds_iso, de_iso),
        ).fetchall()
        for r in rows:
            when = _combine(r["anchor_date"], r["anchor_time"])
            out.append(AggregatedItem(
                when=when, source="attachment", source_id=r["id"],
                category="attachment", title=r["filename"] or "(unnamed)",
                summary="(attached to this day)",
                metadata={"email_id": r["email_id"], "attached": True},
            ))

        # Photos
        rows = conn.execute(
            """SELECT pm.id, pm.source_table, pm.source_row_id, pm.taken_at,
                      te.date AS anchor_date, te.time AS anchor_time
               FROM item_links il
               JOIN timeline_events te ON te.id = il.to_id AND il.to_type = 'timeline_event'
               JOIN photo_metadata pm ON pm.id = il.from_id
               WHERE il.case_id = ? AND il.relationship = 'part_of'
                 AND il.from_type = 'photo'
                 AND te.date BETWEEN ? AND ?""",
            (case_id, ds_iso, de_iso),
        ).fetchall()
        for r in rows:
            when = _combine(r["anchor_date"], r["anchor_time"])
            out.append(AggregatedItem(
                when=when, source="photo", source_id=r["id"],
                category="photo", title="(photo)",
                summary="(attached to this day)",
                metadata={"source_table": r["source_table"],
                          "source_id": r["source_row_id"], "attached": True},
            ))
    return out
