"""Open dialog — shows the content of an aggregated item by source type.

Reuses casepulse.case_theory.ui.email_renderer for emails (preserves the
nice pre-wrap + thread-collapse rendering); plain text otherwise.
"""
from __future__ import annotations
import streamlit as st


def _fetch_email(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, subject, sender_email, sender_name, recipients,
                      cc, date_received, date_sent, body_text, body_html,
                      has_attachments
               FROM emails WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_chat(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, platform, chat_name, sender, timestamp,
                      message_text, has_media, media_type, media_path
               FROM chat_messages WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_document(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, filename, file_path, content_hash, created_at
               FROM documents WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_attachment(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, email_id, filename, content_type, size_bytes,
                      file_path, created_at, is_duplicate
               FROM attachments WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_photo(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, source_table, source_row_id, taken_at,
                      camera_make, camera_model, gps_lat, gps_lon,
                      width, height, exif_present
               FROM photo_metadata WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_timeline_event(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, date, time, category, description, notes,
                      source_type, source_id, metadata_json, case_id
               FROM timeline_events WHERE id = ?""",
            (source_id,),
        ).fetchone()


@st.dialog("Item details")
def open_item_dialog(db, *, source: str, source_id: int):
    """Show the content of an item. Read-only viewer."""
    if source == "email":
        row = _fetch_email(db, source_id)
        if not row:
            st.error(f"Email #{source_id} not found")
            return
        st.markdown(f"### {row['subject'] or '(no subject)'}")
        st.caption(
            f"From **{row['sender_name'] or row['sender_email']}** "
            f"({row['sender_email']}) · "
            f"{row['date_received'] or row['date_sent'] or '?'}"
        )
        if row["recipients"]:
            st.caption(f"To: {row['recipients']}")
        if row["cc"]:
            st.caption(f"Cc: {row['cc']}")
        if row["has_attachments"]:
            st.caption("📎 has attachments")
        st.divider()
        body = row["body_text"] or row["body_html"] or "(no body)"
        # Try the nicer email renderer; fall back to plain pre-wrap
        try:
            from casepulse.case_theory.ui.email_renderer import render_html
            st.markdown(
                f"<div class='reading-content'>{render_html(body)}</div>",
                unsafe_allow_html=True,
            )
        except Exception:
            st.markdown(
                f"<div class='reading-content'><pre>{body}</pre></div>",
                unsafe_allow_html=True,
            )

    elif source == "chat":
        row = _fetch_chat(db, source_id)
        if not row:
            st.error(f"Chat message #{source_id} not found")
            return
        st.markdown(
            f"### {row['platform'] or 'chat'} / {row['chat_name'] or row['sender']}"
        )
        st.caption(f"**{row['sender'] or '?'}** · {row['timestamp'] or '?'}")
        if row["has_media"]:
            st.caption(f"📎 {row['media_type'] or 'media'}: {row['media_path'] or ''}")
        st.divider()
        st.markdown(
            f"<div class='reading-content'><pre>{row['message_text'] or '(empty)'}</pre></div>",
            unsafe_allow_html=True,
        )

    elif source == "document":
        row = _fetch_document(db, source_id)
        if not row:
            st.error(f"Document #{source_id} not found")
            return
        st.markdown(f"### {row['filename']}")
        st.caption(f"Created: {row['created_at']}")
        if row["file_path"]:
            st.code(row["file_path"], language=None)
            st.caption(
                "📂 To open this file in Finder, copy the path above. "
                "An in-app PDF viewer arrives in a later phase."
            )
        if row["content_hash"]:
            st.caption(f"Hash: `{row['content_hash']}`")

    elif source == "attachment":
        row = _fetch_attachment(db, source_id)
        if not row:
            st.error(f"Attachment #{source_id} not found")
            return
        st.markdown(f"### {row['filename']}")
        if row["email_id"]:
            st.caption(f"From email #{row['email_id']}")
        st.caption(f"{row['content_type'] or '?'} · {row['size_bytes'] or 0} bytes")
        if row["file_path"]:
            st.code(row["file_path"], language=None)
        if row["is_duplicate"]:
            st.warning("This is flagged as a duplicate.")

    elif source == "photo":
        row = _fetch_photo(db, source_id)
        if not row:
            st.error(f"Photo #{source_id} not found")
            return
        st.markdown(f"### Photo #{source_id}")
        st.caption(f"Taken: {row['taken_at'] or 'unknown'}")
        if row["camera_make"] or row["camera_model"]:
            st.caption(f"📷 {row['camera_make'] or ''} {row['camera_model'] or ''}".strip())
        if row["gps_lat"] is not None and row["gps_lon"] is not None:
            st.caption(f"📍 {row['gps_lat']:.5f}, {row['gps_lon']:.5f}")
        if row["width"] and row["height"]:
            st.caption(f"{row['width']} × {row['height']}")
        st.caption(f"Source: {row['source_table']} #{row['source_row_id']}")

    elif source == "timeline_event":
        row = _fetch_timeline_event(db, source_id)
        if not row:
            st.error(f"Entry #{source_id} not found")
            return
        st.markdown(f"### {row['description'] or '(untitled)'}")
        st.caption(
            f"{row['category']} · {row['date']} {row['time'] or ''}".strip()
        )
        if row["notes"]:
            st.markdown(row["notes"])
        if row["metadata_json"]:
            with st.expander("Metadata", expanded=False):
                st.json(row["metadata_json"])
        st.divider()
        if st.button("Edit this entry", type="primary",
                      key=f"open_dialog_edit_{source_id}"):
            st.session_state["binder_edit_entry_id"] = source_id
            st.rerun()
        if st.button("Delete this entry",
                      key=f"open_dialog_del_{source_id}"):
            from casepulse.binder.repository import delete_binder_entry
            delete_binder_entry(db, source_id)
            st.success("Deleted.")
            st.rerun()

    else:
        st.error(f"Unknown source type: {source}")
