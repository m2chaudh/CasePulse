"""Stateless aggregator for the Case Binder calendar."""

from __future__ import annotations
from datetime import date, datetime, time
from typing import Optional
import json
from casepulse.binder.models import AggregatedItem, ChipFilter
from casepulse.storage.database import Database

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
    # Email/chat/document/photo/attachment queries added in later tasks.
    items.sort(key=lambda it: it.when)
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
