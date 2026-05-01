"""Tamper-evident hash chain over the audit_log table.

Each row's row_hash = SHA-256(prev_hash || canonical_row_data).
Verification walks the chain and recomputes hashes — any tampering
breaks the chain at the modified row.
"""
import hashlib
import json
from typing import Optional

from casepulse.storage.database import Database


def _canonicalize(row_data: dict) -> bytes:
    """Stable serialization for hashing."""
    return json.dumps(row_data, sort_keys=True, default=str).encode("utf-8")


def get_last_hash(db: Database) -> Optional[str]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT row_hash FROM audit_log WHERE row_hash IS NOT NULL "
        "ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else None


def log_chained(db: Database, *, action: str, details: dict) -> int:
    """Insert a hash-chained audit_log row. Returns inserted row id."""
    conn = db._get_conn()
    cur = conn.cursor()
    prev = get_last_hash(db)
    row_data = {"action": action, "details": details}
    base = (prev or "") + _canonicalize(row_data).decode()
    row_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()
    cur.execute("""
        INSERT INTO audit_log (action, details, prev_hash, row_hash)
        VALUES (?, ?, ?, ?)
    """, (action, json.dumps(details), prev, row_hash))
    conn.commit()
    return cur.lastrowid


def verify_chain(db: Database) -> bool:
    """Walk the chain end-to-end, recomputing each row_hash.

    Pre-W1 rows (NULL row_hash) are skipped — the chain starts at the first
    chained row. Malformed details JSON is treated as a plain string for
    canonicalization rather than raising.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, action, details, prev_hash, row_hash
        FROM audit_log
        WHERE row_hash IS NOT NULL
        ORDER BY id
    """)
    expected_prev = None
    for row_id, action, details_json, stored_prev, stored_row in cur.fetchall():
        if stored_prev != expected_prev:
            return False
        try:
            details = json.loads(details_json) if details_json else {}
        except json.JSONDecodeError:
            details = details_json
        row_data = {"action": action, "details": details}
        base = (stored_prev or "") + _canonicalize(row_data).decode()
        recomputed = hashlib.sha256(base.encode("utf-8")).hexdigest()
        if recomputed != stored_row:
            return False
        expected_prev = stored_row
    return True
