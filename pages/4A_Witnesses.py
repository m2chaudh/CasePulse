"""Witnesses — first-class people who can testify, distinct from Arguments."""
import streamlit as st
from components.page_init import init_page

st.set_page_config(page_title="Witnesses — CasePulse", layout="wide")

db, config = init_page()

st.markdown("## Witnesses")
st.markdown("Manage character witnesses and fact witnesses for your case. Each witness can have multiple statements linked to specific Contradictions or Arguments.")

# Active case
cases = db.get_cases()
if not cases:
    st.info("No cases yet. Go to **Cases** to create one.")
    st.stop()

case_options = {f"{c['name']} ({c['case_type']})": c["id"] for c in cases}
default_idx = 0
if "active_case_id" in st.session_state:
    for i, k in enumerate(case_options.keys()):
        if case_options[k] == st.session_state["active_case_id"]:
            default_idx = i
            break
selected_label = st.sidebar.selectbox("Active case", list(case_options.keys()), index=default_idx)
active_case_id = case_options[selected_label]
st.session_state["active_case_id"] = active_case_id

# List + select witness
from casepulse.case_theory.repository import (
    list_witnesses, get_witness, create_witness, update_witness, delete_witness,
    list_statements_for_witness, create_witness_statement, update_witness_statement,
    delete_witness_statement, list_contradictions, list_arguments_for_contradiction,
)
from casepulse.case_theory.models import (
    Witness, WitnessType, WitnessStatus,
    WitnessStatement, WitnessStatementStatus,
)

witnesses = list_witnesses(db, case_id=active_case_id)

left, right = st.columns([1, 2])

with left:
    st.markdown("### Witness list")
    if witnesses:
        for w in witnesses:
            type_badge = w.witness_type.value if w.witness_type else "—"
            status_badge = w.status.value
            with st.container(border=True):
                st.markdown(f"**{w.name}**")
                st.caption(f"{w.relationship or '—'} · {type_badge} · {status_badge}")
                stmts = list_statements_for_witness(db, witness_id=w.id)
                st.caption(f"{len(stmts)} statement{'s' if len(stmts) != 1 else ''}")
                if st.button("Open", key=f"open_witness_{w.id}"):
                    st.session_state["active_witness_id"] = w.id
                    st.rerun()
    else:
        st.caption("No witnesses yet.")

    with st.expander("+ Add Witness"):
        with st.form(f"new_witness_{active_case_id}"):
            name = st.text_input("Name")
            relationship = st.text_input("Relationship", placeholder="friend, family, neighbor, professional, …")
            witness_type = st.selectbox(
                "Type",
                options=[None] + list(WitnessType),
                format_func=lambda x: "—" if x is None else x.value,
            )
            contact_info = st.text_area("Contact info", placeholder="phone, email, address (optional)")
            status = st.selectbox(
                "Status",
                options=list(WitnessStatus),
                format_func=lambda x: x.value,
                index=0,
            )
            notes = st.text_area("Notes")
            if st.form_submit_button("Add witness") and name:
                w = create_witness(db, Witness(
                    case_id=active_case_id, name=name,
                    relationship=relationship or None,
                    witness_type=witness_type,
                    contact_info=contact_info or None,
                    status=status, notes=notes or None,
                ))
                st.session_state["active_witness_id"] = w.id
                st.rerun()

