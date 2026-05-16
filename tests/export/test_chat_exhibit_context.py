"""Regression test: chat exhibit context window must be CHRONOLOGICAL.

The legacy ±10-by-id query produced random conversation slices after
the AppClose v2 migration scrambled autoincrement IDs (delete-and-
reinsert leaves new IDs in arbitrary order vs. message timestamps).

This test seeds chat_messages where the IDs are intentionally
INVERSE-correlated with timestamps and asserts the context window
returned for an exhibit reflects message-time order, not id order.
"""
from datetime import datetime, timedelta


def _seed_chat(conn, chat_name: str, n: int, *, reverse_ids: bool = True):
    """Insert n messages in (timestamp asc) order but with ids in the
    reverse order, simulating post-migration id scramble."""
    base = datetime(2025, 1, 1, 12, 0, 0)
    rows = []
    for i in range(n):
        ts = (base + timedelta(minutes=i)).isoformat()
        rows.append((ts, f"msg #{i}"))
    if reverse_ids:
        rows = list(reversed(rows))
    for ts, body in rows:
        conn.execute(
            "INSERT INTO chat_messages (source_type, chat_name, sender, "
            "timestamp, message_text, platform) VALUES "
            "('whatsapp', ?, 'A', ?, ?, 'WhatsApp')",
            (chat_name, ts, body),
        )


def _build_pdf_returns_rows_only(db, case_id, tagged_id):
    """Run just the chat-context query the exhibit bundle uses.

    We don't render a PDF here — that requires reportlab and a lot of
    incidental setup. We replicate the query so the regression target
    is the SQL itself.
    """
    with db._get_conn() as conn:
        chat_msg = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ?", (tagged_id,)
        ).fetchone()
        assert chat_msg is not None
        chat_name = chat_msg["chat_name"]
        rows = conn.execute(
            """WITH ranked AS (
                 SELECT *, ROW_NUMBER() OVER (
                     ORDER BY timestamp, id
                 ) AS rn
                 FROM chat_messages WHERE chat_name = ?
               ),
               target AS (
                 SELECT rn FROM ranked WHERE id = ?
               )
               SELECT r.* FROM ranked r, target t
               WHERE r.rn BETWEEN t.rn - 10 AND t.rn + 10
               ORDER BY r.rn""",
            (chat_name, tagged_id),
        ).fetchall()
    return [dict(r) for r in rows]


def test_context_window_returns_chronological_neighbors(tmp_db_with_case):
    """50 messages with reversed ids → exhibit tag in the middle. The
    window must return the 10 messages on each side in TIME order."""
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        _seed_chat(conn, "X", 50, reverse_ids=True)
        # The middle message by timestamp will have id ≈ 25 in the
        # scrambled order — pick the row whose body is 'msg #25'.
        target_id = conn.execute(
            "SELECT id FROM chat_messages WHERE message_text = 'msg #25'"
        ).fetchone()["id"]

    rows = _build_pdf_returns_rows_only(db, case_id, target_id)

    bodies = [r["message_text"] for r in rows]
    # Expect 11 before #25 and 10 after = msg #15 through msg #35
    expected = [f"msg #{i}" for i in range(15, 36)]
    assert bodies == expected, (
        f"context window broken — got {bodies[:3]}…{bodies[-3:]}, "
        f"expected msg #15…#35"
    )


def test_context_window_does_not_leak_other_chats(tmp_db_with_case):
    """Context must be scoped to the same chat_name."""
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        _seed_chat(conn, "ChatA", 20)
        _seed_chat(conn, "ChatB", 20)
        target_id = conn.execute(
            "SELECT id FROM chat_messages WHERE chat_name='ChatA' "
            "AND message_text = 'msg #10'"
        ).fetchone()["id"]

    rows = _build_pdf_returns_rows_only(db, case_id, target_id)
    chat_names = {r["chat_name"] for r in rows}
    assert chat_names == {"ChatA"}


def test_context_window_clamps_at_start(tmp_db_with_case):
    """Tagging the first message returns the message + up to 10 after
    it (no negative-rank rows)."""
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        _seed_chat(conn, "X", 20)
        target_id = conn.execute(
            "SELECT id FROM chat_messages WHERE message_text = 'msg #0'"
        ).fetchone()["id"]

    rows = _build_pdf_returns_rows_only(db, case_id, target_id)
    bodies = [r["message_text"] for r in rows]
    assert bodies[0] == "msg #0"
    assert len(bodies) == 11
    assert bodies[-1] == "msg #10"
