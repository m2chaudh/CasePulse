"""Export manifest — metadata + checksums for defensibility."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_manifest(
    export_id: str,
    case_name: str,
    case_number: str,
    export_type: str,
    filters: dict,
    items_count: int,
    pages_total: int,
    attachments_count: int,
    privilege_excluded: int,
    file_path: Optional[str] = None,
) -> dict:
    """Generate an export manifest with metadata."""
    manifest = {
        "export_id": export_id,
        "generated_at": datetime.now().isoformat(),
        "tool": "CasePulse",
        "case": case_name,
        "case_number": case_number,
        "export_type": export_type,
        "filters_applied": filters,
        "items_included": items_count,
        "pages_total": pages_total,
        "attachments_included": attachments_count,
        "privilege_log_items": privilege_excluded,
        "sha256_checksum": "",
    }

    if file_path and Path(file_path).exists():
        manifest["sha256_checksum"] = compute_checksum(file_path)
        manifest["file_size_bytes"] = Path(file_path).stat().st_size

    return manifest


def compute_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def save_manifest(manifest: dict, output_dir: str) -> str:
    """Save manifest as JSON file alongside the export."""
    path = Path(output_dir) / f"{manifest['export_id']}_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return str(path)


def generate_export_id() -> str:
    """Generate a unique export ID."""
    now = datetime.now()
    return f"EXP-{now.strftime('%Y%m%d-%H%M%S')}"
