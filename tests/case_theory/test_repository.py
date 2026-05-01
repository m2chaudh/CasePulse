from casepulse.case_theory.models import (
    Theme, Allegation, AllegationStatus,
    Contradiction, ContradictionStatus,
    Argument, ArgumentType, Strength,
    Evidence, EvidenceKind, EvidenceRole,
    Witness, WitnessType, WitnessStatus,
    WitnessStatement, WitnessStatementStatus,
)
from casepulse.case_theory.repository import (
    create_theme, get_theme, list_themes, update_theme, delete_theme,
    create_allegation, get_allegation, list_allegations,
    update_allegation, delete_allegation,
    create_contradiction, get_contradiction, list_contradictions,
    update_contradiction, link_allegation_to_contradiction,
    list_allegations_for_contradiction,
    create_argument, get_argument, list_arguments_for_contradiction,
    update_argument, delete_argument,
    create_evidence, attach_evidence_to_argument,
    list_evidence_for_argument, detach_evidence_from_argument,
    create_witness, get_witness, list_witnesses, update_witness, delete_witness,
    create_witness_statement, list_statements_for_witness,
    list_statements_for_argument, update_witness_statement,
    delete_witness_statement,
)


def test_create_and_get_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    theme = Theme(case_id=case_id, title="Pattern", description="d")
    saved = create_theme(db, theme)
    assert saved.id is not None
    got = get_theme(db, saved.id)
    assert got.title == "Pattern"


def test_list_themes_filtered_by_case(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_theme(db, Theme(case_id=case_id, title="T1"))
    create_theme(db, Theme(case_id=case_id, title="T2"))
    themes = list_themes(db, case_id=case_id)
    assert len(themes) == 2


def test_update_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="Old"))
    saved.title = "New"
    updated = update_theme(db, saved)
    assert updated.title == "New"
    assert get_theme(db, saved.id).title == "New"


def test_delete_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="X"))
    delete_theme(db, saved.id)
    assert get_theme(db, saved.id) is None


# ---------------------------------------------------------------------------
# Allegation tests
# ---------------------------------------------------------------------------

def test_create_and_get_allegation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    a = Allegation(case_id=case_id, title="X", claim_text="She said Y",
                    claimed_date="2024-03-14")
    saved = create_allegation(db, a)
    got = get_allegation(db, saved.id)
    assert got.claim_text == "She said Y"
    assert got.status == AllegationStatus.ACTIVE


# ---------------------------------------------------------------------------
# Contradiction + allegation linking tests
# ---------------------------------------------------------------------------

def test_create_contradiction_and_link_allegation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    a = create_allegation(db, Allegation(
        case_id=case_id, title="X", claim_text="text"))
    c = create_contradiction(db, Contradiction(
        case_id=case_id, headline="C1"))
    link_allegation_to_contradiction(db, c.id, a.id)
    linked = list_allegations_for_contradiction(db, c.id)
    assert len(linked) == 1
    assert linked[0].id == a.id


# ---------------------------------------------------------------------------
# Argument tests
# ---------------------------------------------------------------------------

def test_create_argument(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C"))
    arg = create_argument(db, Argument(
        contradiction_id=c.id, title="At party",
        argument_type=ArgumentType.ALIBI, strength=Strength.STRONG,
    ))
    got = get_argument(db, arg.id)
    assert got.argument_type == ArgumentType.ALIBI
    assert got.strength == Strength.STRONG


# ---------------------------------------------------------------------------
# Evidence + argument_evidence linking tests
# ---------------------------------------------------------------------------

def test_create_and_attach_evidence(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C"))
    arg = create_argument(db, Argument(contradiction_id=c.id, title="A"))
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.PHOTO,
        source_table="attachments", source_row_id=42,
    ))
    attach_evidence_to_argument(db, arg.id, e.id, role=EvidenceRole.SUPPORTS)
    listed = list_evidence_for_argument(db, arg.id)
    assert len(listed) == 1
    assert listed[0]["evidence"].source_row_id == 42
    assert listed[0]["role"] == EvidenceRole.SUPPORTS


# ---------------------------------------------------------------------------
# Witness + WitnessStatement CRUD tests
# ---------------------------------------------------------------------------

