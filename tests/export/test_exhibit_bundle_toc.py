"""Regression: TOC page numbers must equal each exhibit's actual start
page in the rendered PDF.

The legacy code did `page_counter += 1` for every exhibit regardless
of body length, so a multi-page email body shifted every subsequent
TOC entry by one (or more) page. Court bundles with a wrong TOC are
an immediate filing challenge.

We render a bundle through the real builder, then re-parse the PDF
with pypdf to read each page's actual content and assert the TOC
entries match.
"""
import io
import re

import pytest


pdfplumber = pytest.importorskip("pdfplumber")


def _make_long_email(db, subject: str, body_chars: int):
    """Seed an email row (account-id NULL to avoid UNIQUE collisions)
    whose body is long enough to span multiple PDF pages."""
    with db._get_conn() as conn:
        body = "X " * (body_chars // 2)
        cur = conn.execute(
            "INSERT INTO emails (message_id, subject, "
            "body_text, sender_email, sender_name, date_received) VALUES "
            "(?, ?, ?, 'a@x', 'A', '2024-01-01T00:00:00')",
            (f"<{subject}@x>", subject, body),
        )
        return None, cur.lastrowid


def _read_pdf_pages(pdf_bytes: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def test_toc_pages_match_actual_exhibit_start_pages(tmp_db_with_case):
    from casepulse.export.pdf_builder import build_exhibit_bundle_pdf

    db, case_id = tmp_db_with_case
    # Three exhibits — middle one's body is very long so it spans
    # multiple pages and would have broken the legacy estimate.
    _, e1 = _make_long_email(db, "first", 200)
    _, e2 = _make_long_email(db, "long-body", 18000)
    _, e3 = _make_long_email(db, "third", 200)

    for label, eid in [("Ex 1", e1), ("Ex 2", e2), ("Ex 3", e3)]:
        db.tag_evidence("email", eid, case_id, exhibit_label=label)

    pdf_bytes = build_exhibit_bundle_pdf(
        db, case_id, case_name="Test Case",
    )
    pages = _read_pdf_pages(pdf_bytes)

    # Find each exhibit's actual start page by scanning page text
    exhibit_label_pages: dict[str, int] = {}
    for i, text in enumerate(pages, start=1):
        for label in ("Ex 1", "Ex 2", "Ex 3"):
            if label in text and label not in exhibit_label_pages:
                # Take the FIRST page where the label appears as the
                # exhibit start. The TOC page also contains all labels,
                # so we need to skip the TOC page itself.
                if "Table of Contents" not in text:
                    exhibit_label_pages[label] = i

    assert set(exhibit_label_pages) == {"Ex 1", "Ex 2", "Ex 3"}

    # Now extract TOC entries — locate the page containing 'Table of
    # Contents' and the page numbers next to each exhibit label.
    toc_page_text = next(p for p in pages if "Table of Contents" in p)
    # Each TOC row is a line like "Ex 1 ... <page_num>"
    toc_pages = {}
    for label in ("Ex 1", "Ex 2", "Ex 3"):
        # Find the line containing this label; last number on that line
        # is the page number.
        for line in toc_page_text.split("\n"):
            if label in line:
                nums = re.findall(r"\b(\d+)\b", line)
                if nums:
                    toc_pages[label] = int(nums[-1])
                break

    assert set(toc_pages) == {"Ex 1", "Ex 2", "Ex 3"}, (
        f"TOC missing entries: extracted {toc_pages}"
    )

    for label in ("Ex 1", "Ex 2", "Ex 3"):
        assert toc_pages[label] == exhibit_label_pages[label], (
            f"TOC says {label} starts on page {toc_pages[label]} but "
            f"the exhibit actually starts on page "
            f"{exhibit_label_pages[label]} — legacy page_counter += 1 "
            f"bug not fixed"
        )
