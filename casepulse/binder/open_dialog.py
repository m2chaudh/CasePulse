"""Open dialog — shows the content of an aggregated item by source type.

For emails: renders the original HTML body (sanitised) when available so
paragraphing / formatting is preserved, splits on common thread
boundaries (Gmail 'On ... wrote:', Outlook 'From: ... Sent: ...',
'-----Original Message-----', 'Begin forwarded message:'), and shows
each earlier message in its own expander. Attachments render inline
(images displayed; PDFs/docs show extracted text + path; other types
show metadata + download).
"""
from __future__ import annotations
import base64
import json
import re
from html import escape
from pathlib import Path
import streamlit as st


# Cap inline-PDF rendering to keep base64 payloads small. Larger PDFs
# fall back to extracted text + Download.
_PDF_INLINE_LIMIT = 12 * 1024 * 1024  # 12 MB


def _render_pdf_inline(file_path: str, height: int = 720) -> bool:
    """Render the PDF via a base64 iframe so the browser's built-in
    viewer handles layout/fonts/images correctly. Returns True on
    success, False if the file is too large or unreadable."""
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return False
    size = p.stat().st_size
    if size > _PDF_INLINE_LIMIT:
        st.caption(
            f"PDF is {_human_size(size)} — too large to preview inline. "
            "Use Download to open it locally."
        )
        return False
    try:
        with p.open("rb") as f:
            data = f.read()
    except OSError:
        return False
    b64 = base64.b64encode(data).decode("ascii")
    iframe = (
        f'<iframe src="data:application/pdf;base64,{b64}" '
        f'width="100%" height="{height}" type="application/pdf" '
        f'style="border:1px solid var(--cp-rule);border-radius:6px;'
        f'background:white"></iframe>'
    )
    st.markdown(iframe, unsafe_allow_html=True)
    return True


def _human_size(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _is_image(content_type: str, filename: str) -> bool:
    if content_type and content_type.lower().startswith("image/"):
        return True
    if filename:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "tif", "heic"):
            return True
    return False


def _is_pdf(content_type: str, filename: str) -> bool:
    if content_type and "pdf" in content_type.lower():
        return True
    return bool(filename) and filename.lower().endswith(".pdf")


def _fetch_attachments(db, email_id: int) -> list[dict]:
    with db._get_conn() as conn:
        rows = conn.execute(
            """SELECT id, filename, content_type, size_bytes, file_path,
                      extracted_text, content_hash, is_duplicate, duplicate_of
               FROM attachments
               WHERE email_id = ? ORDER BY id""",
            (email_id,),
        ).fetchall()
    return [dict(r) for r in rows]


_CID_RE = re.compile(r'''(<img[^>]*?\bsrc\s*=\s*["'])cid:([^"'>]+)(["'])''',
                     re.IGNORECASE)


def _resolve_cid_images(html: str, attachments: list[dict]) -> tuple[str, set[int]]:
    """Replace `<img src="cid:SOMEID">` tags in the HTML body with
    `data:image/...;base64,...` URLs computed from the matching
    attachment's bytes. Returns (resolved_html, set_of_inline_ids) so
    the caller can drop those from the bottom Attachments section.

    Match is heuristic: looks for an attachment whose filename contains
    the cid (or its base before '@'). Common patterns like
    'image001.png' / 'cid:image001@0123' resolve cleanly."""
    inline_ids: set[int] = set()
    if not html or not attachments:
        return (html or ""), inline_ids

    # Index image attachments by lowercase filename for the heuristic
    img_atts = [a for a in attachments if _is_image(a.get("content_type") or "",
                                                     a.get("filename") or "")]
    if not img_atts:
        return html, inline_ids

    def _data_url(att: dict) -> str | None:
        path = att.get("file_path")
        if not path:
            return None
        try:
            p = Path(path)
            if not (p.exists() and p.is_file()):
                return None
            with p.open("rb") as f:
                data = f.read()
            ctype = att.get("content_type") or "image/png"
            return f"data:{ctype};base64,{base64.b64encode(data).decode('ascii')}"
        except OSError:
            return None

    def _replace(m: re.Match) -> str:
        prefix, cid, quote = m.group(1), m.group(2), m.group(3)
        cid_lower = cid.lower()
        cid_base = cid_lower.split("@", 1)[0]
        for att in img_atts:
            fn = (att.get("filename") or "").lower()
            stem = fn.rsplit(".", 1)[0] if "." in fn else fn
            if cid_lower in fn or cid_base in fn or stem == cid_base:
                url = _data_url(att)
                if url:
                    inline_ids.add(att["id"])
                    return f"{prefix}{url}{quote}"
        return m.group(0)  # unchanged

    return _CID_RE.sub(_replace, html), inline_ids


