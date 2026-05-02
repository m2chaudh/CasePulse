# tests/case_theory_ui/test_workbench_smoke.py
def test_workbench_page_loads_with_no_case(page_test):
    """Page renders without errors when no case is selected."""
    at = page_test("pages_modules/case_theory.py")
    at.run()
    assert not at.exception
    # Expect a "no case selected" message
    assert any("case" in (m.value or "").lower()
               for m in at.markdown if m.value)


def test_workbench_creates_contradiction(page_test, tmp_db_with_case):
    """Submitting the new-contradiction form creates a row."""
    db, case_id = tmp_db_with_case
    at = page_test("pages_modules/case_theory.py")
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


def test_view_as_exhibit_button_present(page_test, tmp_db_with_case):
    """Stub button is visible per attached evidence; clicking shows a 'coming
    in Plan 1.3' info message."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import (
        Contradiction, Argument, Evidence, EvidenceKind, EvidenceRole, ArgumentType, Strength
    )
    from casepulse.case_theory.repository import (
        create_contradiction, create_argument, create_evidence,
        attach_evidence_to_argument,
    )
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    a = create_argument(db, Argument(
        contradiction_id=c.id, title="t",
        argument_type=ArgumentType.ALIBI, strength=Strength.STRONG,
    ))
    conn = db._get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO emails (subject, body_text, sender_email, "
                "message_id, content_hash) VALUES "
                "('Subject', 'body text', 'a@x', '<m1>', 'h1')")
    conn.commit(); email_id = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=email_id,
    ))
    attach_evidence_to_argument(db, a.id, e.id, role=EvidenceRole.SUPPORTS)
    at = page_test("pages_modules/case_theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    button_labels = [b.label for b in at.button if b.label]
    assert any("view as exhibit" in (lbl or "").lower() for lbl in button_labels) \
           or any("preview brief" in (lbl or "").lower() for lbl in button_labels)


def test_refine_snippet_updates_char_range(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import Evidence, EvidenceKind
    from casepulse.case_theory.repository import (
        create_evidence, update_evidence_snippet,
    )
    conn = db._get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO emails (subject, body_text, sender_email, "
                "message_id, content_hash) VALUES "
                "('S', 'Para A.\\n\\nPara B.\\n\\nPara C.', 'a@x', '<m1>', 'h1')")
    conn.commit()
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=cur.lastrowid,
    ))
    # Refine to second paragraph
    update_evidence_snippet(db, e.id, char_start=8, char_end=15,
                            snippet="Para B.")
    cur.execute("SELECT char_start, char_end, snippet FROM evidence WHERE id = ?", (e.id,))
    row = cur.fetchone()
    assert row[0] == 8
    assert row[1] == 15
    assert row[2] == "Para B."


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
    at = page_test("pages_modules/case_theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "Was at party" in text


def test_argument_witness_statement_link(page_test, tmp_db_with_case):
    """When a Witness-type argument has linked statements, they surface in the editor."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import (
        Contradiction, Argument, ArgumentType, Strength,
        Witness, WitnessStatement,
    )
    from casepulse.case_theory.repository import (
        create_contradiction, create_argument,
        create_witness, create_witness_statement,
    )
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C-Witness"))
    a = create_argument(db, Argument(
        contradiction_id=c.id, title="Witness testifies",
        argument_type=ArgumentType.WITNESS, strength=Strength.STRONG,
    ))
    w = create_witness(db, Witness(case_id=case_id, name="Jane Doe",
                                    relationship="colleague"))
    create_witness_statement(db, WitnessStatement(
        witness_id=w.id,
        statement_text="She heard the conversation clearly.",
        argument_id=a.id,
    ))

    at = page_test("pages_modules/case_theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    assert "She heard the conversation clearly." in text
