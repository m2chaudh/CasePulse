"""SQLite database for CasePulse email storage."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from casepulse.config import get_data_dir

DB_PATH = get_data_dir() / "db" / "casepulse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    token_file TEXT,
    client_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS senders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    selected INTEGER DEFAULT 0,
    category TEXT DEFAULT 'other',
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT,
    content_hash TEXT,
    account_id INTEGER REFERENCES accounts(id),
    subject TEXT,
    sender_email TEXT,
    sender_name TEXT,
    recipients TEXT,
    cc TEXT,
    date_sent TEXT,
    date_received TEXT,
    body_text TEXT,
    body_html TEXT,
    folder TEXT,
    is_forwarded INTEGER DEFAULT 0,
    is_reply INTEGER DEFAULT 0,
    parent_email_id INTEGER REFERENCES emails(id),
    original_sender TEXT,
    original_date TEXT,
    direction TEXT,
    raw_headers TEXT,
    importance TEXT,
    has_attachments INTEGER DEFAULT 0,
    provider_msg_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(message_id, account_id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    filename TEXT,
    content_type TEXT,
    size_bytes INTEGER,
    file_path TEXT,
    extracted_text TEXT,
    content_hash TEXT,
    is_duplicate INTEGER DEFAULT 0,
    duplicate_of INTEGER REFERENCES attachments(id),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL UNIQUE,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    started_at TEXT,
    completed_at TEXT,
    emails_fetched INTEGER DEFAULT 0,
    attachments_downloaded INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0,
    errors TEXT,
    status TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_email);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date_received);
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_content_hash ON emails(content_hash);
CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id);
CREATE INDEX IF NOT EXISTS idx_attachments_hash ON attachments(content_hash);
CREATE INDEX IF NOT EXISTS idx_senders_selected ON senders(selected);
"""


