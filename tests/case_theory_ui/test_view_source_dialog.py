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


def test_render_source_panel_uses_email_renderer_for_emails(tmp_db_with_case):
    """Emails are rendered via email_renderer (paragraphs preserved, blockquotes)."""
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    body = "Reply line.\n\n> earlier quoted line\n\nMore reply."
    cur.execute(
        "INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        ("S", body, "a@x", "<m1>", "h1"),
    )
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid, inline=True,
    )
    assert "<pre>" in panel_text
    assert "<blockquote>" in panel_text
    assert "earlier quoted line" in panel_text


def test_render_source_panel_with_thread_includes_earlier_section(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    body = "Current message.\n\nOn Mon, Mar 14 2024, Jane wrote:\n> ancient\n"
    cur.execute(
        "INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        ("S", body, "a@x", "<m2>", "h2"),
    )
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid, inline=True,
    )
    assert "Current message." in panel_text
    # Earlier section should be marked clearly
    assert "earlier replies" in panel_text.lower() or "ancient" in panel_text


def test_render_source_panel_highlights_cited_span(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)"
        " VALUES (?, ?, ?, ?, ?)",
        ("S", "Hello world this is a long body.", "a@x", "<m3>", "h3"),
    )
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    # Pass char range (6, 11) which covers "world"
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid,
        inline=True, char_start=6, char_end=11,
    )
    assert '<mark id="cited-highlight">world</mark>' in panel_text
    assert "scrollIntoView" in panel_text
