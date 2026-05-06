"""Spot-check that non-trivial form fields across the app pass help= text.

This test reads the source of selected files and asserts a minimum number
of `help=` arguments appear. It's an approximate quality check, not a strict
audit — if the count drops below the threshold, someone removed help text.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _count_help_args(path: Path) -> int:
    text = path.read_text()
    # Count occurrences of `help="` and `help='` — both quote styles
    return text.count("help=\"") + text.count("help='")


def test_cases_page_has_field_helps():
    assert _count_help_args(ROOT / "pages_modules/cases.py") >= 5


def test_witnesses_page_has_field_helps():
    assert _count_help_args(ROOT / "pages_modules/witnesses.py") >= 4


def test_argument_editor_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/argument_editor.py") >= 4


def test_contradiction_form_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/contradiction_form.py") >= 3


def test_facets_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/facets.py") >= 3
