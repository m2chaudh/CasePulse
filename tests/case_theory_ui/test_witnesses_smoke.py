"""Smoke test for the Witnesses page (pages_modules/witnesses.py)."""


def test_witnesses_page_loads_no_case(page_test, tmp_db):
    """Witnesses page renders without errors when no case exists."""
    at = page_test("pages_modules/witnesses.py")
    at.session_state.db = tmp_db
    at.run()
    assert not at.exception


def test_witnesses_page_loads_with_case(page_test, tmp_db_with_case):
    """Witnesses page renders without errors when a case exists."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/witnesses.py")
    at.session_state.db = db
    at.session_state.active_case_id = case_id
    at.run()
    assert not at.exception
    # Should show witnesses section heading
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "Witnesses" in text


def test_witnesses_page_shows_empty_state(page_test, tmp_db_with_case):
    """Witnesses page shows 'No witnesses yet' when none exist."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/witnesses.py")
    at.session_state.db = db
    at.session_state.active_case_id = case_id
    at.run()
    assert not at.exception
    # Caption for empty witness list
    captions = [c.value or "" for c in at.caption]
    assert any("no witnesses" in c.lower() for c in captions)


def test_witnesses_page_shows_existing_witness(page_test, tmp_db_with_case):
    """Witnesses page lists an existing witness."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.repository import create_witness
    from casepulse.case_theory.models import Witness, WitnessStatus
    create_witness(db, Witness(
        case_id=case_id, name="Alice Nguyen",
        relationship="neighbour",
        status=WitnessStatus.INITIAL,
    ))
    at = page_test("pages_modules/witnesses.py")
    at.session_state.db = db
    at.session_state.active_case_id = case_id
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "Alice Nguyen" in text