class Database:
    """SQLite database wrapper for CasePulse."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)

    # ── Account operations ──

    def add_account(self, provider: str, email: str, display_name: str = "",
                    token_file: str = "", client_id: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT OR REPLACE INTO accounts (provider, email, display_name, token_file, client_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (provider, email, display_name, token_file, client_id)
            )
            return cur.lastrowid

    def get_accounts(self, provider: Optional[str] = None) -> list[dict]:
        with self._get_conn() as conn:
            if provider:
                rows = conn.execute(
                    "SELECT * FROM accounts WHERE provider = ? ORDER BY email", (provider,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM accounts ORDER BY provider, email").fetchall()
            return [dict(r) for r in rows]

    def get_account_by_email(self, email: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    def delete_account(self, account_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM emails WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))

    def update_last_synced(self, account_id: int):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE accounts SET last_synced = datetime('now') WHERE id = ?",
                (account_id,)
            )

    # ── Sender operations ──

    def upsert_sender(self, email: str, display_name: str = "",
                      category: str = "other") -> int:
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM senders WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                if display_name:
                    conn.execute(
                        "UPDATE senders SET display_name = ? WHERE email = ?",
                        (display_name, email)
                    )
                return existing["id"]
            cur = conn.execute(
                "INSERT INTO senders (email, display_name, category) VALUES (?, ?, ?)",
                (email, display_name, category)
            )
            return cur.lastrowid

    def get_senders(self, selected_only: bool = False) -> list[dict]:
        with self._get_conn() as conn:
            if selected_only:
                rows = conn.execute(
                    "SELECT * FROM senders WHERE selected = 1 ORDER BY email"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM senders ORDER BY email").fetchall()
            return [dict(r) for r in rows]

    def set_sender_selected(self, sender_id: int, selected: bool):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE senders SET selected = ? WHERE id = ?",
                (1 if selected else 0, sender_id)
            )

    def set_sender_category(self, sender_id: int, category: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE senders SET category = ? WHERE id = ?",
                (category, sender_id)
            )

    def bulk_update_sender_selection(self, selections: dict[int, bool]):
        with self._get_conn() as conn:
            for sender_id, selected in selections.items():
                conn.execute(
                    "UPDATE senders SET selected = ? WHERE id = ?",
                    (1 if selected else 0, sender_id)
                )

    # ── Email operations ──

    @staticmethod
    def compute_content_hash(body_text: str, subject: str, sender: str) -> str:
        content = f"{subject}|{sender}|{body_text}"
        return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()

    def email_exists(self, message_id: str, account_id: int) -> bool:
        if not message_id:
            return False
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM emails WHERE message_id = ? AND account_id = ?",
                (message_id, account_id)
            ).fetchone()
            return row is not None

    def content_hash_exists(self, content_hash: str) -> Optional[int]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM emails WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            ).fetchone()
            return row["id"] if row else None

    def insert_email(self, **kwargs) -> int:
        fields = [
            "message_id", "content_hash", "account_id", "subject",
            "sender_email", "sender_name", "recipients", "cc",
            "date_sent", "date_received", "body_text", "body_html",
            "folder", "is_forwarded", "is_reply", "parent_email_id",
            "original_sender", "original_date", "direction",
            "raw_headers", "importance", "has_attachments", "provider_msg_id"
        ]
        data = {f: kwargs.get(f) for f in fields}
        # Serialize lists/dicts to JSON
        for json_field in ["recipients", "cc", "raw_headers"]:
            if isinstance(data.get(json_field), (list, dict)):
                data[json_field] = json.dumps(data[json_field])

        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        with self._get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO emails ({cols}) VALUES ({placeholders})",
                list(data.values())
            )
            return cur.lastrowid

    def get_emails(self, sender_email: Optional[str] = None,
                   date_start: Optional[str] = None,
                   date_end: Optional[str] = None,
                   keyword: Optional[str] = None,
                   direction: Optional[str] = None,
                   has_attachments: Optional[bool] = None,
                   limit: int = 1000,
                   offset: int = 0) -> list[dict]:
        conditions = []
        params = []

        if sender_email:
            conditions.append("(sender_email = ? OR recipients LIKE ? OR original_sender = ?)")
            params.extend([sender_email, f"%{sender_email}%", sender_email])
        if date_start:
            conditions.append("date_received >= ?")
            params.append(date_start)
        if date_end:
            conditions.append("date_received <= ?")
            params.append(date_end)
        if keyword:
            conditions.append("(subject LIKE ? OR body_text LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if direction:
            conditions.append("direction = ?")
            params.append(direction)
        if has_attachments is not None:
            conditions.append("has_attachments = ?")
            params.append(1 if has_attachments else 0)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(
                f"""SELECT * FROM emails WHERE {where}
                    ORDER BY date_received ASC LIMIT ? OFFSET ?""",
                params
            ).fetchall()
            return [dict(r) for r in rows]

    def get_email_by_id(self, email_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
            return dict(row) if row else None

    def get_email_count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM emails").fetchone()
            return row["cnt"]

    def get_unique_senders_from_emails(self, date_start: str, date_end: str) -> list[dict]:
        """Get all unique sender emails from fetched emails within a date range."""
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT sender_email, sender_name, COUNT(*) as email_count,
                          MIN(date_received) as first_email, MAX(date_received) as last_email
                   FROM emails
                   WHERE date_received >= ? AND date_received <= ?
                   GROUP BY sender_email
                   ORDER BY email_count DESC""",
                (date_start, date_end)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_contacts_from_emails(self, date_start: str, date_end: str) -> list[dict]:
        """Get all unique contacts (senders + recipients) from emails."""
        with self._get_conn() as conn:
            # Get senders
            senders = conn.execute(
                """SELECT sender_email as email, sender_name as name,
                          COUNT(*) as count, 'sender' as role
                   FROM emails
                   WHERE date_received >= ? AND date_received <= ?
                   GROUP BY sender_email""",
                (date_start, date_end)
            ).fetchall()

            contacts = {}
            for row in senders:
                r = dict(row)
                contacts[r["email"]] = {
                    "email": r["email"],
                    "name": r["name"] or "",
                    "sent_count": r["count"],
                    "received_count": 0,
                }

            # Count received (appears in recipients)
            all_emails = conn.execute(
                """SELECT recipients FROM emails
                   WHERE date_received >= ? AND date_received <= ?""",
                (date_start, date_end)
            ).fetchall()

            for row in all_emails:
                recips = row["recipients"]
                if recips:
                    try:
                        recip_list = json.loads(recips) if isinstance(recips, str) else recips
                        for addr in recip_list:
                            email_addr = addr if isinstance(addr, str) else addr.get("email", addr.get("address", ""))
                            if email_addr and email_addr in contacts:
                                contacts[email_addr]["received_count"] += 1
                            elif email_addr:
                                contacts[email_addr] = {
                                    "email": email_addr,
                                    "name": "",
                                    "sent_count": 0,
                                    "received_count": 1,
                                }
                    except (json.JSONDecodeError, TypeError):
                        pass

            return sorted(contacts.values(), key=lambda x: x["sent_count"] + x["received_count"], reverse=True)

    # ── Attachment operations ──

    def insert_attachment(self, email_id: int, filename: str, content_type: str,
                          size_bytes: int, file_path: str, extracted_text: str = "",
                          content_hash: str = "") -> int:
        # Check for duplicate attachment by hash
        is_duplicate = False
        duplicate_of = None
        if content_hash:
            with self._get_conn() as conn:
                existing = conn.execute(
                    "SELECT id FROM attachments WHERE content_hash = ? AND is_duplicate = 0 LIMIT 1",
                    (content_hash,)
                ).fetchone()
                if existing:
                    is_duplicate = True
                    duplicate_of = existing["id"]

        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO attachments
                   (email_id, filename, content_type, size_bytes, file_path,
                    extracted_text, content_hash, is_duplicate, duplicate_of)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (email_id, filename, content_type, size_bytes, file_path,
                 extracted_text, content_hash, is_duplicate, duplicate_of)
            )
            return cur.lastrowid

    def get_attachments_for_email(self, email_id: int) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM attachments WHERE email_id = ? ORDER BY filename",
                (email_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_attachment_count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM attachments").fetchone()
            return row["cnt"]

    def get_duplicate_attachment_count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM attachments WHERE is_duplicate = 1"
            ).fetchone()
            return row["cnt"]

    # ── Keyword operations ──

    def add_keyword(self, keyword: str) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (keyword,)
            )
            return cur.lastrowid

    def get_keywords(self, active_only: bool = True) -> list[dict]:
        with self._get_conn() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM keywords WHERE active = 1 ORDER BY keyword"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM keywords ORDER BY keyword").fetchall()
            return [dict(r) for r in rows]

    def toggle_keyword(self, keyword_id: int, active: bool):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE keywords SET active = ? WHERE id = ?",
                (1 if active else 0, keyword_id)
            )

    def delete_keyword(self, keyword_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))

    # ── Sync log operations ──

    def start_sync(self, account_id: int) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO sync_log (account_id, started_at, status) VALUES (?, datetime('now'), 'running')",
                (account_id,)
            )
            return cur.lastrowid

    def update_sync(self, sync_id: int, emails_fetched: int = 0,
                    attachments_downloaded: int = 0, duplicates_skipped: int = 0):
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE sync_log SET emails_fetched = ?, attachments_downloaded = ?,
                   duplicates_skipped = ? WHERE id = ?""",
                (emails_fetched, attachments_downloaded, duplicates_skipped, sync_id)
            )

    def complete_sync(self, sync_id: int, status: str = "completed", errors: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE sync_log SET completed_at = datetime('now'),
                   status = ?, errors = ? WHERE id = ?""",
                (status, errors, sync_id)
            )

    def get_sync_history(self, account_id: Optional[int] = None, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            if account_id:
                rows = conn.execute(
                    "SELECT * FROM sync_log WHERE account_id = ? ORDER BY started_at DESC LIMIT ?",
                    (account_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sync_log ORDER BY started_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Stats ──

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            emails = conn.execute("SELECT COUNT(*) as cnt FROM emails").fetchone()["cnt"]
            attachments = conn.execute("SELECT COUNT(*) as cnt FROM attachments").fetchone()["cnt"]
            dup_attachments = conn.execute(
                "SELECT COUNT(*) as cnt FROM attachments WHERE is_duplicate = 1"
            ).fetchone()["cnt"]
            accounts = conn.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()["cnt"]
            senders = conn.execute(
                "SELECT COUNT(*) as cnt FROM senders WHERE selected = 1"
            ).fetchone()["cnt"]
            date_range = conn.execute(
                "SELECT MIN(date_received) as earliest, MAX(date_received) as latest FROM emails"
            ).fetchone()
            return {
                "total_emails": emails,
                "total_attachments": attachments,
                "duplicate_attachments": dup_attachments,
                "connected_accounts": accounts,
                "selected_senders": senders,
                "earliest_email": date_range["earliest"],
                "latest_email": date_range["latest"],
            }
