"""Unified chat importer — handles WhatsApp .txt, .zip, ChatVault HTML, PDF chats, and bulk directory imports."""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from casepulse.config import get_data_dir
from casepulse.storage.database import Database


def import_whatsapp_txt(file_path: str, db: Database,
                        progress_cb: Optional[Callable] = None) -> dict:
    """Import a WhatsApp .txt chat export."""
    from casepulse.chat_engine.whatsapp_parser import (
        parse_whatsapp_txt, detect_chat_name, get_participants,
    )

    if progress_cb:
        progress_cb(f"Parsing {Path(file_path).name}...")

    messages = parse_whatsapp_txt(file_path)
    if not messages:
        return {"error": "No messages found in file", "count": 0}

    chat_name = detect_chat_name(messages)
    participants = get_participants(messages)
    batch_id = f"wa_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return _store_messages(
        db, messages, "whatsapp_txt", file_path, "WhatsApp",
        chat_name, participants, batch_id, progress_cb,
    )


def import_whatsapp_zip(zip_path: str, db: Database,
                        progress_cb: Optional[Callable] = None) -> dict:
    """Import a WhatsApp .zip chat export (with media)."""
    from casepulse.chat_engine.whatsapp_parser import (
        parse_whatsapp_zip, detect_chat_name, get_participants,
    )

    if progress_cb:
        progress_cb(f"Extracting {Path(zip_path).name}...")

    messages, media_files = parse_whatsapp_zip(zip_path)
    if not messages:
        return {"error": "No messages found in zip", "count": 0}

    chat_name = detect_chat_name(messages)
    participants = get_participants(messages)
    batch_id = f"wa_{Path(zip_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    result = _store_messages(
        db, messages, "whatsapp_zip", zip_path, "WhatsApp",
        chat_name, participants, batch_id, progress_cb,
    )
    result["media_files"] = len(media_files)
    return result


def import_whatsapp_directory(dir_path: str, db: Database,
                               progress_cb: Optional[Callable] = None) -> dict:
    """Import a WhatsApp chat directory (folder with .txt + media files).

    This is for raw WhatsApp exports like:
    WhatsApp Chat with Person/
        WhatsApp Chat with Person.txt
        IMG-20200712-WA0016.jpg
        document.pdf
        ...
    """
    from casepulse.chat_engine.whatsapp_parser import (
        parse_whatsapp_txt, detect_chat_name, get_participants,
    )

    dir_path = Path(dir_path)
    if not dir_path.is_dir():
        return {"error": f"Not a directory: {dir_path}", "count": 0}

    # Find the chat .txt file
    txt_files = list(dir_path.glob("*.txt"))
    if not txt_files:
        return {"error": "No .txt chat file found in directory", "count": 0}

    chat_file = txt_files[0]
    if progress_cb:
        progress_cb(f"Parsing {chat_file.name}...")

    messages = parse_whatsapp_txt(str(chat_file))
    if not messages:
        return {"error": "No messages found", "count": 0}

    chat_name = detect_chat_name(messages)
    participants = get_participants(messages)
    batch_id = f"wa_{dir_path.name}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Map media references to actual files in the directory
    media_files = {}
    for f in dir_path.iterdir():
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".gif", ".webp",
                                 ".mp4", ".mp3", ".opus", ".ogg", ".oga",
                                 ".pdf", ".doc", ".docx", ".vcf", ".3gp"):
            media_files[f.name] = str(f)

    # Enrich messages with media paths
    for msg in messages:
        if msg.get("media_ref") and msg["media_ref"] in media_files:
            msg["media_path"] = media_files[msg["media_ref"]]
        elif msg.get("has_media") and not msg.get("media_path"):
            # Try to match by timestamp pattern in filename
            # e.g., IMG-20200712-WA0016.jpg
            pass

    result = _store_messages(
        db, messages, "whatsapp_dir", str(dir_path), "WhatsApp",
        chat_name, participants, batch_id, progress_cb,
    )
    result["media_files"] = len(media_files)

    # Also extract text from PDF/DOCX attachments in the directory
    extracted = 0
    from casepulse.attachments.extractor import extract_text
    for fname, fpath in media_files.items():
        ext = Path(fname).suffix.lower()
        if ext in (".pdf", ".docx", ".doc"):
            text = extract_text(fpath)
            if text:
                # Store as a chat message referencing the document
                content_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                db.insert_chat_message(
                    source_type="whatsapp_attachment",
                    source_file=fpath,
                    platform="WhatsApp",
                    chat_name=chat_name,
                    sender="__attachment__",
                    timestamp=None,
                    message_text=f"[Document: {fname}]\n\n{text[:10000]}",
                    has_media=True,
                    media_type="document",
                    media_path=fpath,
                    content_hash=content_hash,
                    is_system=False,
                    import_batch=batch_id,
                )
                extracted += 1
    if extracted and progress_cb:
        progress_cb(f"Extracted text from {extracted} documents")

    result["documents_extracted"] = extracted
    return result


