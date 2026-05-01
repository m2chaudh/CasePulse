"""Integration test: image attachment triggers photo_metadata population."""
import pytest
from pathlib import Path
from PIL import Image


def test_attachment_image_triggers_metadata(tmp_db_with_case, tmp_path):
    """When an image attachment is ingested via extract_image + persist_metadata,
    a photo_metadata row is written correctly."""
    from casepulse.case_theory.metadata_extractor import extract_image, persist_metadata
    db, _ = tmp_db_with_case
    img_path = tmp_path / "img.jpg"
    Image.new('RGB', (50, 50)).save(img_path)

    conn = db._get_conn()
    cur = conn.cursor()
    # Insert a parent email row so FK constraint is satisfied
    cur.execute("""
        INSERT INTO emails (message_id, subject, sender_email, body_text,
                            content_hash, direction)
        VALUES ('msg-hook-1', 'test', 'sender@test.com', '', 'hash-hook-1', 'received')
    """)
    email_id = cur.lastrowid
    cur.execute("""
        INSERT INTO attachments (email_id, filename, content_type, size_bytes,
                                  file_path, content_hash)
        VALUES (?, 'img.jpg', 'image/jpeg', 0, ?, 'att-h1')
    """, (email_id, str(img_path)))
    conn.commit()
    att_id = cur.lastrowid

    # Simulate what the fetcher hookup does
    md = extract_image(img_path)
    persist_metadata(db, md, source_table="attachments", source_row_id=att_id)

    cur.execute("SELECT id FROM photo_metadata WHERE source_row_id = ?", (att_id,))
    assert cur.fetchone() is not None


def test_document_image_triggers_metadata(tmp_db_with_case, tmp_path):
    """Image document ingest populates photo_metadata with source_table='documents'."""
    from casepulse.case_theory.metadata_extractor import extract_image, persist_metadata
    db, case_id = tmp_db_with_case
    img_path = tmp_path / "scan.png"
    Image.new('RGB', (200, 300), 'white').save(img_path)

    conn = db._get_conn()
    cur = conn.cursor()
    # Insert a documents row (document_import.py does this at ingest)
    cur.execute("""
        INSERT INTO documents (filename, content_type, size_bytes,
                               file_path, content_hash)
        VALUES ('scan.png', 'image/png', 0, ?, 'doc-h2')
    """, (str(img_path),))
    conn.commit()
    doc_id = cur.lastrowid

    md = extract_image(img_path)
    persist_metadata(db, md, source_table="documents", source_row_id=doc_id)

    cur.execute("SELECT width, height FROM photo_metadata WHERE source_row_id = ?", (doc_id,))
    row = cur.fetchone()
    assert row is not None
    assert row[0] == 200
    assert row[1] == 300
