"""Tests for the email parent_email_id backfill migration.

Seeds synthetic emails with raw_headers JSON and asserts the migration
sets parent_email_id correctly, is idempotent, and respects edge cases
(missing parent, self-reference, no headers).
"""
import json

import pytest

from casepulse.scripts.backfill_email_parents import backfill


def _insert_email(db, *, message_id, headers=None, parent_email_id=None,
                   is_reply=0):
    raw = json.dumps(headers) if headers is not None else None
    with db._get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO emails (message_id, raw_headers, parent_email_id, "
            "is_reply, account_id, subject) VALUES (?, ?, ?, ?, NULL, '')",
            (message_id, raw, parent_email_id, is_reply),
        )
        return cur.lastrowid


def test_links_in_reply_to_to_existing_parent(tmp_db):
    parent_id = _insert_email(tmp_db, message_id="parent@x.com")
    child_id = _insert_email(
        tmp_db, message_id="child@x.com",
        headers={"In-Reply-To": "<parent@x.com>"},
    )

    stats = backfill(tmp_db, apply_changes=True)
    assert stats["linked"] == 1

    with tmp_db._get_conn() as conn:
        row = conn.execute(
            "SELECT parent_email_id, is_reply FROM emails WHERE id = ?",
            (child_id,),
        ).fetchone()
    assert row["parent_email_id"] == parent_id
    assert row["is_reply"] == 1


def test_falls_back_to_references_when_no_in_reply_to(tmp_db):
    parent_id = _insert_email(tmp_db, message_id="grandparent@x.com")
    middle_id = _insert_email(tmp_db, message_id="parent@x.com")
    child_id = _insert_email(
        tmp_db, message_id="child@x.com",
        headers={"References": "<grandparent@x.com> <parent@x.com>"},
    )

    backfill(tmp_db, apply_changes=True)
    with tmp_db._get_conn() as conn:
        row = conn.execute(
            "SELECT parent_email_id FROM emails WHERE id = ?",
            (child_id,),
        ).fetchone()
    # Last References entry wins → 'parent@x.com'
    assert row["parent_email_id"] == middle_id


def test_skips_when_parent_not_in_db(tmp_db):
    _insert_email(
        tmp_db, message_id="orphan@x.com",
        headers={"In-Reply-To": "<missing@somewhere-else.com>"},
    )
    stats = backfill(tmp_db, apply_changes=True)
    assert stats["linked"] == 0
    assert stats["parent_missing"] == 1


def test_skips_self_reference(tmp_db):
    _insert_email(
        tmp_db, message_id="self@x.com",
        headers={"In-Reply-To": "<self@x.com>"},
    )
    stats = backfill(tmp_db, apply_changes=True)
    assert stats["linked"] == 0
    assert stats["self_reference"] == 1


def test_dry_run_does_not_write(tmp_db):
    parent_id = _insert_email(tmp_db, message_id="parent@x.com")
    child_id = _insert_email(
        tmp_db, message_id="child@x.com",
        headers={"In-Reply-To": "<parent@x.com>"},
    )
    stats = backfill(tmp_db, apply_changes=False)
    assert stats["linked"] == 1

    with tmp_db._get_conn() as conn:
        row = conn.execute(
            "SELECT parent_email_id FROM emails WHERE id = ?",
            (child_id,),
        ).fetchone()
    assert row["parent_email_id"] is None  # not written


def test_idempotent_second_run_is_noop(tmp_db):
    _insert_email(tmp_db, message_id="parent@x.com")
    _insert_email(
        tmp_db, message_id="child@x.com",
        headers={"In-Reply-To": "<parent@x.com>"},
    )
    backfill(tmp_db, apply_changes=True)
    second = backfill(tmp_db, apply_changes=True)
    assert second["linked"] == 0
    assert second["already_linked"] == 1


def test_handles_email_with_no_raw_headers(tmp_db):
    _insert_email(tmp_db, message_id="bare@x.com", headers=None)
    stats = backfill(tmp_db, apply_changes=True)
    assert stats["no_header"] == 1


def test_handles_malformed_json_headers(tmp_db):
    """Some legacy rows may have non-JSON raw_headers. Don't crash."""
    with tmp_db._get_conn() as conn:
        conn.execute(
            "INSERT INTO emails (message_id, raw_headers, account_id, "
            "subject) VALUES ('bad@x.com', 'not-json{', NULL, '')"
        )
    stats = backfill(tmp_db, apply_changes=True)
    assert stats["no_header"] == 1


def test_does_not_touch_emails_with_correct_parent_already(tmp_db):
    parent_id = _insert_email(tmp_db, message_id="parent@x.com")
    child_id = _insert_email(
        tmp_db, message_id="child@x.com",
        headers={"In-Reply-To": "<parent@x.com>"},
        parent_email_id=parent_id, is_reply=1,
    )
    stats = backfill(tmp_db, apply_changes=True)
    assert stats["linked"] == 0
    assert stats["already_linked"] == 1
