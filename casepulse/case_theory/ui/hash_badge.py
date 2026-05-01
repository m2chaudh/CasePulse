# casepulse/case_theory/ui/hash_badge.py
"""Hash verification badge: ✓ verified or ⚠ check.

The badge's verified state is computed by `repository.verify_evidence_hash`
in the calling page; this helper just maps that bool to a label/colour pair.
"""
from dataclasses import dataclass
from enum import Enum


class BadgeStatus(str, Enum):
    VERIFIED = "verified"
    CHECK = "check"


@dataclass
class Badge:
    status: BadgeStatus
    label: str
    colour: str   # hex


def badge_for_evidence(*, verified: bool) -> Badge:
    if verified:
        return Badge(
            status=BadgeStatus.VERIFIED,
            label="✓ verified",
            colour="#10b981",  # emerald-500
        )
    return Badge(
        status=BadgeStatus.CHECK,
        label="⚠ check",
        colour="#f59e0b",  # amber-500
    )
