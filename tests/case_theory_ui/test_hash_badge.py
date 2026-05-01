# tests/case_theory_ui/test_hash_badge.py
from casepulse.case_theory.ui.hash_badge import (
    badge_for_evidence, BadgeStatus,
)


def test_badge_verified():
    b = badge_for_evidence(verified=True)
    assert b.status == BadgeStatus.VERIFIED
    assert "✓" in b.label


def test_badge_check():
    b = badge_for_evidence(verified=False)
    assert b.status == BadgeStatus.CHECK
    assert "⚠" in b.label
