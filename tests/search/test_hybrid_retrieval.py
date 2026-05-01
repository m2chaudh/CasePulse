"""Tests for hybrid retrieval combining BM25 and embedding search via RRF."""
from casepulse.search.retrieval import hybrid_search


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
