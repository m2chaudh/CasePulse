# casepulse/case_theory/ui/argument_editor.py
"""Left-pane Argument editor for the Workbench page."""
from typing import Sequence
import streamlit as st

from casepulse.case_theory.models import (
    Argument, ArgumentType, Strength,
)
from casepulse.case_theory.repository import (
    list_arguments_for_contradiction, create_argument,
    update_argument, list_evidence_for_argument,
    list_statements_for_argument, get_witness,
)
from casepulse.case_theory.ui.source_row_card import (
    format_one_line_meta, icon_for,
)
from casepulse.case_theory.ui.picker_state import set_recent_argument_id


def _strength_color(s: Strength | None) -> str:
    return {
        Strength.STRONG: "#10b981",
        Strength.MODERATE: "#f59e0b",
        Strength.CIRCUMSTANTIAL: "#94a3b8",
    }.get(s, "#94a3b8")


def render(db, *, contradiction_id: int) -> None:
    args: Sequence[Argument] = list_arguments_for_contradiction(
        db, contradiction_id=contradiction_id,
    )

    for a in args:
        with st.container(border=True):
            colour = _strength_color(a.strength)
            st.markdown(
                f"**{a.title}**  "
                f"<span style='color:{colour}; font-size:0.85em'>"
                f"{a.argument_type.value if a.argument_type else '—'} · "
                f"{a.strength.value if a.strength else '—'}</span>",
                unsafe_allow_html=True,
            )
            if a.reasoning_text:
                st.markdown(a.reasoning_text)
            evidence_list = list_evidence_for_argument(db, a.id)
            if evidence_list:
                st.markdown(f"_Attached evidence ({len(evidence_list)}):_")
                for entry in evidence_list:
                    ev = entry["evidence"]
                    cols = st.columns([4, 1])
                    with cols[0]:
                        st.markdown(
                            f"- {format_one_line_meta(kind=ev.evidence_kind.value, subject=ev.snippet or ev.source_table)}"
                        )
                    with cols[1]:
                        if st.button("View as exhibit", key=f"vae_{ev.id}"):
                            st.info("Exhibit preview ships in Plan 1.3.")
                    if st.button("✎ refine snippet", key=f"ref_{ev.id}"):
                        from casepulse.case_theory.ui.refine_snippet_dialog import show as show_refine
                        show_refine(db, evidence_id=ev.id,
                                    source_table=ev.source_table,
                                    source_row_id=ev.source_row_id)

            # Witness statements pane — only shown for Witness-type arguments
            if a.argument_type == ArgumentType.WITNESS:
                st.markdown("**Linked witness statements**")
                linked_stmts = list_statements_for_argument(db, a.id)
                if linked_stmts:
                    for stmt in linked_stmts:
                        witness = get_witness(db, stmt.witness_id)
                        if witness:
                            name = witness.name
                            rel = f" ({witness.relationship})" if witness.relationship else ""
                        else:
                            name = f"Witness #{stmt.witness_id}"
                            rel = ""
                        st.markdown(
                            f"- **{name}**{rel} — \"{stmt.statement_text}\""
                        )
                else:
                    st.caption(
                        "No witness statements linked. "
                        "Add one from the **Witnesses** page."
                    )

            if st.button(f"Edit", key=f"edit_arg_{a.id}"):
                set_recent_argument_id(st.session_state, a.id)

            if st.button("Preview brief", key=f"preview_brief_{a.id}"):
                st.info("Brief preview ships in Plan 1.3 (export pipeline). "
                        "Until then, the data is in the DB and ready for export.")

    with st.expander("+ Add Argument"):
        with st.form(f"new_arg_{contradiction_id}"):
            title = st.text_input(
                "Title",
                help="A short label for this argument, e.g. 'Alibi — was at work on March 14'. "
                     "Appears as a heading in the brief.",
            )
            arg_type = st.selectbox(
                "Type",
                options=[None] + list(ArgumentType),
                format_func=lambda x: "—" if x is None else x.value,
                help="Alibi: shows the user wasn't there. Self-contradiction: shows the opposing "
                     "party's own statements conflict. Witness: a third party will testify. "
                     "Documentary: a document refutes the claim. Timing: events couldn't have happened "
                     "as alleged. Pattern: a pattern of similar false claims.",
            )
            strength = st.selectbox(
                "Strength",
                options=[None] + list(Strength),
                format_func=lambda x: "—" if x is None else x.value,
                help="Strong: bulletproof, leads at trial. Moderate: corroborating but not decisive. "
                     "Circumstantial: supports a pattern but needs other arguments alongside.",
            )
            reasoning = st.text_area(
                "Reasoning",
                help="Your analysis of why this argument holds. Keep it concise — "
                     "this becomes a paragraph in the brief.",
            )
            submit = st.form_submit_button("Add")
            if submit and title:
                create_argument(db, Argument(
                    contradiction_id=contradiction_id,
                    title=title,
                    argument_type=arg_type,
                    strength=strength,
                    reasoning_text=reasoning or None,
                ))
                st.rerun()
