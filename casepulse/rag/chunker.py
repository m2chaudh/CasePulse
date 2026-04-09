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


def build_all_chunks(db: Database, chunk_size: int = 500,
                     chunk_overlap: int = 50,
                     progress_cb=None) -> list[dict]:
    """Build chunks from all emails and attachments in the database."""
    all_chunks = []
    emails = db.get_emails(limit=100000)

    for i, email in enumerate(emails):
        # Chunk the email body
        email_chunks = chunk_email(email, chunk_size, chunk_overlap)
        all_chunks.extend(email_chunks)

        # Chunk attachments
        attachments = db.get_attachments_for_email(email["id"])
        for att in attachments:
            att_chunks = chunk_attachment(att, email, chunk_size, chunk_overlap)
            all_chunks.extend(att_chunks)

        if progress_cb and (i + 1) % 50 == 0:
            progress_cb(f"Chunked {i + 1}/{len(emails)} emails... {len(all_chunks)} chunks so far")

    if progress_cb:
        progress_cb(f"Done. {len(all_chunks)} total chunks from {len(emails)} emails")

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
