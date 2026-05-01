# tests/case_theory_ui/test_picker_state.py
import pytest
from casepulse.case_theory.ui.picker_state import (
    get_recent_argument_id, set_recent_argument_id,
    get_tray_query, set_tray_query,
)


def test_recent_argument_id_default_none():
    state = {}
    assert get_recent_argument_id(state) is None


def test_recent_argument_id_set_and_get():
    state = {}
    set_recent_argument_id(state, 42)
    assert get_recent_argument_id(state) == 42


def test_tray_query_persists_across_calls():
    state = {}
    set_tray_query(state, "march photos")
    assert get_tray_query(state) == "march photos"
    set_tray_query(state, "")
    assert get_tray_query(state) == ""
