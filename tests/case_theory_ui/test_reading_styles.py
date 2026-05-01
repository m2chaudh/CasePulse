# tests/case_theory_ui/test_reading_styles.py
from casepulse.case_theory.ui.reading_styles import (
    GLOBAL_CSS, build_inject_block,
)


def test_global_css_includes_max_width():
    assert "max-width: 1100px" in GLOBAL_CSS


def test_global_css_includes_reading_content_class():
    assert ".reading-content" in GLOBAL_CSS
    assert "max-width: 720px" in GLOBAL_CSS
    assert "ui-serif" in GLOBAL_CSS or "Georgia" in GLOBAL_CSS
    assert "line-height: 1.7" in GLOBAL_CSS


def test_build_inject_block_returns_style_tag():
    out = build_inject_block()
    assert out.startswith("<style>")
    assert out.endswith("</style>")
    assert "max-width: 1100px" in out
    assert ".reading-content" in out
