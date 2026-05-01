"""Text chunking for RAG pipeline — splits emails into retrievable chunks."""
from __future__ import annotations

import json
from typing import Optional

from casepulse.storage.database import Database


def chunk_email(email: dict, chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict]:
    """Split an email into chunks with metadata for retrieval.

    Each chunk includes:
    - text: The chunk content
    - metadata: sender, date, subject, direction, email_id, chunk_index
    """
    chunks = []
    email_id = email["id"]
    subject = email.get("subject", "")
    sender = email.get("sender_email", "")
    sender_name = email.get("sender_name", "")
    date = email.get("date_received", "")
    direction = email.get("direction", "")

    # Build a header that gets prepended to each chunk for context
    header = f"Email from {sender_name or sender} ({sender})\n"
    header += f"Date: {date}\n"
    header += f"Subject: {subject}\n"
    if direction:
        header += f"Direction: {direction}\n"

    # Recipients
    recipients = email.get("recipients", "")
    if recipients:
        if isinstance(recipients, str):
            try:
                recipients = json.loads(recipients)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(recipients, list):
            recip_str = ", ".join(
                r.get("email", r) if isinstance(r, dict) else str(r)
                for r in recipients
            )
            header += f"To: {recip_str}\n"

    if email.get("is_forwarded"):
        header += f"[Forwarded] Original sender: {email.get('original_sender', 'unknown')}\n"

    header += "---\n"

    body = email.get("body_text", "") or ""
    if not body.strip():
        return []

    # Split body into chunks
    words = body.split()
    if not words:
        return []

    # If body fits in one chunk, return it whole
    if len(words) <= chunk_size:
        chunks.append({
            "text": header + body,
            "metadata": _build_metadata(email, 0),
        })
        return chunks

    # Split into overlapping chunks
    idx = 0
    chunk_index = 0
    while idx < len(words):
        end = min(idx + chunk_size, len(words))
        chunk_text = " ".join(words[idx:end])

        chunks.append({
            "text": header + chunk_text,
            "metadata": _build_metadata(email, chunk_index),
        })

        idx += chunk_size - chunk_overlap
        chunk_index += 1

    return chunks


def chunk_attachment(attachment: dict, email: dict,
                     chunk_size: int = 500, chunk_overlap: int = 50) -> list[dict]:
    """Split attachment extracted text into chunks with metadata."""
    extracted = attachment.get("extracted_text", "")
    if not extracted or not extracted.strip():
        return []

    chunks = []
    email_id = email["id"]
    filename = attachment.get("filename", "unknown")

    header = (
        f"Attachment: {filename}\n"
        f"From email: {email.get('subject', '')} "
        f"({email.get('sender_email', '')}, {email.get('date_received', '')})\n"
        f"---\n"
    )

    words = extracted.split()
    if len(words) <= chunk_size:
        chunks.append({
            "text": header + extracted,
            "metadata": {
                "email_id": email_id,
                "attachment_id": attachment["id"],
                "filename": filename,
                "sender": email.get("sender_email", ""),
                "date": email.get("date_received", ""),
                "subject": email.get("subject", ""),
                "type": "attachment",
            },
        })
        return chunks

    idx = 0
    chunk_index = 0
    while idx < len(words):
        end = min(idx + chunk_size, len(words))
        chunk_text = " ".join(words[idx:end])

        chunks.append({
            "text": header + chunk_text,
            "metadata": {
                "email_id": email_id,
                "attachment_id": attachment["id"],
                "filename": filename,
                "sender": email.get("sender_email", ""),
                "date": email.get("date_received", ""),
                "subject": email.get("subject", ""),
                "type": "attachment",
                "chunk_index": chunk_index,
            },
        })

        idx += chunk_size - chunk_overlap
        chunk_index += 1

    return chunks


