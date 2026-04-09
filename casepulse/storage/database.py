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

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_file TEXT,
    platform TEXT,
    chat_name TEXT,
    sender TEXT,
    sender_mapped_email TEXT,
    timestamp TEXT,
    message_text TEXT,
    has_media INTEGER DEFAULT 0,
    media_type TEXT,
    media_path TEXT,
    content_hash TEXT,
    is_system INTEGER DEFAULT 0,
    import_batch TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    source_type TEXT,
    platform TEXT,
    chat_name TEXT,
    message_count INTEGER DEFAULT 0,
    date_start TEXT,
    date_end TEXT,
    participants TEXT,
    imported_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat_sender_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_sender TEXT NOT NULL,
    platform TEXT,
    mapped_email TEXT,
    mapped_category TEXT DEFAULT 'other',
    display_label TEXT,
    UNIQUE(chat_sender, platform)
);

CREATE TABLE IF NOT EXISTS saved_selections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sender_ids TEXT NOT NULL,
    sender_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    case_type TEXT NOT NULL,
    case_number TEXT DEFAULT '',
    description TEXT DEFAULT '',
    exhibit_format TEXT DEFAULT 'alpha',
    exhibit_prefix TEXT DEFAULT '',
    next_exhibit_num INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evidence_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    case_id INTEGER REFERENCES cases(id),
    legal_issue TEXT DEFAULT '',
    exhibit_label TEXT DEFAULT '',
    flag TEXT DEFAULT 'none',
    collection TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(item_type, item_id, case_id)
);

CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type TEXT NOT NULL,
    item_id INTEGER NOT NULL,
    case_id INTEGER REFERENCES cases(id),
    note_text TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_email);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date_received);
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_content_hash ON emails(content_hash);
CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments(email_id);
CREATE INDEX IF NOT EXISTS idx_attachments_hash ON attachments(content_hash);
CREATE INDEX IF NOT EXISTS idx_senders_selected ON senders(selected);
CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_chat_messages_sender ON chat_messages(sender);
CREATE INDEX IF NOT EXISTS idx_chat_messages_source ON chat_messages(source_type);
CREATE INDEX IF NOT EXISTS idx_evidence_tags_item ON evidence_tags(item_type, item_id);
CREATE INDEX IF NOT EXISTS idx_evidence_tags_case ON evidence_tags(case_id);
CREATE INDEX IF NOT EXISTS idx_annotations_item ON annotations(item_type, item_id);
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

    # ── Saved selection views ──

    def save_selection(self, name: str):
        """Save current sender selections as a named view."""
        with self._get_conn() as conn:
            selected = conn.execute(
                "SELECT id FROM senders WHERE selected = 1"
            ).fetchall()
            ids = json.dumps([r["id"] for r in selected])
            conn.execute(
                """INSERT INTO saved_selections (name, sender_ids, sender_count, updated_at)
                   VALUES (?, ?, ?, datetime('now'))
                   ON CONFLICT(name) DO UPDATE SET
                   sender_ids = excluded.sender_ids,
                   sender_count = excluded.sender_count,
                   updated_at = datetime('now')""",
                (name, ids, len(selected))
            )

    def load_selection(self, name: str, merge: bool = False):
        """Load a saved selection view.

        If merge=False, clears current selections first (replace).
        If merge=True, adds saved selections to current ones.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT sender_ids FROM saved_selections WHERE name = ?", (name,)
            ).fetchone()
            if not row:
                return

            ids = json.loads(row["sender_ids"])
            if not merge:
                conn.execute("UPDATE senders SET selected = 0")
            for sid in ids:
                conn.execute("UPDATE senders SET selected = 1 WHERE id = ?", (sid,))

    def get_saved_selections(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM saved_selections ORDER BY updated_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_saved_selection(self, name: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM saved_selections WHERE name = ?", (name,))

    def set_sender_category(self, sender_id: int, category):
        """Set sender category. Accepts a string or list of strings (stored as JSON array)."""
        if isinstance(category, list):
            value = json.dumps(category)
        else:
            value = category
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE senders SET category = ? WHERE id = ?",
                (value, sender_id)
            )

    @staticmethod
    def parse_categories(category_value) -> list:
        """Parse category field — handles both old single-string and new JSON array format."""
        if not category_value:
            return []
        if isinstance(category_value, list):
            return category_value
        try:
            parsed = json.loads(category_value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        # Old format: single string
        if category_value and category_value != "other":
            return [category_value]
        return []

    def bulk_update_sender_selection(self, selections: dict[int, bool]):
        with self._get_conn() as conn:
            for sender_id, selected in selections.items():
                conn.execute(
                    "UPDATE senders SET selected = ? WHERE id = ?",
                    (1 if selected else 0, sender_id)
                )

    # ── Email operations ──

    @staticmethod
    def normalize_subject(subject: str) -> str:
        """Strip RE:/FW:/Fwd: prefixes for dedup matching."""
        import re
        s = subject.strip()
        # Repeatedly strip common prefixes
        while True:
            m = re.match(r"^(?:RE|Re|re|FW|Fw|fw|FWD|Fwd|fwd)\s*:\s*", s)
            if m:
                s = s[m.end():]
            else:
                break
        return s.strip()

    @staticmethod
    def compute_content_hash(body_text: str, subject: str, sender: str) -> str:
        """Compute hash for cross-account dedup. Normalizes subject to handle FW:/RE: prefixes."""
        normalized_subject = Database.normalize_subject(subject)
        # Use only subject + body for hash (not sender) so forwards from different senders match
        content = f"{normalized_subject}|{body_text}"
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

    def content_hash_exists(self, content_hash: str, exclude_account_id: Optional[int] = None) -> Optional[int]:
        """Check if an email with this content hash already exists (cross-account dedup).

        Returns the existing email ID, or None.
        """
        with self._get_conn() as conn:
            if exclude_account_id:
                row = conn.execute(
                    "SELECT id FROM emails WHERE content_hash = ? AND account_id != ? LIMIT 1",
                    (content_hash, exclude_account_id)
                ).fetchone()
            else:
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
            # Chat stats
            chat_msgs = conn.execute("SELECT COUNT(*) as cnt FROM chat_messages WHERE is_system = 0").fetchone()["cnt"]
            chat_imports = conn.execute("SELECT COUNT(*) as cnt FROM chat_imports").fetchone()["cnt"]

            return {
                "total_emails": emails,
                "total_attachments": attachments,
                "duplicate_attachments": dup_attachments,
                "connected_accounts": accounts,
                "selected_senders": senders,
                "earliest_email": date_range["earliest"],
                "latest_email": date_range["latest"],
                "total_chat_messages": chat_msgs,
                "chat_imports": chat_imports,
            }

    # ── Chat message operations ──

    def insert_chat_message(self, **kwargs) -> int:
        fields = [
            "source_type", "source_file", "platform", "chat_name",
            "sender", "sender_mapped_email", "timestamp", "message_text",
            "has_media", "media_type", "media_path", "content_hash",
            "is_system", "import_batch",
        ]
        data = {f: kwargs.get(f) for f in fields}
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        with self._get_conn() as conn:
            cur = conn.execute(
                f"INSERT INTO chat_messages ({cols}) VALUES ({placeholders})",
                list(data.values())
            )
            return cur.lastrowid

    def insert_chat_import(self, source_file: str, source_type: str,
                           platform: str, chat_name: str,
                           message_count: int, date_start: str,
                           date_end: str, participants: list[str]) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO chat_imports
                   (source_file, source_type, platform, chat_name,
                    message_count, date_start, date_end, participants)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_file, source_type, platform, chat_name,
                 message_count, date_start, date_end, json.dumps(participants))
            )
            return cur.lastrowid

    def get_chat_imports(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_imports ORDER BY imported_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_chat_messages(self, sender: Optional[str] = None,
                          date_start: Optional[str] = None,
                          date_end: Optional[str] = None,
                          keyword: Optional[str] = None,
                          platform: Optional[str] = None,
                          include_system: bool = False,
                          limit: int = 5000) -> list[dict]:
        conditions = []
        params = []

        if not include_system:
            conditions.append("is_system = 0")
        if sender:
            conditions.append("(sender = ? OR sender_mapped_email = ?)")
            params.extend([sender, sender])
        if date_start:
            conditions.append("timestamp >= ?")
            params.append(date_start)
        if date_end:
            conditions.append("timestamp <= ?")
            params.append(date_end)
        if keyword:
            conditions.append("message_text LIKE ?")
            params.append(f"%{keyword}%")
        if platform:
            conditions.append("platform = ?")
            params.append(platform)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM chat_messages WHERE {where} ORDER BY timestamp ASC LIMIT ?",
                params
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_chat_import(self, import_id: int):
        """Delete a chat import and all its messages."""
        with self._get_conn() as conn:
            imp = conn.execute(
                "SELECT source_file FROM chat_imports WHERE id = ?", (import_id,)
            ).fetchone()
            if imp:
                conn.execute(
                    "DELETE FROM chat_messages WHERE source_file = ?",
                    (imp["source_file"],)
                )
            conn.execute("DELETE FROM chat_imports WHERE id = ?", (import_id,))

    # ── Chat sender mapping ──

    def upsert_chat_sender_map(self, chat_sender: str, platform: str,
                                mapped_email: str = "", category: str = "other",
                                label: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO chat_sender_map (chat_sender, platform, mapped_email, mapped_category, display_label)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(chat_sender, platform) DO UPDATE SET
                   mapped_email = excluded.mapped_email,
                   mapped_category = excluded.mapped_category,
                   display_label = excluded.display_label""",
                (chat_sender, platform, mapped_email, category, label)
            )

    def get_chat_sender_maps(self, platform: Optional[str] = None) -> list[dict]:
        with self._get_conn() as conn:
            if platform:
                rows = conn.execute(
                    "SELECT * FROM chat_sender_map WHERE platform = ?", (platform,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM chat_sender_map").fetchall()
            return [dict(r) for r in rows]

    # ── Unified timeline ──

    def get_unified_timeline(self, date_start: Optional[str] = None,
                              date_end: Optional[str] = None,
                              keyword: Optional[str] = None,
                              sender: Optional[str] = None,
                              limit: int = 5000) -> list[dict]:
        """Get combined email + chat timeline, sorted chronologically."""
        items = []

        # Build account lookup
        account_map = {}
        for acc in self.get_accounts():
            account_map[acc["id"]] = acc["email"]

        # Emails
        emails = self.get_emails(
            date_start=date_start, date_end=date_end,
            keyword=keyword, sender_email=sender, limit=limit,
        )
        for e in emails:
            items.append({
                "type": "email",
                "timestamp": e.get("date_received", ""),
                "sender": e.get("sender_email", ""),
                "sender_name": e.get("sender_name", ""),
                "subject": e.get("subject", ""),
                "body_preview": (e.get("body_text", "") or "")[:300],
                "direction": e.get("direction", ""),
                "is_forwarded": bool(e.get("is_forwarded")),
                "has_attachments": bool(e.get("has_attachments")),
                "source_id": e["id"],
                "platform": "email",
                "account": account_map.get(e.get("account_id"), ""),
            })

        # Chat messages
        chat_msgs = self.get_chat_messages(
            date_start=date_start, date_end=date_end,
            keyword=keyword, sender=sender, limit=limit,
        )
        for m in chat_msgs:
            items.append({
                "type": "chat",
                "timestamp": m.get("timestamp", ""),
                "sender": m.get("sender", ""),
                "sender_name": m.get("sender", ""),
                "subject": m.get("chat_name", ""),
                "body_preview": (m.get("message_text", "") or "")[:300],
                "direction": "",
                "is_forwarded": False,
                "has_attachments": bool(m.get("has_media")),
                "source_id": m["id"],
                "platform": m.get("platform", "chat"),
            })

        # Sort by timestamp
        items.sort(key=lambda x: x["timestamp"] or "")
        return items[:limit]

    # ── Case operations ──

    def create_case(self, name: str, case_type: str, case_number: str = "",
                    description: str = "", exhibit_format: str = "alpha",
                    exhibit_prefix: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO cases (name, case_type, case_number, description,
                   exhibit_format, exhibit_prefix)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, case_type, case_number, description, exhibit_format, exhibit_prefix)
            )
            return cur.lastrowid

    def get_cases(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM cases ORDER BY created_at").fetchall()
            return [dict(r) for r in rows]

    def get_case(self, case_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            return dict(row) if row else None

    def update_case(self, case_id: int, **kwargs):
        allowed = {"name", "case_number", "description", "exhibit_format", "exhibit_prefix", "next_exhibit_num"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE cases SET {set_clause} WHERE id = ?",
                list(updates.values()) + [case_id]
            )

    def delete_case(self, case_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM evidence_tags WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM annotations WHERE case_id = ?", (case_id,))
            conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))

    def get_next_exhibit_number(self, case_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT next_exhibit_num FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
            if row:
                num = row["next_exhibit_num"]
                conn.execute(
                    "UPDATE cases SET next_exhibit_num = ? WHERE id = ?",
                    (num + 1, case_id)
                )
                return num
            return 1

    # ── Evidence tag operations ──

    def tag_evidence(self, item_type: str, item_id: int, case_id: int,
                     legal_issue: str = "", exhibit_label: str = "",
                     flag: str = "none", collection: str = "") -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO evidence_tags (item_type, item_id, case_id,
                   legal_issue, exhibit_label, flag, collection)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(item_type, item_id, case_id) DO UPDATE SET
                   legal_issue = excluded.legal_issue,
                   exhibit_label = excluded.exhibit_label,
                   flag = excluded.flag,
                   collection = excluded.collection""",
                (item_type, item_id, case_id, legal_issue, exhibit_label, flag, collection)
            )
            return cur.lastrowid

    def get_evidence_tag(self, item_type: str, item_id: int, case_id: int) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_tags WHERE item_type = ? AND item_id = ? AND case_id = ?",
                (item_type, item_id, case_id)
            ).fetchone()
            return dict(row) if row else None

    def get_evidence_tags_for_case(self, case_id: int, legal_issue: Optional[str] = None,
                                    flag: Optional[str] = None,
                                    collection: Optional[str] = None) -> list[dict]:
        conditions = ["case_id = ?"]
        params = [case_id]
        if legal_issue:
            conditions.append("legal_issue = ?")
            params.append(legal_issue)
        if flag:
            conditions.append("flag = ?")
            params.append(flag)
        if collection:
            conditions.append("collection = ?")
            params.append(collection)
        where = " AND ".join(conditions)
        with self._get_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM evidence_tags WHERE {where} ORDER BY created_at",
                params
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_collections(self, case_id: int) -> list[str]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT DISTINCT collection FROM evidence_tags
                   WHERE case_id = ? AND collection != '' ORDER BY collection""",
                (case_id,)
            ).fetchall()
            return [r["collection"] for r in rows]

    def bulk_tag_evidence(self, items: list[tuple], case_id: int,
                          legal_issue: str = "", flag: str = "none",
                          collection: str = ""):
        """Tag multiple items at once. items = [(item_type, item_id), ...]"""
        for item_type, item_id in items:
            self.tag_evidence(item_type, item_id, case_id,
                              legal_issue=legal_issue, flag=flag, collection=collection)

    def remove_evidence_tag(self, tag_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM evidence_tags WHERE id = ?", (tag_id,))

    # ── Annotation operations ──

    def add_annotation(self, item_type: str, item_id: int, note_text: str,
                       case_id: Optional[int] = None) -> int:
        with self._get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO annotations (item_type, item_id, case_id, note_text) VALUES (?, ?, ?, ?)",
                (item_type, item_id, case_id, note_text)
            )
            return cur.lastrowid

    def get_annotations(self, item_type: str, item_id: int,
                        case_id: Optional[int] = None) -> list[dict]:
        with self._get_conn() as conn:
            if case_id:
                rows = conn.execute(
                    """SELECT * FROM annotations
                       WHERE item_type = ? AND item_id = ? AND case_id = ?
                       ORDER BY created_at DESC""",
                    (item_type, item_id, case_id)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM annotations WHERE item_type = ? AND item_id = ? ORDER BY created_at DESC",
                    (item_type, item_id)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_all_annotations_for_case(self, case_id: int) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM annotations WHERE case_id = ? ORDER BY created_at DESC",
                (case_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_annotation(self, annotation_id: int):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))

    def search_annotations(self, query: str, case_id: Optional[int] = None) -> list[dict]:
        with self._get_conn() as conn:
            if case_id:
                rows = conn.execute(
                    "SELECT * FROM annotations WHERE case_id = ? AND note_text LIKE ? ORDER BY created_at DESC",
                    (case_id, f"%{query}%")
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM annotations WHERE note_text LIKE ? ORDER BY created_at DESC",
                    (f"%{query}%",)
                ).fetchall()
            return [dict(r) for r in rows]

    # ── App settings (PIN lock, preferences) ──

    def set_setting(self, key: str, value: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value)
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    # ── Audit log ──

    def log_action(self, action: str, details: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (action, details) VALUES (?, ?)",
                (action, details)
            )

    def get_audit_log(self, limit: int = 100) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
