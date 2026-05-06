"""Tests for the AppClose v2-apply migration.

Verifies:
  1. Dry-run reports counts without writing.
  2. Apply replaces v1 rows with v2 rows for the target source_file only.
  3. Other-PDF rows are untouched.
  4. chat_imports row is updated with new message_count + date range.
  5. Idempotency: a second apply on the same parsed input is a no-op.
  6. Empty bodies for non-text actions become "[<action>]" placeholders.
"""
from datetime import datetime

import pytest

from casepulse.scripts.apply_appclose_v2 import apply_v2, _content_hash
from casepulse.scripts.appclose_parser_v2 import ParsedMessage


def _seed_v1_rows(db, source_file: str, rows: list[dict]):
    """Insert synthetic v1 AppClose rows directly."""
    with db._get_conn() as conn:
        for r in rows:
            conn.execute(
                """INSERT INTO chat_messages (
                    source_type, source_file, platform, chat_name,
                    sender, timestamp, message_text, content_hash,
                    is_system, has_media, media_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "appclose", source_file, "AppClose", "AppClose",
                    r["sender"], r["timestamp"], r["text"],
                    _content_hash(r["timestamp"], r["sender"], r["text"]),
                    0, 0, "",
                ),
            )
        conn.execute(
            """INSERT INTO chat_imports (
                source_file, source_type, platform, chat_name, message_count,
                date_start, date_end, participants
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_file, "appclose", "AppClose", "AppClose",
             len(rows), "2024-01-01", "2024-12-31", "[]"),
        )


def _make_parsed(sender: str, ts: datetime, body: str,
                 action: str = "texted") -> ParsedMessage:
    return ParsedMessage(
        sender=sender,
        sent_at=ts,
        sent_at_raw=ts.strftime("%-m/%-d/%Y %-I:%M%p"),
        action=action,
        body=body,
    )


def test_dry_run_reports_counts_without_writes(tmp_db):
    pdf = "/fake/Conversations.pdf"
    _seed_v1_rows(tmp_db, pdf, [
        {"sender": "2025 Alice", "timestamp": "2024-09-16T16:55:00",
         "text": "first dirty"},
        {"sender": "Thanks Bob", "timestamp": "2024-09-16T17:00:00",
         "text": "second dirty"},
    ])

    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "first clean"),
        _make_parsed("Bob", datetime(2024, 9, 16, 17, 0), "second clean"),
        _make_parsed("Alice", datetime(2024, 9, 16, 17, 5), "missed by v1"),
    ]

    stats = apply_v2(tmp_db, pdf, apply_changes=False, parsed=parsed)
    assert stats["old_rows"] == 2
    assert stats["new_rows"] == 3
    assert stats["would_change"] is True
    assert stats["applied"] is False

    with tmp_db._get_conn() as conn:
        senders = [r["sender"] for r in conn.execute(
            "SELECT sender FROM chat_messages WHERE source_file = ?", (pdf,)
        ).fetchall()]
    assert "2025 Alice" in senders  # unchanged


def test_apply_replaces_target_pdf_rows(tmp_db):
    pdf = "/fake/Conversations.pdf"
    other_pdf = "/fake/Other.pdf"

    _seed_v1_rows(tmp_db, pdf, [
        {"sender": "2025 Alice", "timestamp": "2024-09-16T16:55:00",
         "text": "dirty 1"},
    ])
    _seed_v1_rows(tmp_db, other_pdf, [
        {"sender": "Charlie", "timestamp": "2024-10-01T10:00:00",
         "text": "untouched"},
    ])

    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "clean 1"),
        _make_parsed("Bob", datetime(2024, 9, 17, 9, 0), "clean 2"),
    ]
    stats = apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)
    assert stats["applied"] is True
    assert stats["new_rows"] == 2

    with tmp_db._get_conn() as conn:
        rows = conn.execute(
            "SELECT sender, timestamp, message_text FROM chat_messages "
            "WHERE source_file = ? ORDER BY timestamp", (pdf,)
        ).fetchall()
        assert [r["sender"] for r in rows] == ["Alice", "Bob"]
        assert [r["message_text"] for r in rows] == ["clean 1", "clean 2"]

        # Other PDF rows are untouched
        other = conn.execute(
            "SELECT sender FROM chat_messages WHERE source_file = ?",
            (other_pdf,),
        ).fetchall()
        assert [r["sender"] for r in other] == ["Charlie"]


def test_apply_updates_chat_imports_row(tmp_db):
    pdf = "/fake/Conversations.pdf"
    _seed_v1_rows(tmp_db, pdf, [
        {"sender": "X", "timestamp": "2024-01-01T00:00:00", "text": "a"},
    ])
    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "clean 1"),
        _make_parsed("Bob", datetime(2024, 12, 1, 9, 0), "clean 2"),
    ]
    apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)

    with tmp_db._get_conn() as conn:
        imp = conn.execute(
            "SELECT message_count, date_start, date_end FROM chat_imports "
            "WHERE source_file = ?", (pdf,)
        ).fetchone()
    assert imp["message_count"] == 2
    assert imp["date_start"] == "2024-09-16T16:55:00"
    assert imp["date_end"] == "2024-12-01T09:00:00"


def test_apply_is_idempotent(tmp_db):
    pdf = "/fake/Conversations.pdf"
    _seed_v1_rows(tmp_db, pdf, [
        {"sender": "X", "timestamp": "2024-01-01T00:00:00", "text": "a"},
    ])
    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "clean 1"),
        _make_parsed("Bob", datetime(2024, 9, 17, 9, 0), "clean 2"),
    ]
    apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)

    second = apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)
    assert second["would_change"] is False
    assert second["applied"] is True

    with tmp_db._get_conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM chat_messages WHERE source_file = ?",
            (pdf,),
        ).fetchone()["c"]
    assert count == 2  # Not duplicated


def test_action_only_messages_get_placeholder_body(tmp_db):
    pdf = "/fake/Conversations.pdf"
    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "",
                     action="sent a photo"),
        _make_parsed("Bob", datetime(2024, 9, 16, 17, 0), "with text",
                     action="sent attachment"),
    ]
    apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)

    with tmp_db._get_conn() as conn:
        rows = conn.execute(
            "SELECT message_text, has_media, media_type FROM chat_messages "
            "WHERE source_file = ? ORDER BY timestamp", (pdf,)
        ).fetchall()
    assert rows[0]["message_text"] == "[sent a photo]"
    assert rows[0]["has_media"] == 1
    assert rows[0]["media_type"] == "image"
    assert rows[1]["message_text"] == "with text"


def test_received_permission_marks_system(tmp_db):
    pdf = "/fake/Conversations.pdf"
    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "",
                     action="Received permission to make audio calls"),
    ]
    apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)

    with tmp_db._get_conn() as conn:
        row = conn.execute(
            "SELECT is_system FROM chat_messages WHERE source_file = ?",
            (pdf,),
        ).fetchone()
    assert row["is_system"] == 1


def test_dry_run_when_already_in_sync(tmp_db):
    """If the existing rows already match v2 output, would_change=False."""
    pdf = "/fake/Conversations.pdf"
    parsed = [
        _make_parsed("Alice", datetime(2024, 9, 16, 16, 55), "clean 1"),
    ]
    # Apply once to establish in-sync state
    apply_v2(tmp_db, pdf, apply_changes=True, parsed=parsed)
    # Dry-run should report no changes needed
    stats = apply_v2(tmp_db, pdf, apply_changes=False, parsed=parsed)
    assert stats["would_change"] is False
