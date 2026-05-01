# casepulse/case_theory/ui/contradiction_form.py
"""Create-Contradiction form. Used in two places:
- The "no contradictions yet" empty state in the Workbench
- A dedicated Contradictions list page (later — out of W1.2 scope)
"""
import streamlit as st

from casepulse.case_theory.models import (
    Contradiction, ContradictionStatus,
)
from casepulse.case_theory.repository import (
    create_contradiction, list_themes,
)


def render(db, *, case_id: int) -> int | None:
    """Render the form; returns new contradiction id on success, else None."""
    themes = list_themes(db, case_id=case_id)
    theme_options = {None: "—"}
    for t in themes:
        theme_options[t.id] = t.title
    with st.form(f"new_contradiction_{case_id}"):
        headline = st.text_input("Headline")
        theme_id = st.selectbox(
            "Theme",
            options=list(theme_options.keys()),
            format_func=lambda k: theme_options[k],
        )
        notes = st.text_area("Notes (optional)")
        submit = st.form_submit_button("Create")
        if submit and headline:
            new = create_contradiction(db, Contradiction(
                case_id=case_id,
                headline=headline,
                theme_id=theme_id,
                notes=notes or None,
                status=ContradictionStatus.DRAFT,
            ))
            return new.id
    return None
