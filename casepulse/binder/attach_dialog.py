"""Attach to this day — Streamlit dialog that pairs an existing item
(document / email / attachment / chat / photo / witness) with a calendar
day, via a day-anchor personal_event + an item_links row."""

from __future__ import annotations
from typing import Iterable
import streamlit as st
from casepulse.binder.attach_to_day import attach_item_to_day


def _list_for_type(db, *, case_id: int, item_type: str) -> list[dict]:
    """Return [{id, label}] for items of `item_type` scoped to the case."""
    sql_map = {
        "document": (
            """SELECT d.id AS id, d.filename AS label
               FROM documents d
               JOIN evidence_tags t ON t.item_type='document' AND t.item_id=d.id
               WHERE t.case_id=? ORDER BY d.created_at DESC LIMIT 200""",
        ),
        "email": (
            """SELECT e.id AS id,
                      COALESCE(e.subject, '(no subject)') || ' · ' ||
                      COALESCE(e.sender_email, '?') AS label
               FROM emails e
               JOIN evidence_tags t ON t.item_type='email' AND t.item_id=e.id
               WHERE t.case_id=? ORDER BY e.date_received DESC LIMIT 200""",
        ),
        "attachment": (
            """SELECT a.id AS id, a.filename AS label
               FROM attachments a
               JOIN evidence_tags t ON t.item_type='attachment' AND t.item_id=a.id
               WHERE t.case_id=? ORDER BY a.created_at DESC LIMIT 200""",
        ),
        "chat": (
            """SELECT c.id AS id,
                      COALESCE(c.platform, 'chat') || ' / ' ||
                      COALESCE(c.sender, '?') || ' · ' ||
                      substr(COALESCE(c.message_text, ''), 1, 60) AS label
               FROM chat_messages c
               JOIN evidence_tags t ON t.item_type='chat' AND t.item_id=c.id
               WHERE t.case_id=? ORDER BY c.timestamp DESC LIMIT 200""",
        ),
        "photo": (
            """SELECT pm.id AS id,
                      COALESCE(pm.taken_at, 'unknown date') AS label
               FROM photo_metadata pm
               JOIN evidence_tags t
                 ON t.item_type=pm.source_table AND t.item_id=pm.source_row_id
               WHERE t.case_id=? ORDER BY pm.taken_at DESC LIMIT 200""",
        ),
        "witness": (
            """SELECT w.id AS id, w.name AS label
               FROM witnesses w WHERE w.case_id=? ORDER BY w.name LIMIT 200""",
        ),
    }
    if item_type not in sql_map:
        return []
    sql, = sql_map[item_type]
    with db._get_conn() as conn:
        rows = conn.execute(sql, (case_id,)).fetchall()
    return [{"id": r["id"], "label": r["label"] or f"#{r['id']}"} for r in rows]


@st.dialog("Attach to this day")
def open_attach_dialog(db, *, case_id: int, day: str) -> None:
    """Pick an existing item (any type) to link to this calendar day.
    Creates a day-anchor personal_event if one doesn't exist and writes
    one item_links row with relationship='part_of'."""
    st.caption(
        f"Linking an item to **{day}**. The item keeps its own date — "
        "you're saying it's *also* relevant to this day."
    )

    item_type = st.radio(
        "Item type",
        ["document", "email", "attachment", "chat", "photo", "witness"],
        horizontal=True,
        key="attach_dialog_type",
    )

    items = _list_for_type(db, case_id=case_id, item_type=item_type)
    if not items:
        st.info(f"No {item_type}s in this case yet.")
        return

    # Show as a selectbox with a label preview
    options = {f"#{r['id']} · {r['label']}": r["id"] for r in items}
    chosen_label = st.selectbox(f"Pick a {item_type}", list(options.keys()),
                                 key="attach_dialog_pick")
    chosen_id = options[chosen_label]

    cols = st.columns([1, 1, 4])
    with cols[0]:
        if st.button("Attach", type="primary", key="attach_dialog_save"):
            attach_item_to_day(
                db, case_id=case_id, day=day,
                item_type=item_type, item_id=chosen_id,
            )
            st.success(f"Attached {item_type} #{chosen_id} to {day}")
            st.rerun()
    with cols[1]:
        if st.button("Cancel", key="attach_dialog_cancel"):
            st.rerun()
