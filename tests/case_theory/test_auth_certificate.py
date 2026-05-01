# tests/case_theory/test_auth_certificate.py
from datetime import date
from casepulse.case_theory.auth_certificate import (
    CertificateInput, ExhibitRecord, render_certificate_html,
)


def test_certificate_html_contains_required_clauses():
    cert = CertificateInput(
        operator_name="Mani Chaudhary",
        operator_address="Toronto, ON",
        location="Toronto, ON",
        signing_date=date(2026, 4, 30),
        software_version="CasePulse v1.0",
        exhibits=[
            ExhibitRecord(
                ref="A", description="Photograph IMG_4521.jpg",
                source="WhatsApp", ingested_at="2024-08-12",
                sha256="3a7d8e1f0c2b9a64b72f",
            ),
        ],
    )
    html = render_certificate_html(cert)
    assert "s. 31.6" in html or "31.6" in html
    assert "Mani Chaudhary" in html
    assert "3a7d8e1f0c2b9a64b72f" in html
    assert "EXHIBIT A" in html.upper() or "Exhibit A" in html
