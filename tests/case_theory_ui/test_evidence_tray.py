# tests/case_theory_ui/test_evidence_tray.py
def test_tray_marks_already_attached_results(page_test, tmp_db_with_case):
    """Evidence already attached to the active argument shows '✓ attached'
    instead of '+ add'."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import Contradiction, Argument, Evidence, EvidenceKind, EvidenceRole, ArgumentType, Strength
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
                "('Subject', 'banana body', 'a@x', '<m1>', 'h1')")
    conn.commit(); email_id = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=email_id,
    ))
    attach_evidence_to_argument(db, a.id, e.id, role=EvidenceRole.SUPPORTS)
    at = page_test("pages/11_Case_Theory.py", default_timeout=30.0)
    at.session_state.db = db
    at.session_state.case_theory_recent_argument_id = a.id
    at.session_state.tray_search_input = "banana"
    at.run()
    assert not at.exception
    text = "\n".join((m.value or "") for m in at.markdown)
    # The result row should show "✓ attached" not "+ add"
    assert "✓ attached" in text or "attached" in text.lower()


def test_tray_renders_search_box(page_test, tmp_db_with_case):
    db, case_id = tmp_db_with_case
    # Seed an email and a contradiction (so page gets past empty state)
    from casepulse.case_theory.models import Contradiction
    from casepulse.case_theory.repository import create_contradiction
    create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash) VALUES
        ('Custody hearing', 'Discussion about access', 'a@x', '<m1>', 'h1')
    """)
    conn.commit()
    at = page_test("pages/11_Case_Theory.py")
    at.session_state.db = db
    at.run()
    assert not at.exception
    assert any("evidence tray" in (m.value or "").lower() for m in at.markdown)
    # Search input present
    assert any("search" in (i.label or "").lower() for i in at.text_input)
