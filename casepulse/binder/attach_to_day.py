"""'+ Attach to this day' shortcut — creates a day-anchor personal_event
and writes one item_links row from the picked item."""

from __future__ import annotations
import json
from casepulse.binder.models import BinderCategory, PersonalEventMetadata
from casepulse.binder.repository import (
    create_binder_entry, create_item_link,
)


def _find_day_anchor(db, *, case_id: int, day: str):
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, metadata_json FROM timeline_events
               WHERE case_id=? AND date=? AND time=''
                 AND category='personal_event'""",
            (case_id, day),
        ).fetchall()
    for r in rows:
        try:
            md = json.loads(r["metadata_json"] or "{}")
        except json.JSONDecodeError:
            continue
        if md.get("is_day_anchor"):
            return r["id"]
    return None


def attach_item_to_day(
    db, *, case_id: int, day: str,
    item_type: str, item_id: int,
) -> int:
    """Attach an item to a calendar day. Reuses the day's anchor event if it
    exists; otherwise creates one. Returns the anchor's timeline_event id."""
    anchor_id = _find_day_anchor(db, case_id=case_id, day=day)
    if anchor_id is None:
        md = PersonalEventMetadata(
            location="", evidence_relevance="context", is_day_anchor=True,
        )
        anchor_id = create_binder_entry(
            db, case_id=case_id, date=day, time="",
            category=BinderCategory.PERSONAL_EVENT,
            title="Items attached to this day", summary="",
            metadata=md,
        )
    create_item_link(
        db, case_id=case_id,
        from_type=item_type, from_id=item_id,
        to_type="timeline_event", to_id=anchor_id,
        relationship="part_of",
    )
    return anchor_id
