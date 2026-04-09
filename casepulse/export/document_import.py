"""Document import — scan folders, detect duplicates, extract text, find dates."""
from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from casepulse.config import get_data_dir
from casepulse.storage.database import Database
from casepulse.attachments.extractor import extract_text

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".rtf", ".csv",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",
    ".eml", ".msg", ".htm", ".html",
}


def import_directory(dir_path: str, db: Database,
                     copy_files: bool = True,
                     progress_cb: Optional[Callable] = None) -> dict:
    """Import all supported documents from a directory.

    Returns: {imported, duplicates, errors, files: [{filename, status, doc_id}]}
    """
    root = Path(dir_path)
    if not root.is_dir():
        return {"error": f"Not a directory: {dir_path}", "imported": 0}

    dest_dir = get_data_dir() / "documents"
    dest_dir.mkdir(exist_ok=True)

    files = sorted(f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)

    result = {"imported": 0, "duplicates": 0, "errors": 0, "files": []}

    for i, file_path in enumerate(files):
        if progress_cb:
            progress_cb(f"Processing {i + 1}/{len(files)}: {file_path.name}")

        try:
            # Compute hash for duplicate detection
            content_hash = _hash_file(str(file_path))

            # Check for duplicate
            existing = db.get_document_by_hash(content_hash)
            if existing:
                result["duplicates"] += 1
                result["files"].append({
                    "filename": file_path.name,
                    "status": "duplicate",
                    "duplicate_of": existing["filename"],
                })
                continue

            # Copy file to data directory
            if copy_files:
                dest_path = dest_dir / file_path.name
                # Handle name collisions
                counter = 1
                while dest_path.exists():
                    stem = file_path.stem
                    dest_path = dest_dir / f"{stem}_{counter}{file_path.suffix}"
                    counter += 1
                shutil.copy2(str(file_path), str(dest_path))
                stored_path = str(dest_path)
            else:
                stored_path = str(file_path)

            # Determine content type
            ext = file_path.suffix.lower()
            content_type = _ext_to_mime(ext)

            # Extract text (for non-image files)
            extracted = ""
            ocr_status = "pending"
            if ext in (".pdf", ".docx", ".doc", ".txt", ".rtf", ".csv", ".eml", ".htm", ".html"):
                extracted = extract_text(stored_path, content_type)
                ocr_status = "done" if extracted else "no_text"
            elif ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"):
                ocr_status = "needs_ocr"  # Images need vision model

            # Insert into database
            doc_id = db.insert_document(
                filename=file_path.name,
                file_path=stored_path,
                content_type=content_type,
                size_bytes=file_path.stat().st_size,
                content_hash=content_hash,
                extracted_text=extracted,
                ocr_status=ocr_status,
                source_dir=str(root),
            )

            result["imported"] += 1
            result["files"].append({
                "filename": file_path.name,
                "status": "imported",
                "doc_id": doc_id,
                "has_text": bool(extracted),
            })

        except Exception as e:
            result["errors"] += 1
            result["files"].append({
                "filename": file_path.name,
                "status": "error",
                "error": str(e),
            })

    if progress_cb:
        progress_cb(f"Done: {result['imported']} imported, {result['duplicates']} duplicates, {result['errors']} errors")

    return result


def extract_dates_from_text(text: str) -> list[dict]:
    """Try to extract dates from document text.

    Returns list of {date, context} where context is the surrounding text.
    """
    if not text:
        return []

    dates_found = []
    lines = text.split("\n")

    # Date patterns to look for
    patterns = [
        # 2025-01-15 or 2025/01/15
        (r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", "%Y-%m-%d"),
        # January 15, 2025 or Jan 15, 2025
        (r"(\w{3,9}\s+\d{1,2},?\s+\d{4})", None),
        # 15/01/2025 or 01/15/2025
        (r"(\d{1,2}/\d{1,2}/\d{4})", None),
        # 15-Jan-2025
        (r"(\d{1,2}-\w{3}-\d{4})", None),
    ]

    date_formats = [
        "%Y-%m-%d", "%Y/%m/%d",
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
        "%m/%d/%Y", "%d/%m/%Y",
        "%d-%b-%Y", "%d-%B-%Y",
    ]

    seen = set()
    for line_num, line in enumerate(lines):
        for pattern, _ in patterns:
            for match in re.finditer(pattern, line):
                date_str = match.group(1).strip().rstrip(",")
                if date_str in seen:
                    continue

                # Try to parse the date
                parsed = None
                for fmt in date_formats:
                    try:
                        parsed = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue

                if parsed and 2000 <= parsed.year <= 2030:
                    seen.add(date_str)
                    # Get surrounding context
                    start = max(0, line_num - 1)
                    end = min(len(lines), line_num + 2)
                    context = " ".join(lines[start:end])[:200]

                    dates_found.append({
                        "date": parsed.strftime("%Y-%m-%d"),
                        "raw": date_str,
                        "context": context.strip(),
                        "line": line_num + 1,
                    })

    # Sort by date
    dates_found.sort(key=lambda x: x["date"])
    return dates_found


def parse_timeline_html_json(json_text: str) -> list[dict]:
    """Parse timeline events from the JSON export of timeline.html.

    Expected format: {events: [{date, time, category, description, ...}], evidence: [...]}
    """
    import json
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return []

    events = []

    for ev in data.get("events", []):
        events.append({
            "date": ev.get("date", ""),
            "time": ev.get("time", ""),
            "approx": ev.get("approx", "exact"),
            "category": ev.get("category", "context"),
            "description": ev.get("description", ""),
            "refs": ", ".join(ev.get("refs", [])) if isinstance(ev.get("refs"), list) else ev.get("refs", ""),
            "strength": ev.get("strength", "unassessed"),
            "contradicts": ev.get("contradicts", ""),
            "notes": ev.get("notes", ""),
            "source_file": ev.get("filepath", ""),
            "source_type": "timeline_html",
        })

    # Also import evidence items as events if they have dates
    for evi in data.get("evidence", []):
        if evi.get("date"):
            events.append({
                "date": evi.get("date", ""),
                "time": "",
                "approx": "exact",
                "category": evi.get("type", "context"),
                "description": evi.get("description", ""),
                "refs": "",
                "strength": "unassessed",
                "contradicts": "",
                "notes": evi.get("notes", ""),
                "source_file": evi.get("filepath", ""),
                "source_type": "timeline_html_evidence",
            })

    return events


def _hash_file(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _ext_to_mime(ext: str) -> str:
    mime_map = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".rtf": "application/rtf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".heic": "image/heic",
        ".eml": "message/rfc822",
        ".htm": "text/html",
        ".html": "text/html",
    }
    return mime_map.get(ext, "application/octet-stream")
