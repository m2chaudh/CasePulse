"""Tests for documents appearing in ChromaDB chunks."""


def test_documents_appear_in_chunks(tmp_db_with_case):
    """Documents added to the documents table also enter ChromaDB chunks."""
    from casepulse.rag.chunker import build_all_chunks
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_hash,
                               extracted_text, ocr_status)
        VALUES ('test.pdf', '/tmp/test.pdf', 'docHash1',
                'Long document content about visitation', 'done')
    """)
    conn.commit()
    chunks = build_all_chunks(db)
    doc_chunks = [c for c in chunks if c["metadata"].get("type") == "document"]
    assert len(doc_chunks) >= 1
    assert "visitation" in doc_chunks[0]["text"].lower()
