from casepulse.case_theory.models import Theme
from casepulse.case_theory.repository import (
    create_theme, get_theme, list_themes, update_theme, delete_theme,
)


def test_create_and_get_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    theme = Theme(case_id=case_id, title="Pattern", description="d")
    saved = create_theme(db, theme)
    assert saved.id is not None
    got = get_theme(db, saved.id)
    assert got.title == "Pattern"


def test_list_themes_filtered_by_case(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_theme(db, Theme(case_id=case_id, title="T1"))
    create_theme(db, Theme(case_id=case_id, title="T2"))
    themes = list_themes(db, case_id=case_id)
    assert len(themes) == 2


def test_update_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="Old"))
    saved.title = "New"
    updated = update_theme(db, saved)
    assert updated.title == "New"
    assert get_theme(db, saved.id).title == "New"


def test_delete_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="X"))
    delete_theme(db, saved.id)
    assert get_theme(db, saved.id) is None
