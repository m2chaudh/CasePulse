# tests/case_theory_ui/test_view_source_dialog.py
def test_view_source_dialog_renders_for_email(page_test, tmp_db_with_case):
    db, case_id = tmp_db_with_case
    conn = db._get_conn(); cur = conn.cursor()
    cur.execute("INSERT INTO emails (subject, body_text, sender_email, "
                "message_id, content_hash) VALUES "
                "('Test', 'Lorem ipsum body', 'a@x', '<m1>', 'h1')")
    conn.commit()
    # The dialog is invoked imperatively; smoke-test the renderer function
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    panel_text = render_source_panel(db, source_table="emails",
                                     source_row_id=cur.lastrowid,
                                     inline=True)
    assert "Lorem ipsum body" in panel_text
    assert "a@x" in panel_text
