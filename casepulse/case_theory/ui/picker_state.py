# casepulse/case_theory/ui/picker_state.py
"""Helpers for reading/writing st.session_state in the Workbench / Search UI.

All helpers take a `state` mapping (typically `st.session_state`) so they can
be unit-tested without spinning up Streamlit.
"""
from typing import Any, Mapping, MutableMapping


_RECENT_ARG_KEY = "case_theory_recent_argument_id"
_TRAY_QUERY_KEY = "case_theory_tray_query"
_TRAY_FACETS_KEY = "case_theory_tray_facets"


def get_recent_argument_id(state: Mapping[str, Any]) -> int | None:
    return state.get(_RECENT_ARG_KEY)


def set_recent_argument_id(state: MutableMapping[str, Any], arg_id: int) -> None:
    state[_RECENT_ARG_KEY] = arg_id


def get_tray_query(state: Mapping[str, Any]) -> str:
    return state.get(_TRAY_QUERY_KEY, "")


def set_tray_query(state: MutableMapping[str, Any], query: str) -> None:
    state[_TRAY_QUERY_KEY] = query


def get_tray_facets(state: Mapping[str, Any]) -> dict:
    return state.get(_TRAY_FACETS_KEY, {})


def set_tray_facets(state: MutableMapping[str, Any], facets: dict) -> None:
    state[_TRAY_FACETS_KEY] = facets
