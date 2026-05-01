import pytest
from datetime import datetime
from casepulse.case_theory.models import (
    Theme, Allegation, Contradiction, Argument, Evidence,
    EvidenceKind, ArgumentType, Strength, ContradictionStatus,
    AllegationStatus, EvidenceRole,
)

def test_theme_model():
    t = Theme(case_id=1, title="Pattern of false reports")
    assert t.case_id == 1

def test_argument_with_type_and_strength():
    a = Argument(
        contradiction_id=1, title="Was at party",
        argument_type=ArgumentType.ALIBI,
        strength=Strength.STRONG,
    )
    assert a.argument_type == ArgumentType.ALIBI
    assert a.strength == Strength.STRONG

def test_evidence_polymorphic():
    e = Evidence(
        evidence_kind=EvidenceKind.PHOTO,
        source_table="attachments",
        source_row_id=42,
    )
    assert e.evidence_kind == EvidenceKind.PHOTO

def test_invalid_argument_type():
    with pytest.raises(ValueError):
        Argument(contradiction_id=1, title="x", argument_type="not_a_type")