def import_chatvault_html(file_path: str, db: Database,
                           progress_cb: Optional[Callable] = None) -> dict:
    """Import a ChatVault HTML export."""
    from casepulse.chat_engine.chatvault_parser import parse_chatvault_html

    if progress_cb:
        progress_cb(f"Parsing ChatVault export...")

    result = parse_chatvault_html(file_path)
    messages = result["messages"]

    if not messages:
        return {"error": "No messages found in ChatVault export", "count": 0}

    chat_name = result["chat_name"]
    participants = result["participants"]
    batch_id = f"cv_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Convert ChatVault format to our standard format
    converted = []
    for msg in messages:
        converted.append({
            "timestamp": msg.get("timestamp"),
            "sender": msg.get("sender", ""),
            "message": msg.get("message", ""),
            "is_system": msg.get("is_system", False),
            "has_media": msg.get("has_media", False),
            "media_ref": "",
            "media_path": msg.get("media_path", ""),
            "media_type": msg.get("media_type", ""),
        })

    return _store_messages(
        db, converted, "chatvault", file_path, "WhatsApp",
        chat_name, participants, batch_id, progress_cb,
    )


def import_appclose_pdf(file_path: str, db: Database,
                        progress_cb: Optional[Callable] = None) -> dict:
    """Import an AppClose co-parenting app PDF export."""
    from casepulse.chat_engine.appclose_parser import parse_appclose_pdf, get_participants

    if progress_cb:
        progress_cb("Parsing AppClose PDF export...")

    messages = parse_appclose_pdf(file_path)
    if not messages:
        return {"error": "No messages found in AppClose PDF", "count": 0}

    chat_name = "AppClose"
    participants = get_participants(messages)
    batch_id = f"appclose_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Convert to standard message format
    converted = []
    for m in messages:
        converted.append({
            "timestamp": m["timestamp"],
            "sender": m["sender"],
            "message": m["message"],
            "is_system": m.get("is_system", False),
            "has_media": m.get("has_media", False),
            "media_ref": m.get("media_ref", ""),
        })

    return _store_messages(
        db, converted, "appclose", file_path, "AppClose",
        chat_name, participants, batch_id, progress_cb,
    )


def import_pdf_chat(file_path: str, db: Database,
                     platform: str = "auto",
                     progress_cb: Optional[Callable] = None) -> dict:
    """Import a chat exported as PDF."""
    from casepulse.chat_engine.pdf_chat_parser import parse_pdf_chat

    if progress_cb:
        progress_cb(f"Parsing PDF chat export...")

    result = parse_pdf_chat(file_path, platform_hint=platform)
    messages = result["messages"]

    if not messages:
        # Fall back: store the raw text as a single document
        if result["raw_text"]:
            batch_id = f"pdf_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            content_hash = hashlib.sha256(
                result["raw_text"].encode("utf-8", errors="replace")
            ).hexdigest()
            db.insert_chat_message(
                source_type="pdf_chat_raw",
                source_file=file_path,
                platform=result["platform"],
                chat_name=Path(file_path).stem,
                sender="__document__",
                timestamp=None,
                message_text=result["raw_text"],
                content_hash=content_hash,
                is_system=False,
                import_batch=batch_id,
            )
            db.insert_chat_import(
                source_file=file_path, source_type="pdf_chat",
                platform=result["platform"],
                chat_name=Path(file_path).stem,
                message_count=1,
                date_start="", date_end="",
                participants=[],
            )
            return {"count": 1, "chat_name": Path(file_path).stem, "raw_fallback": True}

        return {"error": "No messages or text found in PDF", "count": 0}

    chat_name = Path(file_path).stem
    participants = sorted(set(m.get("sender", "") for m in messages if m.get("sender")))
    batch_id = f"pdf_{Path(file_path).stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    return _store_messages(
        db, messages, "pdf_chat", file_path, result["platform"],
        chat_name, participants, batch_id, progress_cb,
    )


