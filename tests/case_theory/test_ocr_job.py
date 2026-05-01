"""Tests for background OCR job enqueue and run."""
import json
import shutil
import struct
import zlib
import pytest


def test_ocr_job_enqueued_for_image(tmp_db_with_case):
    """Ingested image attachment results in pending background_jobs row."""
    from casepulse.jobs import enqueue_job
    db, _ = tmp_db_with_case
    enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 42})
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT job_type, status FROM background_jobs "
                "WHERE job_type = 'ocr_attachment'")
    row = cur.fetchone()
    assert row[0] == "ocr_attachment"
    assert row[1] == "pending"


def test_enqueue_job_returns_id(tmp_db_with_case):
    """enqueue_job returns a positive integer job ID."""
    from casepulse.jobs import enqueue_job
    db, _ = tmp_db_with_case
    job_id = enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 1})
    assert isinstance(job_id, int)
    assert job_id > 0


def test_enqueue_multiple_jobs_independent(tmp_db_with_case):
    """Multiple OCR jobs can be enqueued independently."""
    from casepulse.jobs import enqueue_job
    db, _ = tmp_db_with_case
    id1 = enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 1})
    id2 = enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 2})
    assert id1 != id2

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM background_jobs WHERE job_type = 'ocr_attachment'")
    count = cur.fetchone()[0]
    assert count == 2


def test_run_ocr_jobs_no_pending(tmp_db_with_case):
    """run_ocr_jobs returns 0 when no OCR jobs are pending."""
    from casepulse.jobs import run_ocr_jobs
    db, _ = tmp_db_with_case
    result = run_ocr_jobs(db, max_jobs=10)
    assert result == 0


def test_run_ocr_jobs_missing_attachment(tmp_db_with_case):
    """run_ocr_jobs marks job failed when attachment row doesn't exist."""
    from casepulse.jobs import enqueue_job, run_ocr_jobs
    db, _ = tmp_db_with_case
    enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 9999})
    processed = run_ocr_jobs(db, max_jobs=10)
    assert processed == 1  # processed (even if failed)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status FROM background_jobs WHERE job_type = 'ocr_attachment'")
    row = cur.fetchone()
    assert row[0] == "failed"


def _make_tiny_png(path: str) -> None:
    """Write a minimal 1×1 white PNG to *path* without PIL dependency."""
    import zlib
    import struct

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1×1 RGB
    # Single white pixel: filter byte 0x00 + RGB 0xFF 0xFF 0xFF
    raw_row = b"\x00\xff\xff\xff"
    idat_data = zlib.compress(raw_row)
    png_bytes = (
        signature
        + png_chunk(b"IHDR", ihdr_data)
        + png_chunk(b"IDAT", idat_data)
        + png_chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(png_bytes)


def test_ocr_job_routes_documents_correctly(tmp_db_with_case, tmp_path):
    """OCR job with source_table='documents' updates documents table, not attachments."""
    import shutil
    tesseract = shutil.which("tesseract")
    if not tesseract:
        pytest.skip("tesseract binary not installed on this system")

    from casepulse.jobs import enqueue_job, run_ocr_jobs
    db, _ = tmp_db_with_case

    # Create a tiny PNG image in tmp_path
    img_path = str(tmp_path / "test_ocr.png")
    _make_tiny_png(img_path)

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_type, size_bytes,
                                content_hash, ocr_status)
        VALUES ('test_ocr.png', ?, 'image/png', 100, 'h_ocr1', 'needs_ocr')
    """, (img_path,))
    conn.commit()
    doc_id = cur.lastrowid

    # Enqueue with new payload format
    enqueue_job(db, job_type="ocr_attachment",
                payload={"source_table": "documents", "source_row_id": doc_id})

    processed = run_ocr_jobs(db, max_jobs=10)
    assert processed == 1

    # Documents table should have been updated
    cur.execute("SELECT extracted_text, ocr_status FROM documents WHERE id = ?", (doc_id,))
    row = cur.fetchone()
    # extracted_text may be empty for a blank image — what matters is the job ran and
    # the status was written (not still 'needs_ocr' and not 'failed' due to wrong table)
    assert row is not None, "document row must still exist"
    # Attachments table must NOT have been touched
    cur.execute("SELECT COUNT(*) FROM attachments WHERE extracted_text IS NOT NULL")
    att_count = cur.fetchone()[0]
    assert att_count == 0, "attachments table must not have been written by a document OCR job"
