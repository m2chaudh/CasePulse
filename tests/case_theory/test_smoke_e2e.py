"""Smoke test exercising the full Plan-1 surface end-to-end."""
from casepulse.case_theory.models import (
    Theme, Allegation, Contradiction, Argument, Evidence,
    ArgumentType, Strength, EvidenceKind, EvidenceRole,
)
from casepulse.case_theory.repository import (
    create_theme, create_allegation, create_contradiction,
    link_allegation_to_contradiction, create_argument, create_evidence,
    attach_evidence_to_argument, list_evidence_for_argument,
    verify_evidence_hash,
)
from casepulse.case_theory.audit_chain import log_chained, verify_chain
from casepulse.search.retrieval import hybrid_search


def test_build_contradiction_end_to_end(tmp_db_with_case, monkeypatch):
    db, case_id = tmp_db_with_case
    # Seed an email — use account_id=NULL (column is nullable; no accounts row needed)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id, date_received)
        VALUES ('Custody', 'access denied for the third time',
                'opp@x.com', '<m1>', 'h1', NULL, '2024-03-14')
    """)
    conn.commit()
    email_id = cur.lastrowid

    # Confirm FTS5 trigger fired so BM25 can find it
    fts_count = cur.execute(
        "SELECT COUNT(*) FROM emails_fts WHERE emails_fts MATCH ?", ("denied",)
    ).fetchone()[0]
    assert fts_count == 1, "FTS5 trigger did not fire on INSERT"

    # Build case theory
    theme = create_theme(db, Theme(
        case_id=case_id, title="Pattern of access denial"))
    alleg = create_allegation(db, Allegation(
        case_id=case_id, title="Access denied 2024-03-14",
        claim_text="Access was refused", claimed_date="2024-03-14"))
    contra = create_contradiction(db, Contradiction(
        case_id=case_id, headline="False access-denial claim",
        theme_id=theme.id))
    link_allegation_to_contradiction(db, contra.id, alleg.id)
    arg = create_argument(db, Argument(
        contradiction_id=contra.id, title="Email shows we did meet",
        argument_type=ArgumentType.DOCUMENTARY,
        strength=Strength.STRONG))
    evi = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=email_id))
    attach_evidence_to_argument(db, arg.id, evi.id, role=EvidenceRole.SUPPORTS)

    # Verify evidence listing and hash integrity
    listed = list_evidence_for_argument(db, arg.id)
    assert len(listed) == 1
    assert listed[0]["evidence"].id == evi.id
    assert verify_evidence_hash(db, evi.id) is True

    # Search finds the email via BM25 (embedding stubbed to empty)
    monkeypatch.setattr("casepulse.search.retrieval._embedding_search",
                        lambda *a, **kw: [])
    hits = hybrid_search(db, "denied", k=10)
    assert any(h.citation.row_id == email_id for h in hits), (
        f"Expected email_id={email_id} in hits, got: "
        f"{[(h.citation.table, h.citation.row_id) for h in hits]}"
    )

    # Audit chain: log an action and verify chain integrity
    log_chained(db, action="contradiction_created",
                details={"contradiction_id": contra.id})
    assert verify_chain(db) is True
