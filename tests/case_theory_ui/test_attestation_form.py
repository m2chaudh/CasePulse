"""Tests for the attestation form component and its repository helpers."""
import pytest


def test_record_and_list_attestations(tmp_db_with_case):
    """record_attestation inserts, list_attestations_for_metadata retrieves."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.repository import (
        record_attestation, list_attestations_for_metadata,
    )
    # Insert a photo_metadata row directly
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO photo_metadata (source_table, source_row_id, "
        "exif_present, width, height) VALUES "
        "('attachments', 1, 0, 100, 100)"
    )
    conn.commit()
    pmid = cur.lastrowid

    record_attestation(
        db,
        photo_metadata_id=pmid,
        field_name="taken_at",
        status="attested",
        attestation_text="I, X, took this on Date.",
        attested_by="Mani Chaudhary",
        attested_at="2026-04-30",
    )
    rows = list_attestations_for_metadata(db, photo_metadata_id=pmid)
    assert len(rows) == 1
    assert rows[0]["status"] == "attested"
    assert rows[0]["field_name"] == "taken_at"
    assert rows[0]["attestation_text"] == "I, X, took this on Date."


def test_record_struck_attestation(tmp_db_with_case):
    """Strike attestation is recorded correctly."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.repository import (
        record_attestation, list_attestations_for_metadata,
    )
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO photo_metadata (source_table, source_row_id, "
        "exif_present, width, height) VALUES "
        "('documents', 2, 1, 200, 300)"
    )
    conn.commit()
    pmid = cur.lastrowid

    row_id = record_attestation(
        db,
        photo_metadata_id=pmid,
        field_name="gps_lat",
        status="struck",
        reason="GPS data appears fabricated",
    )
    assert row_id > 0
    rows = list_attestations_for_metadata(db, photo_metadata_id=pmid)
    assert len(rows) == 1
    assert rows[0]["status"] == "struck"
    assert rows[0]["reason"] == "GPS data appears fabricated"


def test_multiple_attestations_for_same_metadata(tmp_db_with_case):
    """Multiple fields can be attested for the same photo_metadata_id."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.repository import (
        record_attestation, list_attestations_for_metadata,
    )
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO photo_metadata (source_table, source_row_id, "
        "exif_present, width, height) VALUES "
        "('attachments', 5, 1, 1920, 1080)"
    )
    conn.commit()
    pmid = cur.lastrowid

    record_attestation(db, photo_metadata_id=pmid, field_name="camera_make",
                       status="attested", attestation_text="Confirmed Canon")
    record_attestation(db, photo_metadata_id=pmid, field_name="gps_lat",
                       status="struck", reason="Location falsified")

    rows = list_attestations_for_metadata(db, photo_metadata_id=pmid)
    assert len(rows) == 2
    fields = {r["field_name"] for r in rows}
    assert "camera_make" in fields
    assert "gps_lat" in fields
