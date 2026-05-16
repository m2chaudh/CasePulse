"""Cascade-delete regression tests.

Polymorphic FKs (`evidence_tags.item_type` + `item_id`) can't auto-
cascade through SQLite. The DB methods that delete an email account
or a chat import need to clean up dependent rows in the same
transaction. Orphaned tags later cause silent TOC gaps in court PDFs.
"""


def _seed_chat_import_with_messages(db, source_file: str, msg_bodies: list[str]):
    """Returns the chat_imports.id."""
    with db._get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO chat_imports (source_file, source_type, platform, "
            "chat_name, message_count) VALUES (?, 'whatsapp', 'WhatsApp', "
            "'X', ?)",
            (source_file, len(msg_bodies)),
        )
        import_id = cur.lastrowid
        for body in msg_bodies:
            conn.execute(
                "INSERT INTO chat_messages (source_type, source_file, "
                "platform, chat_name, sender, timestamp, message_text) "
                "VALUES ('whatsapp', ?, 'WhatsApp', 'X', 'A', "
                "'2024-01-01T00:00:00', ?)",
                (source_file, body),
            )
    return import_id


def _tag_each_message(db, source_file: str, case_id: int):
    """Tag every chat message under source_file with exhibit labels."""
    with db._get_conn() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM chat_messages WHERE source_file = ?",
            (source_file,),
        ).fetchall()]
        for i, mid in enumerate(ids, 1):
            conn.execute(
                "INSERT INTO evidence_tags (item_type, item_id, case_id, "
                "exhibit_label) VALUES ('chat', ?, ?, ?)",
                (mid, case_id, f"C-{i}"),
            )
            conn.execute(
                "INSERT INTO annotations (item_type, item_id, case_id, "
                "note_text) VALUES ('chat', ?, ?, 'review me')",
                (mid, case_id),
            )
    return ids


def test_delete_chat_import_cascades_evidence_tags(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    import_id = _seed_chat_import_with_messages(
        db, "/x/a.txt", ["one", "two", "three"],
    )
    msg_ids = _tag_each_message(db, "/x/a.txt", case_id)

    db.delete_chat_import(import_id)

    with db._get_conn() as conn:
        placeholders = ",".join("?" * len(msg_ids))
        n_tags = conn.execute(
            f"SELECT COUNT(*) AS c FROM evidence_tags WHERE "
            f"item_type='chat' AND item_id IN ({placeholders})",
            msg_ids,
        ).fetchone()["c"]
        n_anns = conn.execute(
            f"SELECT COUNT(*) AS c FROM annotations WHERE "
            f"item_type='chat' AND item_id IN ({placeholders})",
            msg_ids,
        ).fetchone()["c"]
    assert n_tags == 0
    assert n_anns == 0


def test_delete_chat_import_leaves_unrelated_tags_intact(tmp_db_with_case):
    """A delete on import A must not touch tags pointing at import B."""
    db, case_id = tmp_db_with_case
    import_a = _seed_chat_import_with_messages(db, "/x/a.txt", ["a1"])
    _seed_chat_import_with_messages(db, "/x/b.txt", ["b1"])
    _tag_each_message(db, "/x/a.txt", case_id)
    _tag_each_message(db, "/x/b.txt", case_id)

    db.delete_chat_import(import_a)

    with db._get_conn() as conn:
        # Tags on import B's messages still there
        b_tags = conn.execute(
            "SELECT COUNT(*) AS c FROM evidence_tags t "
            "JOIN chat_messages m ON m.id = t.item_id "
            "WHERE t.item_type='chat' AND m.source_file='/x/b.txt'"
        ).fetchone()["c"]
    assert b_tags == 1


def test_delete_account_cascades_email_tags_and_evidence(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO accounts (email, provider, last_synced) "
            "VALUES ('foo@bar.com', 'gmail', NULL)"
        )
        account_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO emails (message_id, account_id, subject, "
            "sender_email) VALUES ('m1@x', ?, 'hi', 'a@x')",
            (account_id,),
        )
        email_id = cur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id, "
            "exhibit_label) VALUES ('email', ?, ?, 'E-1')",
            (email_id, case_id),
        )
        conn.execute(
            "INSERT INTO annotations (item_type, item_id, case_id, "
            "note_text) VALUES ('email', ?, ?, 'note')",
            (email_id, case_id),
        )
        conn.execute(
            "INSERT INTO evidence (evidence_kind, source_table, "
            "source_row_id, snippet) VALUES ('quote', 'emails', ?, 'foo')",
            (email_id,),
        )

    db.delete_account(account_id)

    with db._get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM evidence_tags WHERE item_type='email'"
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM annotations WHERE item_type='email'"
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM evidence WHERE source_table='emails'"
        ).fetchone()["c"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS c FROM emails WHERE account_id = ?",
            (account_id,),
        ).fetchone()["c"] == 0
