"""Tests for hybrid retrieval combining BM25 and embedding search via RRF."""
import json
from casepulse.search.retrieval import hybrid_search, _embedding_search, SearchFacets


def test_hybrid_returns_results(tmp_db_with_case, monkeypatch):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accounts (provider, email) VALUES ('gmail', 'a@x.com')"
    )
    acct_id = cur.lastrowid
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Custody', 'access schedule discussion', 'a@x', '<m1>',
                'h1', ?)
    """, (acct_id,))
    conn.commit()
    # Stub embedding query — empty for this test
    monkeypatch.setattr(
        "casepulse.search.retrieval._embedding_search", lambda *a, **kw: []
    )
    hits = hybrid_search(db, "custody", k=10)
    assert len(hits) >= 1


def test_embedding_search_chat_citations_have_real_row_ids(tmp_db_with_case, monkeypatch):
    """Chat hits from _embedding_search must expand to per-message Citations,
    each with its own real row_id — not collapsed into row_id=0.

    We stub VectorStore.query via monkeypatching the source modules so that
    the local imports inside _embedding_search pick up the fakes.
    """
    db, _ = tmp_db_with_case

    # Fake VectorStore.query returning one chat hit with three message IDs
    fake_hit = {
        "text": "Alice: hello Bob: hi Alice: how are you",
        "relevance_score": 0.9,
        "metadata": {
            "type": "chat",
            "platform": "WhatsApp",
            "chat_name": "Family Chat",
            "sender": "Alice, Bob",
            "date": "2024-01-10",
            "date_end": "2024-01-10",
            "subject": "Family Chat",
            "chunk_index": 0,
            "chat_message_ids": json.dumps([42, 43, 44]),
            "first_chat_message_id": 42,
        },
    }

    class FakeVS:
        def query(self, *a, **kw):
            return [fake_hit]

    class FakeEmbedder:
        def embed_query(self, text):
            return [0.1] * 384

    # Patch the modules that _embedding_search imports locally
    import casepulse.rag.vectorstore as vs_mod
    import casepulse.rag.embedder as emb_mod
    monkeypatch.setattr(vs_mod, "VectorStore", FakeVS)
    monkeypatch.setattr(emb_mod, "LocalEmbedder", FakeEmbedder)

    # Also patch at the module class level so `from ... import X` picks up the stub
    monkeypatch.setattr("casepulse.rag.vectorstore.VectorStore", FakeVS)
    monkeypatch.setattr("casepulse.rag.embedder.LocalEmbedder", FakeEmbedder)

    hits = _embedding_search(db, "hello", SearchFacets(), k=10)

    row_ids = [h.citation.row_id for h in hits]
    assert 42 in row_ids, f"row_id 42 missing from hits: {row_ids}"
    assert 43 in row_ids, f"row_id 43 missing from hits: {row_ids}"
    assert 44 in row_ids, f"row_id 44 missing from hits: {row_ids}"
    assert 0 not in row_ids, f"row_id 0 (sentinel) should not appear in hits: {row_ids}"
    assert len(hits) == 3, f"Expected 3 citations (one per message ID), got {len(hits)}"
