"""Extract text content from email attachments (PDF, DOCX, TXT)."""
from __future__ import annotations

import os
from pathlib import Path


def extract_text(file_path: str, content_type: str = "") -> str:
    """Extract text from a file based on its type.

    Supports: PDF, DOCX, DOC, TXT, RTF, CSV
    """
    path = Path(file_path)
    if not path.exists():
        return ""

    ext = path.suffix.lower()
    content_type = content_type.lower()

    try:
        if ext == ".pdf" or "pdf" in content_type:
            return _extract_pdf(path)
        elif ext in (".docx",) or "wordprocessingml" in content_type:
            return _extract_docx(path)
        elif ext in (".txt", ".text", ".log", ".md", ".csv", ".tsv"):
            return _extract_text_file(path)
        elif ext == ".rtf" or "rtf" in content_type:
            return _extract_text_file(path)  # Basic RTF as text
        elif ext in (".htm", ".html") or "html" in content_type:
            return _extract_html(path)
        elif ext in (".eml", ".msg"):
            return _extract_eml(path)
    except Exception as e:
        return f"[Extraction error: {str(e)}]"

    return ""


def _extract_pdf(path: Path) -> str:
    """Extract text from PDF using pdfplumber."""
    import pdfplumber
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def _extract_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    import docx
    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    # Also extract from tables
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                paragraphs.append(" | ".join(cells))
    return "\n".join(paragraphs)


def _extract_text_file(path: Path) -> str:
    """Extract text from plain text files."""
    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return ""


def _extract_html(path: Path) -> str:
    """Extract text from HTML files."""
    from casepulse.email_engine.parser import html_to_text
    html = _extract_text_file(path)
    return html_to_text(html)


def _extract_eml(path: Path) -> str:
    """Extract text from .eml files."""
    import email
    from email import policy
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw, policy=policy.default)
    body = msg.get_body(preferencelist=("plain", "html"))
    if body:
        content = body.get_content()
        if body.get_content_type() == "text/html":
            from casepulse.email_engine.parser import html_to_text
            return html_to_text(content)
        return content
    return ""


def get_file_size_human(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
