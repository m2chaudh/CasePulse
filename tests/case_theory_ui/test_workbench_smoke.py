# tests/case_theory_ui/test_workbench_smoke.py
def test_workbench_page_loads_with_no_case(page_test):
    """Page renders without errors when no case is selected."""
    at = page_test("pages/11_Case_Theory.py")
    at.run()
    assert not at.exception
    # Expect a "no case selected" message
    assert any("case" in (m.value or "").lower()
               for m in at.markdown if m.value)


def test_workbench_creates_contradiction(page_test, tmp_db_with_case):
    """Submitting the new-contradiction form creates a row."""
    db, case_id = tmp_db_with_case
    at = page_test("pages/11_Case_Theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    # Find the headline input + submit
    headline_input = next((i for i in at.text_input if "headline" in i.label.lower()), None)
    assert headline_input is not None
    headline_input.set_value("C1 — false abuse claim").run()
    submit = next((b for b in at.button if "create" in b.label.lower()), None)
    assert submit is not None
    submit.click().run()
    from casepulse.case_theory.repository import list_contradictions
    rows = list_contradictions(db, case_id=case_id)
    assert any(r.headline == "C1 — false abuse claim" for r in rows)


def test_workbench_renders_arguments_for_contradiction(page_test, tmp_db_with_case):
    """When a contradiction has arguments, they appear in the left pane."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import Contradiction, Argument, ArgumentType, Strength
    from casepulse.case_theory.repository import create_contradiction, create_argument
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    create_argument(db, Argument(
        contradiction_id=c.id, title="Was at party",
        argument_type=ArgumentType.ALIBI, strength=Strength.STRONG,
    ))
    # Use real DB path so the page can reopen it
    at = page_test("pages/11_Case_Theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "Was at party" in text
