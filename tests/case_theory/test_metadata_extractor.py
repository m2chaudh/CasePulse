"""Tests for EXIF extractor, persist_metadata, and run_ocr_image."""
from pathlib import Path
import pytest
from casepulse.case_theory.metadata_extractor import extract_image, ImageMetadata


FIXTURES = Path(__file__).parent.parent / "fixtures" / "photos"


# ── Task 3.1: EXIF extractor ────────────────────────────────────────────────

def test_extract_image_with_exif():
    md = extract_image(FIXTURES / "iphone_with_exif.jpg")
    assert isinstance(md, ImageMetadata)
    assert md.exif_present is True
    assert md.taken_at is not None
    assert md.width == 100
    assert md.height == 100


def test_extract_image_without_exif():
    md = extract_image(FIXTURES / "no_exif.png")
    assert md.exif_present is False
    assert md.taken_at is None
    assert md.width == 100  # still extracted from file


# ── Task 3.2: persist_metadata ───────────────────────────────────────────────

def test_persist_image_metadata(tmp_db, tmp_path):
    from casepulse.case_theory.metadata_extractor import (
        extract_image, persist_metadata
    )
    src = FIXTURES / "iphone_with_exif.jpg"
    md = extract_image(src)
    persist_metadata(tmp_db, md, source_table="attachments", source_row_id=1)
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT exif_present, width, height FROM photo_metadata "
                "WHERE source_row_id = 1")
    row = cur.fetchone()
    assert row[0] == 1  # exif_present True stored as 1
    assert row[1] == 100


def test_persist_metadata_upsert(tmp_db, tmp_path):
    """Calling persist_metadata twice for same source row updates instead of duplicating."""
    from casepulse.case_theory.metadata_extractor import (
        extract_image, persist_metadata
    )
    src = FIXTURES / "no_exif.png"
    md = extract_image(src)
    row_id1 = persist_metadata(tmp_db, md, source_table="attachments", source_row_id=99)
    row_id2 = persist_metadata(tmp_db, md, source_table="attachments", source_row_id=99)
    assert row_id1 == row_id2  # same row updated, not duplicated


# ── Task 3.3: run_ocr_image ──────────────────────────────────────────────────

def test_run_ocr_on_image_with_text(tmp_path):
    import shutil
    if not shutil.which("tesseract"):
        pytest.skip("tesseract binary not installed on this system")
    from PIL import Image, ImageDraw
    from casepulse.case_theory.metadata_extractor import run_ocr_image
    img = Image.new('RGB', (300, 100), 'white')
    d = ImageDraw.Draw(img)
    d.text((10, 30), "HELLO WORLD", fill='black')
    p = tmp_path / "test_ocr.png"
    img.save(p)
    text, confidence = run_ocr_image(p)
    assert "HELLO" in text.upper()
    assert 0 <= confidence <= 1


def test_run_ocr_graceful_without_tesseract(tmp_path, monkeypatch):
    """run_ocr_image returns ('', 0.0) when pytesseract binary is unavailable."""
    from casepulse.case_theory.metadata_extractor import run_ocr_image
    from PIL import Image
    img = Image.new('RGB', (100, 50), 'white')
    p = tmp_path / "blank.png"
    img.save(p)
    # Simulate missing binary by patching image_to_string to raise
    import pytesseract
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *a, **kw: (_ for _ in ()).throw(Exception("no tesseract")))
    text, conf = run_ocr_image(p)
    assert text == ""
    assert conf == 0.0
