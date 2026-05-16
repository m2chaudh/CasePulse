"""Contradiction Engine regression tests.

Two bugs the recent fix addresses:
  1. Every chat statement extracted from a 30-message window was
     attributed to win[0]["id"] regardless of which message it came
     from — so a contradiction cited in a court PDF pointed at the
     wrong message.
  2. extract_statements ingested every document in the DB into every
     sender's statement set, producing false-positive "contradictions"
     between a sender's chats and documents they themselves filed.
"""
from casepulse.analysis.contradictions import extract_statements
from casepulse.llm.base import LLMProvider


class _StubLLM(LLMProvider):
    """Replay scripted responses in order. Each query() call pulls the
    next response. Returns "" if the script is exhausted."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        self.calls.append((system_prompt, user_prompt))
        if not self._responses:
            return ""
        return self._responses.pop(0)

    def is_available(self) -> bool:
        return True

    def get_name(self) -> str:
        return "stub"


def _seed_chats(db, sender: str, n: int, *, chat_name="X"):
    """Insert n consecutive chat rows on sequential days."""
    with db._get_conn() as conn:
        for i in range(n):
            ts = f"2025-01-{i+1:02d}T12:00:00"
            conn.execute(
                "INSERT INTO chat_messages (source_type, chat_name, "
                "sender, timestamp, message_text, platform) VALUES "
                "('whatsapp', ?, ?, ?, ?, 'WhatsApp')",
                (chat_name, sender, ts, f"chat body {i}"),
            )
    with db._get_conn() as conn:
        return [r["id"] for r in conn.execute(
            "SELECT id FROM chat_messages WHERE sender = ? ORDER BY id",
            (sender,),
        ).fetchall()]


def test_chat_statement_attributes_to_matching_date(tmp_db_with_case):
    """LLM emits a statement dated 2025-01-05. The extractor must
    attribute it to the chat row at that timestamp, not win[0]."""
    db, _ = tmp_db_with_case
    sender = "Alice"
    msg_ids = _seed_chats(db, sender, 10)
    # Chat response: one statement dated 2025-01-05 (the 5th message).
    chat_response = "2025-01-05 | I will pay on the 5th | promise"
    llm = _StubLLM(responses=[chat_response])

    stmts = extract_statements(db, llm, sender_email=sender, sender_name=sender)

    chat_stmts = [s for s in stmts if s["source_type"] == "chat"]
    assert len(chat_stmts) == 1
    # Message #5 has id = msg_ids[4] (0-indexed)
    assert chat_stmts[0]["source_id"] == msg_ids[4]


def test_chat_statement_falls_back_to_first_when_date_unmatched(tmp_db_with_case):
    """If the LLM's emitted date doesn't match any message in the
    window, we fall back to win[0] — legacy behavior, preserved as a
    last resort."""
    db, _ = tmp_db_with_case
    sender = "Bob"
    msg_ids = _seed_chats(db, sender, 5)
    chat_response = "2099-01-01 | future statement | other"
    llm = _StubLLM(responses=[chat_response])

    stmts = extract_statements(db, llm, sender_email=sender, sender_name=sender)
    chat_stmts = [s for s in stmts if s["source_type"] == "chat"]
    assert len(chat_stmts) == 1
    assert chat_stmts[0]["source_id"] == msg_ids[0]


def test_documents_no_longer_polluted_into_sender_statements(tmp_db_with_case):
    """A document about a different person must NOT be appended to the
    sender's statement set. (Was the cause of false-positive
    'contradictions' between a sender's chat and the user's own filings.)"""
    db, _ = tmp_db_with_case
    sender = "Charlie"
    _seed_chats(db, sender, 3)
    # Seed a document with OCR done that has nothing to do with Charlie
    with db._get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (filename, file_path, ocr_status, "
            "extracted_text, content_type) VALUES "
            "('unrelated.pdf', '/x/unrelated.pdf', 'done', "
            "'This document mentions someone else entirely with a long "
            "claim about facts unrelated to Charlie.', 'application/pdf')"
        )
    # LLM responds with a chat statement; document loop is now gone, so
    # the LLM should be called once (for chats), not twice.
    llm = _StubLLM(responses=["2025-01-01 | hi | other"])

    stmts = extract_statements(db, llm, sender_email=sender, sender_name=sender)

    # No 'document' source_type statements should exist
    assert not any(s["source_type"] == "document" for s in stmts)
    # And LLM was called exactly once (chat batch). If documents were
    # still being ingested we'd see ≥2 calls.
    assert len(llm.calls) == 1
