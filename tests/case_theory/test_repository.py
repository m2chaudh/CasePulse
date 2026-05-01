from casepulse.case_theory.models import (
    Theme, Allegation, AllegationStatus,
    Contradiction, ContradictionStatus,
    Argument, ArgumentType, Strength,
    Evidence, EvidenceKind, EvidenceRole,
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
