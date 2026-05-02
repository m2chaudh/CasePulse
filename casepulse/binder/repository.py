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


# ---------------------------------------------------------------------------
# Filter chips
# ---------------------------------------------------------------------------

def create_filter_chip(
    db: Database, *, case_id: Optional[int], label: str, emoji: str = "★",
    filter_json: dict, pinned: bool = False, sort_order: int = 0,
) -> int:
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO binder_filter_chips
                (case_id, label, emoji, filter_json, pinned, sort_order)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (case_id, label, emoji, json.dumps(filter_json),
             1 if pinned else 0, sort_order),
        )
        return cur.lastrowid


def list_filter_chips(db: Database, *, case_id: int) -> list[dict]:
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, case_id, label, emoji, filter_json, pinned, sort_order
               FROM binder_filter_chips
               WHERE case_id = ? OR case_id IS NULL
               ORDER BY pinned DESC, sort_order ASC, id ASC""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_filter_chip(db: Database, chip_id: int) -> None:
    with db._get_conn() as conn:
        conn.execute("DELETE FROM binder_filter_chips WHERE id = ?", (chip_id,))


# ---------------------------------------------------------------------------
# Case-relevant senders
# ---------------------------------------------------------------------------

def upsert_relevant_sender(
    db: Database, *, case_id: int, address: str, role: str,
    display_name: str = "", notes: str = "",
) -> int:
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO case_relevant_senders
                 (case_id, address, role, display_name, notes, active)
               VALUES (?, ?, ?, ?, ?, 1)
               ON CONFLICT(case_id, address) DO UPDATE SET
                 role = excluded.role,
                 display_name = excluded.display_name,
                 notes = excluded.notes,
                 active = 1""",
            (case_id, address.lower(), role, display_name, notes),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            "SELECT id FROM case_relevant_senders WHERE case_id=? AND address=?",
            (case_id, address.lower()),
        ).fetchone()
        return row["id"]


def list_relevant_senders(
    db: Database, *, case_id: int, active_only: bool = False,
) -> list[dict]:
    where = "case_id = ?"
    args: list = [case_id]
    if active_only:
        where += " AND active = 1"
    with db._get_conn() as conn:
        rows = conn.execute(
            f"""SELECT id, case_id, address, role, display_name, notes, active
                FROM case_relevant_senders WHERE {where} ORDER BY role, address""",
            args,
        ).fetchall()
        return [dict(r) for r in rows]


def deactivate_relevant_sender(db: Database, sender_id: int) -> None:
    with db._get_conn() as conn:
        conn.execute(
            "UPDATE case_relevant_senders SET active = 0 WHERE id = ?",
            (sender_id,),
        )


# ---------------------------------------------------------------------------
# Item links — typed user-curated relationships
# ---------------------------------------------------------------------------

def create_item_link(
    db: Database, *, case_id: int,
    from_type: str, from_id: int,
    to_type: str, to_id: int,
    relationship: str,
    note: str = "",
) -> int:
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO item_links
                (case_id, from_type, from_id, to_type, to_id, relationship, note)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (case_id, from_type, from_id, to_type, to_id, relationship, note),
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute(
            """SELECT id FROM item_links WHERE case_id=? AND
                from_type=? AND from_id=? AND to_type=? AND to_id=? AND relationship=?""",
            (case_id, from_type, from_id, to_type, to_id, relationship),
        ).fetchone()
        return row["id"]


def list_links_from(
    db: Database, *, case_id: int, from_type: str, from_id: int,
) -> list[dict]:
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, to_type, to_id, relationship, note, created_at
               FROM item_links
               WHERE case_id=? AND from_type=? AND from_id=?
               ORDER BY id""",
            (case_id, from_type, from_id),
        ).fetchall()
        return [dict(r) for r in rows]


def list_links_to(
    db: Database, *, case_id: int, to_type: str, to_id: int,
) -> list[dict]:
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, from_type, from_id, relationship, note, created_at
               FROM item_links
               WHERE case_id=? AND to_type=? AND to_id=?
               ORDER BY id""",
            (case_id, to_type, to_id),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_item_link(db: Database, link_id: int) -> None:
    with db._get_conn() as conn:
        conn.execute("DELETE FROM item_links WHERE id = ?", (link_id,))
