"""EXIF metadata extraction, DB persistence, and OCR for image files."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ExifTags
from pydantic import BaseModel


class ImageMetadata(BaseModel):
    taken_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens: Optional[str] = None
    software: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    orientation: Optional[int] = None
    width: int = 0
    height: int = 0
    exif_present: bool = False


def _parse_exif_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _decode_gps(gps_info: dict) -> tuple[float | None, float | None, float | None]:
    """Decode GPSInfo dict into (lat, lon, accuracy) decimals."""
    if not gps_info:
        return (None, None, None)

    def _to_decimal(coord, ref):
        if not coord:
            return None
        d, m, s = coord
        decimal = float(d) + float(m) / 60 + float(s) / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal

    lat = _to_decimal(gps_info.get(2), gps_info.get(1, "N"))
    lon = _to_decimal(gps_info.get(4), gps_info.get(3, "E"))
    return (lat, lon, None)


def extract_image(path: Path | str) -> ImageMetadata:
    """Extract EXIF + dimensions from an image file. Returns ImageMetadata
    with exif_present=False if the image has no EXIF block."""
    p = Path(path)
    md = ImageMetadata()
    try:
        with Image.open(p) as img:
            md.width, md.height = img.size
            exif = img._getexif() if hasattr(img, "_getexif") else None
    except Exception:
        return md

    if not exif:
        return md
    md.exif_present = True

    tag_to_id = ExifTags.TAGS
    name_to_value = {tag_to_id.get(k, k): v for k, v in exif.items()}

    md.taken_at = _parse_exif_datetime(name_to_value.get("DateTimeOriginal"))
    md.camera_make = (name_to_value.get("Make") or "").strip() or None
    md.camera_model = (name_to_value.get("Model") or "").strip() or None
    md.lens = (name_to_value.get("LensModel") or "").strip() or None
    md.software = (name_to_value.get("Software") or "").strip() or None
    md.orientation = name_to_value.get("Orientation")
    gps_info = name_to_value.get("GPSInfo")
    if gps_info:
        md.gps_lat, md.gps_lon, md.gps_accuracy = _decode_gps(gps_info)
    return md


# ── Task 3.2: Persist to DB ─────────────────────────────────────────────────

def persist_metadata(db, md: ImageMetadata, *,
                     source_table: str, source_row_id: int) -> int:
    """Insert or update photo_metadata row. Returns photo_metadata.id."""
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO photo_metadata (
            source_table, source_row_id, taken_at, camera_make, camera_model,
            lens, software, gps_lat, gps_lon, gps_accuracy,
            orientation, width, height, exif_present
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_table, source_row_id) DO UPDATE SET
            taken_at = excluded.taken_at,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            lens = excluded.lens,
            software = excluded.software,
            gps_lat = excluded.gps_lat,
            gps_lon = excluded.gps_lon,
            gps_accuracy = excluded.gps_accuracy,
            orientation = excluded.orientation,
            width = excluded.width,
            height = excluded.height,
            exif_present = excluded.exif_present
    """, (
        source_table, source_row_id,
        md.taken_at.isoformat() if md.taken_at else None,
        md.camera_make, md.camera_model, md.lens, md.software,
        md.gps_lat, md.gps_lon, md.gps_accuracy,
        md.orientation, md.width, md.height,
        1 if md.exif_present else 0,
    ))
    conn.commit()
    cur.execute("SELECT id FROM photo_metadata "
                "WHERE source_table = ? AND source_row_id = ?",
                (source_table, source_row_id))
    return cur.fetchone()[0]


# ── Task 3.3: OCR via pytesseract ────────────────────────────────────────────

def run_ocr_image(path: Path | str) -> tuple[str, float]:
    """Run Tesseract on an image. Returns (text, mean_confidence_0_to_1).

    If pytesseract isn't installed or Tesseract binary missing, returns ('', 0.0).
    """
    try:
        import pytesseract
    except ImportError:
        return ("", 0.0)
    try:
        text = pytesseract.image_to_string(str(path))
        data = pytesseract.image_to_data(
            str(path), output_type=pytesseract.Output.DICT
        )
        confs = [int(c) for c in data.get("conf", []) if c not in ("-1", -1)]
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return (text.strip(), mean_conf)
    except Exception:
        return ("", 0.0)