def test_create_and_get_witness(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    w = Witness(case_id=case_id, name="Jane Doe", relationship="neighbour",
                witness_type=WitnessType.FACT, status=WitnessStatus.INITIAL)
    saved = create_witness(db, w)
    assert saved.id is not None
    got = get_witness(db, saved.id)
    assert got.name == "Jane Doe"
    assert got.relationship == "neighbour"
    assert got.witness_type == WitnessType.FACT
    assert got.status == WitnessStatus.INITIAL


def test_list_witnesses_case_scoped(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    other_case_id = db.create_case(name="Other", case_number="O1")
    create_witness(db, Witness(case_id=case_id, name="Alice"))
    create_witness(db, Witness(case_id=case_id, name="Bob"))
    create_witness(db, Witness(case_id=other_case_id, name="Carol"))
    result = list_witnesses(db, case_id=case_id)
    assert len(result) == 2
    names = {w.name for w in result}
    assert names == {"Alice", "Bob"}
    other_result = list_witnesses(db, case_id=other_case_id)
    assert len(other_result) == 1
    assert other_result[0].name == "Carol"


def test_update_witness(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_witness(db, Witness(case_id=case_id, name="Alice",
                                       status=WitnessStatus.INITIAL))
    saved.name = "Alice Smith"
    saved.status = WitnessStatus.CONTACTED
    saved.witness_type = WitnessType.CHARACTER
    update_witness(db, saved)
    got = get_witness(db, saved.id)
    assert got.name == "Alice Smith"
    assert got.status == WitnessStatus.CONTACTED
    assert got.witness_type == WitnessType.CHARACTER


def test_delete_witness(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_witness(db, Witness(case_id=case_id, name="ToDelete"))
    delete_witness(db, saved.id)
    assert get_witness(db, saved.id) is None


def test_witness_statement_round_trip(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    w = create_witness(db, Witness(case_id=case_id, name="Alice"))
    stmt = create_witness_statement(db, WitnessStatement(
        witness_id=w.id,
        statement_text="She was present at the time.",
        statement_date="2024-01-15",
    ))
    assert stmt.id is not None
    stmts = list_statements_for_witness(db, w.id)
    assert len(stmts) == 1
    assert stmts[0].statement_text == "She was present at the time."
    assert stmts[0].statement_date == "2024-01-15"
    assert stmts[0].status == WitnessStatementStatus.DRAFT


def test_list_statements_for_argument(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    w = create_witness(db, Witness(case_id=case_id, name="Alice"))
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    arg = create_argument(db, Argument(contradiction_id=c.id, title="A1",
                                        argument_type=ArgumentType.WITNESS))
    # Statement linked to this argument
    s1 = create_witness_statement(db, WitnessStatement(
        witness_id=w.id,
        statement_text="Key testimony.",
        argument_id=arg.id,
        contradiction_id=c.id,
    ))
    # Statement NOT linked to any argument
    s2 = create_witness_statement(db, WitnessStatement(
        witness_id=w.id,
        statement_text="Unrelated note.",
    ))
    linked = list_statements_for_argument(db, arg.id)
    assert len(linked) == 1
    assert linked[0].id == s1.id
    assert linked[0].statement_text == "Key testimony."


def test_update_witness_statement(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    w = create_witness(db, Witness(case_id=case_id, name="Alice"))
    stmt = create_witness_statement(db, WitnessStatement(
        witness_id=w.id, statement_text="Original text."))
    stmt.statement_text = "Updated text."
    stmt.status = WitnessStatementStatus.REVIEWED
    update_witness_statement(db, stmt)
    stmts = list_statements_for_witness(db, w.id)
    assert stmts[0].statement_text == "Updated text."
    assert stmts[0].status == WitnessStatementStatus.REVIEWED


def test_delete_witness_statement(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    w = create_witness(db, Witness(case_id=case_id, name="Alice"))
    stmt = create_witness_statement(db, WitnessStatement(
        witness_id=w.id, statement_text="To be deleted."))
    delete_witness_statement(db, stmt.id)
    assert list_statements_for_witness(db, w.id) == []


def test_witness_cascade_deletes_statements(tmp_db_with_case):
    """Deleting a witness should cascade-delete all their statements."""
    db, case_id = tmp_db_with_case
    w = create_witness(db, Witness(case_id=case_id, name="Cascade Test"))
    create_witness_statement(db, WitnessStatement(
        witness_id=w.id, statement_text="Statement 1"))
    create_witness_statement(db, WitnessStatement(
        witness_id=w.id, statement_text="Statement 2"))
    delete_witness(db, w.id)
    # get_witness returns None, statements are gone
    assert get_witness(db, w.id) is None
    assert list_statements_for_witness(db, w.id) == []
