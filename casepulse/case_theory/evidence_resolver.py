# casepulse/case_theory/evidence_resolver.py
from dataclasses import dataclass, field
from typing import Any

from casepulse.case_theory.models import Evidence
from casepulse.storage.database import Database


@dataclass
class ResolvedSource:
    kind: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None  # for attachments / documents / photos


def resolve(db: Database, e: Evidence) -> ResolvedSource:
    conn = db._get_conn()
    cur = conn.cursor()

    if e.source_table == "emails":
        cur.execute("""
            SELECT subject, body_text, sender_email, sender_name,
                   date_received, recipients, message_id, content_hash
            FROM emails WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="email",
            text=r[1] or "",
            metadata={
                "subject": r[0], "sender_email": r[2], "sender_name": r[3],
                "date": r[4], "recipients": r[5], "message_id": r[6],
                "content_hash": r[7],
            },
        )

    if e.source_table == "chat_messages":
        cur.execute("""
            SELECT message_text, sender, timestamp, chat_name, platform,
                   media_path, content_hash
            FROM chat_messages WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="chat",
            text=r[0] or "",
            metadata={
                "sender": r[1], "date": r[2], "chat_name": r[3],
                "platform": r[4], "content_hash": r[6],
            },
            file_path=r[5],
        )

    if e.source_table == "attachments":
        cur.execute("""
            SELECT filename, content_type, file_path, extracted_text,
                   content_hash, email_id
            FROM attachments WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="attachment",
            text=r[3] or "",
            metadata={
                "filename": r[0], "content_type": r[1],
                "content_hash": r[4], "email_id": r[5],
            },
            file_path=r[2],
        )

    if e.source_table == "documents":
        cur.execute("""
            SELECT filename, file_path, extracted_text, content_hash,
                   timeline_date
            FROM documents WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="document",
            text=r[2] or "",
            metadata={"filename": r[0], "content_hash": r[3],
                       "date": r[4]},
            file_path=r[1],
        )

    if e.source_table == "annotations":
        cur.execute("""
            SELECT note_text, item_type, item_id, created_at
            FROM annotations WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="annotation",
            text=r[0] or "",
            metadata={"item_type": r[1], "item_id": r[2], "date": r[3]},
        )

    raise ValueError(f"unknown source_table: {e.source_table}")
