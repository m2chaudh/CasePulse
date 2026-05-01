"""Tests for background OCR job enqueue and run."""
import json
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