def import_bulk_directory(dir_path: str, db: Database,
                           progress_cb: Optional[Callable] = None) -> dict:
    """Import all chat exports from a directory.

    Handles mixed content:
    - WhatsApp Chat with X/ subdirectories
    - WhatsApp Chat with X.zip files
    - ChatVault HTML files
    - PDF chat exports
    """
    root = Path(dir_path)
    results = {
        "total_imports": 0,
        "total_messages": 0,
        "total_media": 0,
        "errors": [],
        "imports": [],
    }

    items = sorted(root.iterdir())

    for item in items:
        try:
            if item.is_dir():
                # Check if it's a WhatsApp chat directory
                txt_files = list(item.glob("*.txt"))
                html_files = list(item.glob("**/index.html"))

                if txt_files and any("whatsapp" in f.stem.lower() or "chat" in f.stem.lower() for f in txt_files):
                    if progress_cb:
                        progress_cb(f"Importing WhatsApp directory: {item.name}")
                    result = import_whatsapp_directory(str(item), db, progress_cb)
                elif html_files:
                    # ChatVault or similar HTML export
                    for html_file in html_files:
                        if progress_cb:
                            progress_cb(f"Importing ChatVault: {html_file.name}")
                        result = import_chatvault_html(str(html_file), db, progress_cb)
                else:
                    continue

            elif item.suffix.lower() == ".zip":
                if progress_cb:
                    progress_cb(f"Importing zip: {item.name}")
                result = import_whatsapp_zip(str(item), db, progress_cb)

            elif item.suffix.lower() == ".txt":
                if progress_cb:
                    progress_cb(f"Importing txt: {item.name}")
                result = import_whatsapp_txt(str(item), db, progress_cb)

            elif item.suffix.lower() == ".pdf":
                if progress_cb:
                    progress_cb(f"Importing PDF: {item.name}")
                result = import_pdf_chat(str(item), db, progress_cb)

            elif item.suffix.lower() in (".html", ".htm"):
                if progress_cb:
                    progress_cb(f"Importing HTML: {item.name}")
                result = import_chatvault_html(str(item), db, progress_cb)

            else:
                continue

            if "error" in result:
                results["errors"].append(f"{item.name}: {result['error']}")
            else:
                results["total_imports"] += 1
                results["total_messages"] += result.get("count", 0)
                results["total_media"] += result.get("media_files", 0)
                results["imports"].append({
                    "name": item.name,
                    "messages": result.get("count", 0),
                    "chat_name": result.get("chat_name", ""),
                })

        except Exception as e:
            results["errors"].append(f"{item.name}: {str(e)}")

    if progress_cb:
        progress_cb(
            f"Bulk import complete: {results['total_imports']} chats, "
            f"{results['total_messages']} messages"
        )

    return results


def _store_messages(db: Database, messages: list[dict],
                    source_type: str, source_file: str,
                    platform: str, chat_name: str,
                    participants: list[str], batch_id: str,
                    progress_cb: Optional[Callable] = None) -> dict:
    """Store parsed messages in the database."""
    count = 0
    date_start = None
    date_end = None

    for i, msg in enumerate(messages):
        ts = msg.get("timestamp")
        ts_str = ""
        if isinstance(ts, datetime):
            ts_str = ts.isoformat()
        elif isinstance(ts, str):
            ts_str = ts

        if ts_str:
            if date_start is None or ts_str < date_start:
                date_start = ts_str
            if date_end is None or ts_str > date_end:
                date_end = ts_str

        text = msg.get("message", "")
        content_hash = ""
        if text:
            content_hash = hashlib.sha256(
                f"{ts_str}|{msg.get('sender', '')}|{text}".encode("utf-8", errors="replace")
            ).hexdigest()

        media_type = msg.get("media_type", "")
        if not media_type and msg.get("has_media"):
            media_ref = msg.get("media_ref", "").lower()
            if any(ext in media_ref for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                media_type = "image"
            elif any(ext in media_ref for ext in (".mp4", ".3gp")):
                media_type = "video"
            elif any(ext in media_ref for ext in (".mp3", ".opus", ".ogg", ".oga")):
                media_type = "audio"
            elif any(ext in media_ref for ext in (".pdf", ".doc", ".docx")):
                media_type = "document"

        db.insert_chat_message(
            source_type=source_type,
            source_file=source_file,
            platform=platform,
            chat_name=chat_name,
            sender=msg.get("sender", ""),
            timestamp=ts_str,
            message_text=text,
            has_media=msg.get("has_media", False),
            media_type=media_type,
            media_path=msg.get("media_path", ""),
            content_hash=content_hash,
            is_system=msg.get("is_system", False),
            import_batch=batch_id,
        )
        count += 1

        if progress_cb and (i + 1) % 500 == 0:
            progress_cb(f"Stored {i + 1}/{len(messages)} messages...")

    # Register sender mappings
    for p in participants:
        db.upsert_chat_sender_map(p, platform)

    # Record the import
    db.insert_chat_import(
        source_file=source_file,
        source_type=source_type,
        platform=platform,
        chat_name=chat_name,
        message_count=count,
        date_start=date_start or "",
        date_end=date_end or "",
        participants=participants,
    )

    if progress_cb:
        progress_cb(f"Imported {count} messages from {chat_name}")

    return {
        "count": count,
        "chat_name": chat_name,
        "participants": participants,
        "date_start": date_start,
        "date_end": date_end,
    }
