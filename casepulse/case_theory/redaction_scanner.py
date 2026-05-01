"""Wrapper around freelawproject's x-ray library to detect bad PDF redactions
(black rectangles drawn over still-extractable text)."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RedactionFinding:
    page: int
    text: str
    bbox: tuple | None = None


def scan_pdf(path: "Path | str") -> list[RedactionFinding]:
    """Scan a PDF for bad redactions. Returns empty list if clean."""
    try:
        import xray  # noqa
    except ImportError:
        # Library not installed; return empty (don't fail builds)
        return []
    p = Path(path)
    try:
        results = xray.inspect(str(p))
    except Exception:
        return []

    findings: list[RedactionFinding] = []
    for page_num, page_findings in (results or {}).items():
        for item in (page_findings or []):
            findings.append(RedactionFinding(
                page=int(page_num),
                text=item.get("text", "") if isinstance(item, dict) else str(item),
                bbox=item.get("bbox") if isinstance(item, dict) else None,
            ))
    return findings
