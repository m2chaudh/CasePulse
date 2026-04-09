"""Extract metadata and EXIF data from images — GPS coordinates, timestamps, camera info."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


def extract_image_metadata(file_path: str) -> dict:
    """Extract EXIF and metadata from an image file.

    Returns dict with:
    - gps_lat, gps_lon: GPS coordinates (if available)
    - gps_address: Reverse-geocoded address (if GPS available)
    - date_taken: Original date/time photo was taken
    - camera_make, camera_model: Camera/phone info
    - width, height: Image dimensions
    - orientation: Image orientation
    - all_exif: Raw EXIF dict for additional inspection
    """
    path = Path(file_path)
    if not path.exists():
        return {}

    result = {
        "file_path": file_path,
        "filename": path.name,
        "file_size": path.stat().st_size,
    }

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        img = Image.open(str(path))
        result["width"] = img.width
        result["height"] = img.height
        result["format"] = img.format

        # Get EXIF data
        exif_data = img._getexif()
        if not exif_data:
            return result

        exif = {}
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            exif[tag] = value

        result["all_exif"] = {k: str(v) for k, v in exif.items() if isinstance(k, str)}

        # Date taken
        date_taken = exif.get("DateTimeOriginal") or exif.get("DateTime")
        if date_taken:
            try:
                dt = datetime.strptime(str(date_taken), "%Y:%m:%d %H:%M:%S")
                result["date_taken"] = dt.isoformat()
            except (ValueError, TypeError):
                result["date_taken"] = str(date_taken)

        # Camera info
        result["camera_make"] = str(exif.get("Make", "")).strip()
        result["camera_model"] = str(exif.get("Model", "")).strip()

        # Orientation
        result["orientation"] = exif.get("Orientation", "")

        # GPS data
        gps_info = exif.get("GPSInfo")
        if gps_info:
            gps = {}
            for key, val in gps_info.items():
                decoded = GPSTAGS.get(key, key)
                gps[decoded] = val

            lat = _convert_gps_to_decimal(
                gps.get("GPSLatitude"),
                gps.get("GPSLatitudeRef", "N"),
            )
            lon = _convert_gps_to_decimal(
                gps.get("GPSLongitude"),
                gps.get("GPSLongitudeRef", "E"),
            )

            if lat is not None and lon is not None:
                result["gps_lat"] = lat
                result["gps_lon"] = lon
                result["gps_google_maps"] = f"https://maps.google.com/?q={lat},{lon}"

                # GPS altitude
                alt = gps.get("GPSAltitude")
                if alt:
                    try:
                        result["gps_altitude_m"] = float(alt)
                    except (TypeError, ValueError):
                        pass

                # GPS timestamp
                gps_date = gps.get("GPSDateStamp")
                gps_time = gps.get("GPSTimeStamp")
                if gps_date and gps_time:
                    try:
                        h, m, s = [float(x) for x in gps_time]
                        result["gps_timestamp"] = f"{gps_date} {int(h):02d}:{int(m):02d}:{int(s):02d}"
                    except (TypeError, ValueError):
                        pass

        img.close()

    except ImportError:
        # Pillow not installed — already in requirements via pdfplumber
        pass
    except Exception as e:
        result["metadata_error"] = str(e)

    return result


def _convert_gps_to_decimal(coords, ref: str) -> Optional[float]:
    """Convert GPS coordinates from degrees/minutes/seconds to decimal."""
    if not coords:
        return None
    try:
        degrees = float(coords[0])
        minutes = float(coords[1])
        seconds = float(coords[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError, IndexError):
        return None


def extract_metadata_for_directory(dir_path: str) -> list[dict]:
    """Extract metadata from all images in a directory."""
    path = Path(dir_path)
    results = []
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif", ".tiff"}

    for f in sorted(path.rglob("*")):
        if f.suffix.lower() in image_extensions:
            meta = extract_image_metadata(str(f))
            if meta:
                results.append(meta)

    return results


def format_metadata_for_rag(metadata: dict) -> str:
    """Format image metadata as text for RAG indexing."""
    parts = [f"Image: {metadata.get('filename', 'unknown')}"]

    if metadata.get("date_taken"):
        parts.append(f"Date taken: {metadata['date_taken']}")

    if metadata.get("camera_make") or metadata.get("camera_model"):
        camera = f"{metadata.get('camera_make', '')} {metadata.get('camera_model', '')}".strip()
        parts.append(f"Camera: {camera}")

    if metadata.get("gps_lat") and metadata.get("gps_lon"):
        parts.append(f"GPS: {metadata['gps_lat']}, {metadata['gps_lon']}")
        if metadata.get("gps_google_maps"):
            parts.append(f"Map: {metadata['gps_google_maps']}")

    if metadata.get("width") and metadata.get("height"):
        parts.append(f"Size: {metadata['width']}x{metadata['height']}")

    return "\n".join(parts)
