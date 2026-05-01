# tests/case_theory/test_redaction_scanner.py
pytest = __import__("pytest")
xray = pytest.importorskip("xray", reason="xray not installed")

from pathlib import Path
from casepulse.case_theory.redaction_scanner import scan_pdf

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pdfs"


def test_clean_pdf_no_findings():
    findings = scan_pdf(FIXTURES / "clean.pdf")
    assert findings == []


def test_bad_redaction_detected():
    findings = scan_pdf(FIXTURES / "bad_redaction.pdf")
    assert len(findings) >= 1
    assert findings[0].page > 0
