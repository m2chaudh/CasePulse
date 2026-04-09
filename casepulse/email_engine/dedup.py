"""Cross-account email deduplication."""
from __future__ import annotations

from casepulse.storage.database import Database


def find_cross_account_duplicates(db: Database) -> list[dict]:
    """Find emails that appear in multiple accounts (same content_hash).

    Returns list of duplicate groups: [{hash, emails: [{id, account, subject, date}]}]
    """
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT content_hash, COUNT(*) as cnt
        FROM emails
        WHERE content_hash IS NOT NULL AND content_hash != ''
        GROUP BY content_hash
        HAVING cnt > 1
        ORDER BY cnt DESC
    """).fetchall()

    duplicates = []
    for row in rows:
        ch = row["content_hash"]
        emails = conn.execute("""
            SELECT e.id, e.subject, e.sender_email, e.date_received, e.direction,
                   a.email as account_email, a.provider
            FROM emails e
            JOIN accounts a ON e.account_id = a.id
            WHERE e.content_hash = ?
            ORDER BY e.date_received
        """, (ch,)).fetchall()

        duplicates.append({
            "content_hash": ch,
            "count": row["cnt"],
            "emails": [dict(e) for e in emails],
        })

    conn.close()
    return duplicates


def get_dedup_stats(db: Database) -> dict:
    """Get deduplication statistics."""
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) as cnt FROM emails").fetchone()["cnt"]

    unique_hashes = conn.execute(
        "SELECT COUNT(DISTINCT content_hash) as cnt FROM emails WHERE content_hash IS NOT NULL"
    ).fetchone()["cnt"]

    dup_emails = total - unique_hashes if total > unique_hashes else 0

    dup_attachments = conn.execute(
        "SELECT COUNT(*) as cnt FROM attachments WHERE is_duplicate = 1"
    ).fetchone()["cnt"]

    conn.close()

    return {
        "total_emails": total,
        "unique_emails": unique_hashes,
        "duplicate_emails": dup_emails,
        "duplicate_attachments": dup_attachments,
    }
