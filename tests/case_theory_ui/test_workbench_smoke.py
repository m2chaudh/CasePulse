# tests/case_theory_ui/test_workbench_smoke.py
def test_workbench_page_loads_with_no_case(page_test):
    """Page renders without errors when no case is selected."""
    at = page_test("pages/11_Case_Theory.py")
    at.run()
    assert not at.exception
    # Expect a "no case selected" message
    assert any("case" in (m.value or "").lower()
               for m in at.markdown if m.value)


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
