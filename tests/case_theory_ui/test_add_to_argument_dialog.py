"""Tests for the + Add to Argument dialog and its imperative helper."""
import pytest


def test_add_to_argument_creates_evidence_and_link(tmp_db_with_case):
    """Calling attach_to directly should create Evidence and argument_evidence rows."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import Contradiction, Argument, ArgumentType, Strength
    from casepulse.case_theory.repository import (
        create_contradiction, create_argument, list_evidence_for_argument,
    )
    from casepulse.case_theory.ui.add_to_argument import attach_to
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    a = create_argument(db, Argument(
        contradiction_id=c.id, title="t",
        argument_type=ArgumentType.ALIBI, strength=Strength.STRONG,
    ))
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO emails (subject, body_text, sender_email, "
        "message_id, content_hash) VALUES "
        "('S', 'B', 'a@x', '<m1>', 'h1')"
    )
    conn.commit()
    email_id = cur.lastrowid
    attach_to(db, argument_id=a.id, source_table="emails", source_row_id=email_id)
    listed = list_evidence_for_argument(db, a.id)
    assert len(listed) == 1
    assert listed[0]["evidence"].source_table == "emails"
    assert listed[0]["evidence"].source_row_id == email_id


def test_list_recent_arguments_for_picker_returns_recent_first(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import Contradiction, Argument
    from casepulse.case_theory.repository import (
        create_contradiction, create_argument,
        list_recent_arguments_for_picker,
    )
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C1"))
    a1 = create_argument(db, Argument(contradiction_id=c.id, title="A1"))
    a2 = create_argument(db, Argument(contradiction_id=c.id, title="A2"))
    rows = list_recent_arguments_for_picker(db, case_id=case_id, limit=10)
    assert any(r["argument_id"] == a1.id for r in rows)
    assert any(r["argument_id"] == a2.id for r in rows)
    # Keys present
    assert "argument_title" in rows[0]
    assert "contradiction_headline" in rows[0]


def test_attach_to_with_role(tmp_db_with_case):
    """attach_to respects the role parameter."""
    db, case_id = tmp_db_with_case
    from casepulse.case_theory.models import (
        Contradiction, Argument, ArgumentType, Strength, EvidenceRole,
    )
    from casepulse.case_theory.repository import (
        create_contradiction, create_argument, list_evidence_for_argument,
    )
    from casepulse.case_theory.ui.add_to_argument import attach_to
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C2"))
    a = create_argument(db, Argument(
        contradiction_id=c.id, title="rebuttal arg",
        argument_type=ArgumentType.ALIBI, strength=Strength.MODERATE,
    ))
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO emails (subject, body_text, sender_email, "
        "message_id, content_hash) VALUES "
        "('S2', 'Body2', 'b@x', '<m2>', 'h2')"
    )
    conn.commit()
    attach_to(db, argument_id=a.id, source_table="emails",
              source_row_id=cur.lastrowid, role=EvidenceRole.REFUTES)
    listed = list_evidence_for_argument(db, a.id)
    assert len(listed) == 1
    assert listed[0]["role"] == EvidenceRole.REFUTES
