"""Background job runner — runs fetches in daemon threads with DB-based progress."""
from __future__ import annotations

import json
import threading
from typing import Optional

from casepulse.storage.database import Database
from casepulse.config import get_data_dir

# Track running threads so we don't start duplicates
_running_threads: dict[int, threading.Thread] = {}


def start_fetch_job(db: Database, accounts: list[dict],
                    date_start: str, date_end: str,
                    sender_emails: Optional[list[str]] = None,
                    keywords: Optional[list[str]] = None) -> int:
    """Start a background email fetch job.

    Returns the job ID. Progress is written to the background_jobs table.
    """
    # Check for already running fetch
    running = db.get_running_jobs("fetch_emails")
    if running:
        return running[0]["id"]  # Return existing job

    account_names = ", ".join(a["email"] for a in accounts)
    job_id = db.create_job(
        job_type="fetch_emails",
        account_email=account_names,
        details=json.dumps({
            "date_start": date_start,
            "date_end": date_end,
            "accounts": [a["email"] for a in accounts],
            "sender_count": len(sender_emails) if sender_emails else 0,
        }),
    )

    # Capture sender_emails explicitly to avoid closure issues
    _sender_emails = list(sender_emails) if sender_emails else None
    _keywords = list(keywords) if keywords else None

    def _run():
        # Create a fresh DB connection for this thread
        _db = Database()
        total_fetched = 0
        total_attachments = 0
        total_skipped = 0
        errors = []

        # Log what filter we're using
        filter_info = f"sender_filter={len(_sender_emails) if _sender_emails else 'NONE'}"
        _db.update_job_progress(job_id, f"Starting... {filter_info}")

        try:
            for acc in accounts:
                # Check if cancelled
                job = _db.get_job(job_id)
                if job and job["status"] == "cancelled":
                    _db.update_job_progress(job_id, f"Cancelled. {total_fetched} emails saved.")
                    _db.complete_job(job_id, "cancelled",
                                     json.dumps({"fetched": total_fetched, "skipped": total_skipped,
                                                 "attachments": total_attachments}))
                    return

                _db.update_job_progress(job_id, f"Fetching {acc['email']}... {filter_info}")

                try:
                    if acc["provider"] == "microsoft":
                        from casepulse.auth.microsoft import MicrosoftAuth
                        auth = MicrosoftAuth(client_id=acc.get("client_id", ""), account_email=acc["email"])
                        token = auth.get_access_token()
                        if not token:
                            errors.append(f"Token expired for {acc['email']}")
                            continue

                        from casepulse.email_engine.microsoft_fetcher import MicrosoftFetcher
                        fetcher = MicrosoftFetcher(token, acc["id"], _db)

                        def _ms_progress(msg, a=acc["email"]):
                            _db.update_job_progress(
                                job_id,
                                f"[{a}] {msg} | Total: {total_fetched} stored"
                            )

                        result = fetcher.fetch_emails(
                            date_start, date_end,
                            sender_emails=_sender_emails,
                            keywords=_keywords,
                            progress_cb=_ms_progress,
                        )

                    elif acc["provider"] == "google":
                        from casepulse.auth.google_auth import GoogleAuth
                        creds_file = acc.get("token_file", "")
                        auth = GoogleAuth(credentials_file=creds_file, account_email=acc["email"])
                        service = auth.get_service()
                        if not service:
                            errors.append(f"Token expired for {acc['email']}")
                            continue

                        from casepulse.email_engine.gmail_fetcher import GmailFetcher
                        fetcher = GmailFetcher(service, acc["id"], _db)

                        def _gmail_progress(msg, a=acc["email"]):
                            _db.update_job_progress(
                                job_id,
                                f"[{a}] {msg} | Total: {total_fetched} stored"
                            )

                        result = fetcher.fetch_emails(
                            date_start, date_end,
                            sender_emails=_sender_emails,
                            keywords=_keywords,
                            progress_cb=_gmail_progress,
                        )

                    total_fetched += result["emails_fetched"]
                    total_attachments += result["attachments_downloaded"]
                    total_skipped += result["duplicates_skipped"]
                    errors.extend(result.get("errors", []))

                    _db.update_job_progress(
                        job_id,
                        f"Done with {acc['email']}: {result['emails_fetched']} emails. "
                        f"Total: {total_fetched} stored, {total_skipped} skipped"
                    )

                except Exception as e:
                    errors.append(f"{acc['email']}: {str(e)}")

            _db.complete_job(job_id, "completed", json.dumps({
                "fetched": total_fetched,
                "skipped": total_skipped,
                "attachments": total_attachments,
                "errors": errors[:20],
            }))

        except Exception as e:
            _db.complete_job(job_id, "failed", json.dumps({"error": str(e)}))

    thread = threading.Thread(target=_run, daemon=True, name=f"fetch-job-{job_id}")
    thread.start()
    _running_threads[job_id] = thread

    return job_id


def get_job_status(db: Database, job_id: int) -> Optional[dict]:
    """Get current status of a background job."""
    return db.get_job(job_id)


def cancel_job(db: Database, job_id: int):
    """Cancel a running job. The thread checks this flag periodically."""
    db.cancel_job(job_id)


# ── Background OCR jobs (Task 3.5) ──────────────────────────────────────────

def enqueue_job(db: Database, *, job_type: str, payload: dict) -> int:
    """Enqueue a background job with 'pending' status.

    Payload is serialised as JSON into the ``details`` column (which is the
    existing column used by all background_jobs rows).  Returns the new job ID.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO background_jobs (job_type, status, details, started_at)
        VALUES (?, 'pending', ?, datetime('now'))
        """,
        (job_type, json.dumps(payload)),
    )
    conn.commit()
    return cur.lastrowid


def run_ocr_jobs(db: Database, max_jobs: int = 10) -> int:
    """Drain up to *max_jobs* pending OCR jobs.  Returns number processed."""
    from casepulse.case_theory.metadata_extractor import run_ocr_image

    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, details FROM background_jobs
        WHERE job_type = 'ocr_attachment' AND status = 'pending'
        LIMIT ?
        """,
        (max_jobs,),
    )
    jobs = cur.fetchall()
    processed = 0
    for job_id, details_str in jobs:
        try:
            payload = json.loads(details_str or "{}")
        except (json.JSONDecodeError, TypeError):
            payload = {}
        att_id = payload.get("attachment_id")
        if att_id is None:
            cur.execute(
                "UPDATE background_jobs SET status = 'failed' WHERE id = ?",
                (job_id,),
            )
            processed += 1
            continue

        cur.execute("SELECT file_path FROM attachments WHERE id = ?", (att_id,))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "UPDATE background_jobs SET status = 'failed', "
                "completed_at = datetime('now') WHERE id = ?",
                (job_id,),
            )
            processed += 1
            continue

        text, conf = run_ocr_image(row[0])
        if text:
            cur.execute(
                "UPDATE attachments SET extracted_text = ? WHERE id = ?",
                (text, att_id),
            )
            status = "completed" if conf >= 0.6 else "needs_review"
        else:
            status = "failed"
        cur.execute(
            "UPDATE background_jobs SET status = ?, completed_at = datetime('now') "
            "WHERE id = ?",
            (status, job_id),
        )
        processed += 1

    conn.commit()
    return processed