def chunk_chat_messages(messages: list[dict], chunk_size: int = 500,
                        chunk_overlap: int = 50) -> list[dict]:
    """Group chat messages into conversation chunks for RAG.

    Instead of chunking individual messages (too short), groups sequential
    messages into conversation windows for better context.
    """
    chunks = []
    if not messages:
        return chunks

    # Group messages into windows of ~chunk_size words
    window = []
    window_words = 0
    chunk_index = 0

    for msg in messages:
        text = msg.get("message_text", "") or ""
        sender = msg.get("sender", "")
        timestamp = msg.get("timestamp", "")
        words = len(text.split())

        if msg.get("is_system"):
            continue

        window.append(msg)
        window_words += words

        if window_words >= chunk_size:
            chunk = _build_chat_chunk(window, chunk_index)
            if chunk:
                chunks.append(chunk)
            # Overlap: keep last few messages
            overlap_msgs = max(2, len(window) // 4)
            window = window[-overlap_msgs:]
            window_words = sum(len((m.get("message_text") or "").split()) for m in window)
            chunk_index += 1

    # Don't forget remaining messages
    if window:
        chunk = _build_chat_chunk(window, chunk_index)
        if chunk:
            chunks.append(chunk)

    return chunks


def _build_chat_chunk(messages: list[dict], chunk_index: int) -> Optional[dict]:
    """Build a single chunk from a window of chat messages."""
    if not messages:
        return None

    chat_name = messages[0].get("chat_name", "")
    platform = messages[0].get("platform", "chat")
    first_ts = messages[0].get("timestamp", "")
    last_ts = messages[-1].get("timestamp", "")

    header = f"Chat: {chat_name} ({platform})\n"
    header += f"Period: {first_ts[:16] if first_ts else '?'} to {last_ts[:16] if last_ts else '?'}\n"
    header += "---\n"

    lines = []
    for msg in messages:
        ts = msg.get("timestamp", "")[:16] if msg.get("timestamp") else ""
        sender = msg.get("sender", "?")
        text = msg.get("message_text", "")
        if msg.get("has_media"):
            media_type = msg.get("media_type", "media")
            text = text or f"[{media_type}]"
        if text:
            lines.append(f"[{ts}] {sender}: {text}")

    if not lines:
        return None

    body = "\n".join(lines)
    senders = list(set(m.get("sender", "") for m in messages if m.get("sender")))

    return {
        "text": header + body,
        "metadata": {
            "type": "chat",
            "platform": platform,
            "chat_name": chat_name,
            "sender": ", ".join(senders[:5]),
            "date": first_ts[:10] if first_ts else "",
            "date_end": last_ts[:10] if last_ts else "",
            "subject": chat_name,
            "chunk_index": chunk_index,
        },
    }


def chunk_document(doc: dict, chunk_size: int = 500,
                   overlap: int = 50) -> list[dict]:
    """Chunk a documents-table row into RAG chunks with metadata."""
    text = doc.get("extracted_text", "") or ""
    if not text:
        return []
    words = text.split()
    chunks = []
    i = 0
    chunk_idx = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        body = " ".join(chunk_words)
        header = f"Document: {doc.get('filename', 'unknown')}\n"
        chunks.append({
            "text": header + body,
            "metadata": {
                "document_id": doc["id"],
                "filename": doc.get("filename"),
                "type": "document",
                "chunk_index": chunk_idx,
            },
        })
        i += chunk_size - overlap
        chunk_idx += 1
    return chunks


def build_all_chunks(db: Database, chunk_size: int = 500,
                     chunk_overlap: int = 50,
                     progress_cb=None) -> list[dict]:
    """Build chunks from all emails, attachments, chat messages, AND documents."""
    all_chunks = []

    # ── Email chunks ──
    emails = db.get_emails(limit=100000)
    for i, email in enumerate(emails):
        email_chunks = chunk_email(email, chunk_size, chunk_overlap)
        all_chunks.extend(email_chunks)

        attachments = db.get_attachments_for_email(email["id"])
        for att in attachments:
            att_chunks = chunk_attachment(att, email, chunk_size, chunk_overlap)
            all_chunks.extend(att_chunks)

        if progress_cb and (i + 1) % 50 == 0:
            progress_cb(f"Chunked {i + 1}/{len(emails)} emails... {len(all_chunks)} chunks so far")

    if progress_cb:
        progress_cb(f"Emails done: {len(all_chunks)} chunks from {len(emails)} emails")

    # ── Chat message chunks ──
    chat_messages = db.get_chat_messages(limit=500000)
    if chat_messages:
        if progress_cb:
            progress_cb(f"Chunking {len(chat_messages)} chat messages...")

        # Group by chat_name for better context
        chats = {}
        for msg in chat_messages:
            key = msg.get("chat_name", "unknown")
            if key not in chats:
                chats[key] = []
            chats[key].append(msg)

        for chat_name, msgs in chats.items():
            chat_chunks = chunk_chat_messages(msgs, chunk_size, chunk_overlap)
            all_chunks.extend(chat_chunks)

        if progress_cb:
            progress_cb(f"Chat done: {len(all_chunks)} total chunks ({len(chat_messages)} messages from {len(chats)} chats)")

    # ── Document chunks ──
    documents = db.get_documents()
    if documents:
        if progress_cb:
            progress_cb(f"Chunking {len(documents)} documents...")
        for doc in documents:
            doc_chunks = chunk_document(doc, chunk_size, chunk_overlap)
            all_chunks.extend(doc_chunks)
        if progress_cb:
            progress_cb(f"Documents done: {len(all_chunks)} total chunks")

    if progress_cb:
        progress_cb(f"Total: {len(all_chunks)} chunks ready for indexing")

    return all_chunks


def _build_metadata(email: dict, chunk_index: int) -> dict:
    return {
        "email_id": email["id"],
        "sender": email.get("sender_email", ""),
        "sender_name": email.get("sender_name", ""),
        "date": email.get("date_received", ""),
        "subject": email.get("subject", ""),
        "direction": email.get("direction", ""),
        "is_forwarded": bool(email.get("is_forwarded")),
        "original_sender": email.get("original_sender", ""),
        "has_attachments": bool(email.get("has_attachments")),
        "type": "email",
        "chunk_index": chunk_index,
    }
