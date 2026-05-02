"""Repository for Case Binder tables. Module-level functions following the
existing case_theory.repository pattern."""

from __future__ import annotations
import json
from typing import Optional
from pydantic import BaseModel
from casepulse.binder.models import BinderCategory
from casepulse.storage.database import Database


# ---------------------------------------------------------------------------
# Binder entries — backed by timeline_events with binder categories
# ---------------------------------------------------------------------------

def create_binder_entry(
    db: Database, *, case_id: int, date: str, time: str,
    category: BinderCategory, title: str, summary: str,
    metadata: BaseModel,
) -> int:
    payload = json.dumps(metadata.model_dump(mode="json"))
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO timeline_events
                (date, time, category, description, notes, case_id, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (date, time, category.value, title, summary, case_id, payload),
        )
        entry_id = cur.lastrowid
        conn.execute(
            """INSERT OR IGNORE INTO evidence_tags (item_type, item_id, case_id)
               VALUES (?, ?, ?)""",
            ("timeline_event", entry_id, case_id),
        )
        return entry_id


def get_binder_entry(db: Database, entry_id: int) -> Optional[dict]:
    with db._get_conn() as conn:
        row = conn.execute(
            """SELECT id, case_id, date, time, category,
                      description AS title, notes AS summary, metadata_json
               FROM timeline_events WHERE id = ?""",
            (entry_id,),
        ).fetchone()
        return dict(row) if row else None


def list_binder_entries_for_day(
    db: Database, *, case_id: int, date: str,
) -> list[dict]:
    binder_cats = (
        BinderCategory.COURT_APPEARANCE.value,
        BinderCategory.DISCLOSURE.value,
        BinderCategory.COUNSEL_CORRESPONDENCE.value,
        BinderCategory.PERSONAL_EVENT.value,
    )
    with db._get_conn() as conn:
        rows = conn.execute(
            f"""SELECT id, case_id, date, time, category,
                       description AS title, notes AS summary, metadata_json
                FROM timeline_events
                WHERE case_id = ? AND date = ?
                  AND category IN ({','.join('?' for _ in binder_cats)})
                ORDER BY time ASC, id ASC""",
            (case_id, date, *binder_cats),
        ).fetchall()
        return [dict(r) for r in rows]


def update_binder_entry(
    db: Database, entry_id: int, *,
    title: Optional[str] = None,
    summary: Optional[str] = None,
    time: Optional[str] = None,
    metadata: Optional[BaseModel] = None,
) -> None:
    sets: list[str] = []
    args: list = []
    if title is not None:
        sets.append("description = ?")
        args.append(title)
    if summary is not None:
        sets.append("notes = ?")
        args.append(summary)
    if time is not None:
        sets.append("time = ?")
        args.append(time)
    if metadata is not None:
        sets.append("metadata_json = ?")
        args.append(json.dumps(metadata.model_dump(mode="json")))
    if not sets:
        return
    args.append(entry_id)
    with db._get_conn() as conn:
        conn.execute(
            f"UPDATE timeline_events SET {', '.join(sets)} WHERE id = ?", args,
        )


def delete_binder_entry(db: Database, entry_id: int) -> None:
    with db._get_conn() as conn:
        conn.execute("DELETE FROM timeline_events WHERE id = ?", (entry_id,))
        conn.execute(
            "DELETE FROM evidence_tags WHERE item_type='timeline_event' AND item_id=?",
            (entry_id,),
        )