def _render_email_message(
    db, msg: dict, *,
    expanded: bool,
    is_focal: bool,
    seen_hashes: dict,
) -> None:
    """Render one email message in the thread — headers, body (with cid:
    images inlined), and the message's own attachments. Attachments
    already seen earlier in the thread (by content_hash) render as a
    dedup notice instead of a duplicate. The whole block lives inside an
    expander labelled with sender + date, expanded based on the flag."""
    sender = msg["sender_name"] or msg["sender_email"] or "?"
    when = msg["date_received"] or msg["date_sent"] or "?"
    label = f"{'★ ' if is_focal else ''}From {sender} · {when}"

    with st.expander(label, expanded=expanded):
        to_str = _format_recipients(msg["recipients"])
        cc_str = _format_recipients(msg["cc"])
        if to_str:
            st.caption(f"To: {to_str}")
        if cc_str:
            st.caption(f"Cc: {cc_str}")

        # Pre-fetch attachments so cid: in body can resolve
        atts = _fetch_attachments(db, msg["id"]) if msg["has_attachments"] else []
        inline_ids: set[int] = set()

        body_html = msg["body_html"]
        body_text = msg["body_text"]

        if body_html:
            html, inline_ids = _resolve_cid_images(body_html, atts)
            safe = _sanitize_html(html)
            st.markdown(
                f"<div class='reading-content email-body'>{safe}</div>",
                unsafe_allow_html=True,
            )
        else:
            body = body_text or "(no body)"
            parts = _split_thread(body)
            if parts:
                st.markdown(
                    f"<div class='reading-content'>"
                    f"{_plaintext_to_html(parts[0])}</div>",
                    unsafe_allow_html=True,
                )
                for chunk in parts[1:]:
                    with st.expander(f"↪ {_peek_thread_header(chunk)}"):
                        st.markdown(
                            f"<div class='reading-content'>"
                            f"{_plaintext_to_html(chunk)}</div>",
                            unsafe_allow_html=True,
                        )

        # Attachments for THIS message — non-inline ones
        non_inline = [a for a in atts if a["id"] not in inline_ids]
        if non_inline or inline_ids:
            n_visible = len(non_inline)
            n_inline = len(inline_ids)
            header_bits = []
            if n_visible:
                header_bits.append(f"{n_visible} file(s)")
            if n_inline:
                header_bits.append(f"{n_inline} inline image(s) shown above")
            if header_bits:
                st.markdown("**📎 Attachments — " + " · ".join(header_bits) + "**")

            for att in non_inline:
                ch = att.get("content_hash") or ""
                prior = seen_hashes.get(ch) if ch else None
                if prior:
                    # Dedup — same file as in earlier message
                    st.markdown(
                        f"📎 **{att['filename']}** "
                        f"<small>· {_human_size(att['size_bytes'])} · "
                        f"<em>same file as in {prior['date']} from {prior['from']}</em>"
                        f"</small>",
                        unsafe_allow_html=True,
                    )
                else:
                    if ch:
                        seen_hashes[ch] = {
                            "date": when, "from": sender,
                            "filename": att["filename"],
                        }
                    _render_attachment_inline(att, key_prefix=f"email_{msg['id']}")


