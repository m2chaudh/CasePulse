import pytest
from datetime import datetime
from casepulse.case_theory.models import (
    Theme, Allegation, Contradiction, Argument, Evidence,
    EvidenceKind, ArgumentType, Strength, ContradictionStatus,
    AllegationStatus, EvidenceRole,
    Witness, WitnessType, WitnessStatus,
    WitnessStatement, WitnessStatementStatus,
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


def test_witness_model():
    w = Witness(case_id=1, name="Alice Nguyen", relationship="neighbour")
    assert w.case_id == 1
    assert w.name == "Alice Nguyen"
    assert w.relationship == "neighbour"
    assert w.status == WitnessStatus.INITIAL
    assert w.witness_type is None
    assert w.id is None


def test_witness_model_enum_coercion():
    w = Witness(
        case_id=2, name="Bob Smith",
        witness_type="fact",
        status="contacted",
    )
    assert w.witness_type == WitnessType.FACT
    assert w.status == WitnessStatus.CONTACTED


def test_witness_model_invalid_status():
    with pytest.raises(ValueError):
        Witness(case_id=1, name="X", status="not_valid")


def test_witness_statement_model():
    stmt = WitnessStatement(witness_id=5, statement_text="I saw the incident.")
    assert stmt.witness_id == 5
    assert stmt.statement_text == "I saw the incident."
    assert stmt.status == WitnessStatementStatus.DRAFT
    assert stmt.contradiction_id is None
    assert stmt.argument_id is None


def test_witness_statement_enum_coercion():
    stmt = WitnessStatement(
        witness_id=3,
        statement_text="She was there.",
        status="reviewed",
        contradiction_id=7,
        argument_id=12,
    )
    assert stmt.status == WitnessStatementStatus.REVIEWED
    assert stmt.contradiction_id == 7
    assert stmt.argument_id == 12
