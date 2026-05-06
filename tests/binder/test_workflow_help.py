from casepulse.ui.workflow_help import compute_workflow_state, WorkflowState


def test_initial_state_all_false(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    state = compute_workflow_state(db, case_id=case_id)
    assert state.has_account is False
    assert state.has_flagged_sender is False
    assert state.has_email is False
    assert state.has_document is False


def test_account_present(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        conn.execute(
            "INSERT INTO accounts (email, provider) VALUES ('a@b','imap')"
        )
    state = compute_workflow_state(db, case_id=case_id)
    assert state.has_account is True


def test_flagged_sender_present(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO case_relevant_senders (case_id, address, role, active)
               VALUES (?, 'x@y', 'crown', 1)""",
            (case_id,))
    state = compute_workflow_state(db, case_id=case_id)
    assert state.has_flagged_sender is True


def test_email_present(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO emails (subject, sender_email, date_received)
               VALUES ('S','x@y','2024-03-14T10:00:00')""")
        eid = cur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('email', ?, ?)",
            (eid, case_id))
    state = compute_workflow_state(db, case_id=case_id)
    assert state.has_email is True


def test_document_present(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    with db._get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO documents (filename, file_path, content_hash, created_at)
               VALUES ('a.pdf','/tmp/a.pdf','h','2024-03-14T08:00:00')""")
        did = cur.lastrowid
        conn.execute(
            "INSERT INTO evidence_tags (item_type, item_id, case_id) VALUES ('document', ?, ?)",
            (did, case_id))
    state = compute_workflow_state(db, case_id=case_id)
    assert state.has_document is True
