# tests/case_theory_ui/test_workbench_smoke.py
def test_workbench_page_loads_with_no_case(page_test):
    """Page renders without errors when no case is selected."""
    at = page_test("pages/11_Case_Theory.py")
    at.run()
    assert not at.exception
    # Expect a "no case selected" message
    assert any("case" in (m.value or "").lower()
               for m in at.markdown if m.value)