def _render_attachment_inline(att: dict, *, key_prefix: str) -> None:
    """Render a single attachment inside an expander. Images shown
    inline; PDFs/docs show extracted text + path; other types show
    metadata only."""
    filename = att["filename"] or "(unnamed)"
    size = _human_size(att["size_bytes"])
    ctype = att["content_type"] or ""
    label = f"📎 {filename}  ·  {size}"
    if att["is_duplicate"]:
        label += "  ·  ⚠ duplicate"

    with st.expander(label, expanded=False):
        meta_cols = st.columns([3, 1])
        with meta_cols[0]:
            st.caption(f"Type: {ctype or 'unknown'}")
            if att["file_path"]:
                # Show path as code so user can copy
                st.code(att["file_path"], language=None)
        with meta_cols[1]:
            # Download button if file exists on disk
            if att["file_path"]:
                p = Path(att["file_path"])
                if p.exists() and p.is_file():
                    try:
                        with p.open("rb") as f:
                            data = f.read()
                        st.download_button(
                            "Download",
                            data=data,
                            file_name=filename,
                            mime=ctype or "application/octet-stream",
                            key=f"{key_prefix}_dl_{att['id']}",
                        )
                    except OSError:
                        st.caption("(file unreadable)")

        # Inline preview by type
        if att["file_path"] and Path(att["file_path"]).exists():
            if _is_image(ctype, filename):
                try:
                    st.image(att["file_path"], use_container_width=True)
                except Exception as e:
                    st.caption(f"(image preview failed: {e})")
            elif _is_pdf(ctype, filename):
                # Render the PDF via the browser's built-in viewer for
                # full fidelity (layout, fonts, embedded images, tables).
                rendered = _render_pdf_inline(att["file_path"])
                # Keep extracted text as a secondary view — useful for
                # copy/paste and quick text search.
                if att.get("extracted_text"):
                    label = "Extracted text" if rendered else "Extracted text (PDF preview unavailable)"
                    with st.expander(label, expanded=not rendered):
                        st.markdown(
                            f"<div class='reading-content'><pre>"
                            f"{escape(att['extracted_text'][:8000])}"
                            f"{'…' if len(att['extracted_text']) > 8000 else ''}"
                            f"</pre></div>",
                            unsafe_allow_html=True,
                        )
                elif not rendered:
                    st.caption("No extracted text available. Use Download to open it locally.")
            elif att.get("extracted_text"):
                # Plain text / DOCX / etc. — show extracted text
                with st.container(border=True):
                    st.markdown(
                        f"<div class='reading-content'><pre>"
                        f"{escape(att['extracted_text'][:8000])}"
                        f"{'…' if len(att['extracted_text']) > 8000 else ''}"
                        f"</pre></div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("File not on disk (deleted or moved). Metadata only.")


def _fetch_email(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, subject, sender_email, sender_name, recipients,
                      cc, date_received, date_sent, body_text, body_html,
                      has_attachments, parent_email_id
               FROM emails WHERE id = ?""",
            (source_id,),
        ).fetchone()


def _fetch_email_thread(db, email_id: int) -> list[dict]:
    """Walk parent_email_id forward (children) and backward (parents)
    to assemble the email thread. Returns chronologically sorted list
    (oldest first). The email_id passed in is always included."""
    seen: set[int] = set()
    thread: list[dict] = []

    def add(row):
        if row and row["id"] not in seen:
            seen.add(row["id"])
            thread.append(dict(row))

    # Walk backward: this email → its parent → grandparent → ...
    cur_id = email_id
    while cur_id and cur_id not in seen:
        row = _fetch_email(db, cur_id)
        if not row:
            break
        add(row)
        cur_id = row["parent_email_id"]

    # Walk forward: anyone whose parent_email_id is in our seen set
    frontier = set(seen)
    while frontier:
        with db._get_conn() as conn:
            placeholders = ",".join("?" for _ in frontier)
            rows = conn.execute(
                f"""SELECT id FROM emails
                    WHERE parent_email_id IN ({placeholders})
                      AND id NOT IN ({','.join('?' for _ in seen)})""",
                (*frontier, *seen),
            ).fetchall()
        next_frontier = set()
        for r in rows:
            child = _fetch_email(db, r["id"])
            if child and child["id"] not in seen:
                add(child)
                next_frontier.add(child["id"])
        frontier = next_frontier

    thread.sort(key=lambda e: e.get("date_received") or e.get("date_sent") or "")
    return thread


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


def _format_recipients(raw) -> str:
    """Format a recipients/cc JSON string as 'Name <email>, ...'."""
    if not raw:
        return ""
    try:
        people = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return str(raw)
    if not isinstance(people, list):
        return str(raw)
    parts = []
    for p in people:
        if not isinstance(p, dict):
            parts.append(str(p))
            continue
        name = (p.get("name") or "").strip()
        email = (p.get("email") or "").strip()
        if name and email:
            parts.append(f"{name} <{email}>")
        elif email:
            parts.append(email)
        elif name:
            parts.append(name)
    return ", ".join(parts) or str(raw)


def _sanitize_html(html: str) -> str:
    """Strip dangerous / overriding HTML so the email body renders inside
    Streamlit without escaping our theme. Uses BeautifulSoup which is
    already in requirements.txt."""
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return escape(html)
    soup = BeautifulSoup(html, "lxml")
    # Drop tags that override our chrome or run code
    for sel in ("script", "style", "iframe", "object", "embed", "meta", "link", "base"):
        for tag in soup.find_all(sel):
            tag.decompose()
    # Drop event handlers + javascript: hrefs
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on"):
                del tag[attr]
            elif attr.lower() in ("href", "src"):
                v = tag.get(attr) or ""
                if isinstance(v, str) and v.strip().lower().startswith("javascript:"):
                    del tag[attr]
    body = soup.find("body")
    return str(body) if body else str(soup)


# Boundary regexes for splitting plain-text email bodies into thread
# messages. Each regex matches the START of a previous message header.
# DOTALL on the Gmail pattern lets "." match newlines so "On <date>...
# wrote:" splits that span email-address-on-its-own-line still match.
_BOUNDARIES = [
    # Gmail: "On Mon, Aug 19, 2024 at 1:10 PM Mani Chaudhary <\nx@y\n> wrote:"
    re.compile(r"^On\s.+?wrote:\s*$",
               re.MULTILINE | re.DOTALL | re.IGNORECASE),
    # Outlook: "From: ..." followed within ~3 lines by "Sent:" or "Date:"
    re.compile(
        r"^From:\s.+\r?\n(?:.*\r?\n){0,3}?(?:Sent|Date):\s",
        re.MULTILINE | re.IGNORECASE,
    ),
    # Apple Mail / generic
    re.compile(r"^Begin forwarded message:\s*$", re.MULTILINE | re.IGNORECASE),
    # Old-style forward marker
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.MULTILINE | re.IGNORECASE),
]


def _split_thread(body: str) -> list[str]:
    """Split an email body into [latest, earlier_1, earlier_2, ...]
    using common Gmail/Outlook/Apple thread boundaries."""
    if not body:
        return []
    cuts = []
    for rx in _BOUNDARIES:
        for m in rx.finditer(body):
            cuts.append(m.start())
    if not cuts:
        return [body.rstrip()]
    cuts = sorted(set(cuts))
    parts = []
    prev = 0
    for c in cuts:
        chunk = body[prev:c].rstrip()
        if chunk.strip():
            parts.append(chunk)
        prev = c
    tail = body[prev:].rstrip()
    if tail.strip():
        parts.append(tail)
    return parts


def _plaintext_to_html(text: str) -> str:
    """Render a plain-text email chunk as basic HTML — escape, then
    convert blank-line-separated paragraphs into <p>, single newlines
    into <br>."""
    if not text:
        return ""
    paragraphs = re.split(r"\n\s*\n", text)
    out = []
    for p in paragraphs:
        if not p.strip():
            continue
        out.append("<p>" + escape(p).replace("\n", "<br>") + "</p>")
    return "\n".join(out) or "<p>(empty)</p>"


def _peek_thread_header(chunk: str) -> str:
    """Pull a one-line preview from a thread chunk — the first
    'From:' line or the 'On ... wrote:' line — to use as expander label."""
    for line in chunk.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith("from:") or s.lower().startswith("on "):
            return s[:140]
        return s[:140]
    return "(earlier message)"


def _fetch_timeline_event(db, source_id: int):
    with db._get_conn() as conn:
        return conn.execute(
            """SELECT id, date, time, category, description, notes,
                      source_type, source_id, metadata_json, case_id
               FROM timeline_events WHERE id = ?""",
            (source_id,),
        ).fetchone()


@st.dialog("Item details", width="large")
def open_item_dialog(db, *, source: str, source_id: int):
    """Show the content of an item. Read-only viewer."""
    if source == "email":
        focal = _fetch_email(db, source_id)
        if not focal:
            st.error(f"Email #{source_id} not found")
            return
        # Subject is the same across the thread; show once at top
        st.markdown(f"### {focal['subject'] or '(no subject)'}")

        thread = _fetch_email_thread(db, source_id)
        seen_hashes: dict[str, dict] = {}  # content_hash → {email_date, filename}

        # Render each message in chronological order. Most-recent (which
        # is also the focal one if it's the latest reply) is expanded.
        for idx, msg in enumerate(thread):
            is_focal = msg["id"] == source_id
            is_last = idx == len(thread) - 1
            _render_email_message(
                db, msg,
                expanded=is_focal or is_last,
                is_focal=is_focal,
                seen_hashes=seen_hashes,
            )
        return  # rest of the email branch superseded by per-message rendering

        # Pre-fetch attachments so we can inline cid: images into the body
        # AND know which to hide from the bottom Attachments list.
        all_atts = _fetch_attachments(db, row["id"]) if row["has_attachments"] else []
        inline_att_ids: set[int] = set()

        if row["body_html"]:
            # Prefer the HTML body — preserves paragraphing, formatting,
            # nested-quote styling done by the original mail client.
            html_with_inline_imgs, inline_att_ids = _resolve_cid_images(
                row["body_html"], all_atts,
            )
            safe = _sanitize_html(html_with_inline_imgs)
            st.markdown(
                f"<div class='reading-content email-body'>{safe}</div>",
                unsafe_allow_html=True,
            )
        else:
            # Fall back to plain text. Split on common thread boundaries
            # so each previous message lives in its own expander.
            body = row["body_text"] or "(no body)"
            parts = _split_thread(body)
            if not parts:
                st.markdown("<p>(empty)</p>", unsafe_allow_html=True)
            else:
                # First chunk is the latest message — render inline
                st.markdown(
                    f"<div class='reading-content'>{_plaintext_to_html(parts[0])}</div>",
                    unsafe_allow_html=True,
                )
                # Each subsequent chunk = one earlier message in the thread
                for i, chunk in enumerate(parts[1:], start=1):
                    label = f"↪ {_peek_thread_header(chunk)}"
                    with st.expander(label, expanded=(i == 1)):
                        st.markdown(
                            f"<div class='reading-content'>"
                            f"{_plaintext_to_html(chunk)}</div>",
                            unsafe_allow_html=True,
                        )

        # Attachments section — only the *non-inline* attachments. The
        # ones already rendered as cid:-resolved <img> in the body
        # (signatures, inline screenshots, logos) don't need a duplicate
        # entry below.
        if all_atts:
            visible_atts = [a for a in all_atts if a["id"] not in inline_att_ids]
            if visible_atts:
                st.divider()
                label = f"#### 📎 Attachments ({len(visible_atts)})"
                if inline_att_ids:
                    label += f"  ·  *{len(inline_att_ids)} inline image(s) shown above*"
                st.markdown(label)
                for att in visible_atts:
                    _render_attachment_inline(att, key_prefix=f"email_{row['id']}")
            elif inline_att_ids:
                st.caption(
                    f"All {len(inline_att_ids)} attachment(s) are inline images "
                    "in the body above (signatures, embedded screenshots, etc.)."
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