with right:
    active_witness_id = st.session_state.get("active_witness_id")
    if not active_witness_id:
        st.info("Select a witness on the left, or add a new one.")
    else:
        w = get_witness(db, active_witness_id)
        if not w or w.case_id != active_case_id:
            st.warning("Selected witness isn't in the active case.")
        else:
            # Editable fields
            st.markdown(f"### {w.name}")
            new_name = st.text_input("Name", value=w.name, key=f"wname_{w.id}")
            new_rel = st.text_input("Relationship", value=w.relationship or "", key=f"wrel_{w.id}")
            new_type = st.selectbox(
                "Type",
                options=[None] + list(WitnessType),
                format_func=lambda x: "—" if x is None else x.value,
                index=0 if w.witness_type is None else (list(WitnessType).index(w.witness_type) + 1),
                key=f"wtype_{w.id}",
            )
            new_contact = st.text_area("Contact info", value=w.contact_info or "", key=f"wcontact_{w.id}")
            new_status = st.selectbox(
                "Status",
                options=list(WitnessStatus),
                format_func=lambda x: x.value,
                index=list(WitnessStatus).index(w.status),
                key=f"wstatus_{w.id}",
            )
            new_notes = st.text_area("Notes", value=w.notes or "", key=f"wnotes_{w.id}")
            cols = st.columns([1, 1, 4])
            with cols[0]:
                if st.button("Save", key=f"save_witness_{w.id}"):
                    w.name = new_name
                    w.relationship = new_rel or None
                    w.witness_type = new_type
                    w.contact_info = new_contact or None
                    w.status = new_status
                    w.notes = new_notes or None
                    update_witness(db, w)
                    st.toast("Saved")
                    st.rerun()
            with cols[1]:
                if st.button("Delete", key=f"del_witness_{w.id}", type="secondary"):
                    delete_witness(db, w.id)
                    st.session_state.pop("active_witness_id", None)
                    st.rerun()

            st.markdown("---")
            st.markdown("### Statements")
            statements = list_statements_for_witness(db, witness_id=w.id)

            # Existing statements
            for stmt in statements:
                with st.container(border=True):
                    st.markdown(stmt.statement_text)
                    cap_parts = []
                    if stmt.statement_date:
                        cap_parts.append(f"Date: {stmt.statement_date}")
                    if stmt.contradiction_id:
                        cap_parts.append(f"Contradiction #{stmt.contradiction_id}")
                    if stmt.argument_id:
                        cap_parts.append(f"Argument #{stmt.argument_id}")
                    cap_parts.append(f"Status: {stmt.status.value}")
                    st.caption(" · ".join(cap_parts))
                    cols = st.columns([1, 1, 4])
                    with cols[0]:
                        if st.button("Edit", key=f"edit_stmt_{stmt.id}"):
                            st.session_state[f"editing_stmt_{stmt.id}"] = True
                            st.rerun()
                    with cols[1]:
                        if st.button("Delete", key=f"del_stmt_{stmt.id}", type="secondary"):
                            delete_witness_statement(db, stmt.id)
                            st.rerun()
                    if st.session_state.get(f"editing_stmt_{stmt.id}"):
                        # Edit form (simplified — let the user re-enter a few fields)
                        new_text = st.text_area(
                            "Statement", value=stmt.statement_text,
                            key=f"editstmt_text_{stmt.id}",
                        )
                        new_date = st.text_input(
                            "Statement date (YYYY-MM-DD)",
                            value=stmt.statement_date or "",
                            key=f"editstmt_date_{stmt.id}",
                        )
                        if st.button("Save changes", key=f"savestmt_{stmt.id}"):
                            stmt.statement_text = new_text
                            stmt.statement_date = new_date or None
                            update_witness_statement(db, stmt)
                            st.session_state.pop(f"editing_stmt_{stmt.id}", None)
                            st.rerun()

            # Add statement form
            with st.expander("+ Add Statement"):
                # Pull contradictions and arguments for this case for the picker
                contras = list_contradictions(db, case_id=active_case_id)
                contra_options = {None: "—"}
                for c in contras:
                    contra_options[c.id] = c.headline
                with st.form(f"new_stmt_{w.id}"):
                    text = st.text_area("Statement (what they will say)")
                    sdate = st.text_input("Statement date (YYYY-MM-DD, optional)")
                    contra_id = st.selectbox(
                        "Linked Contradiction (optional)",
                        options=list(contra_options.keys()),
                        format_func=lambda k: contra_options[k],
                    )
                    arg_id = None
                    if contra_id:
                        args = list_arguments_for_contradiction(db, contradiction_id=contra_id)
                        arg_options = {None: "—"}
                        for a in args:
                            arg_options[a.id] = a.title
                        arg_id = st.selectbox(
                            "Linked Argument (optional)",
                            options=list(arg_options.keys()),
                            format_func=lambda k: arg_options[k],
                        )
                    if st.form_submit_button("Add statement") and text:
                        create_witness_statement(db, WitnessStatement(
                            witness_id=w.id, statement_text=text,
                            statement_date=sdate or None,
                            contradiction_id=contra_id, argument_id=arg_id,
                        ))
                        st.rerun()
