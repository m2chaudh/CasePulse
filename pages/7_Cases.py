"""Cases & Evidence Manager — manage cases, tag evidence, add annotations, assign exhibits."""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from casepulse.legal.exhibits import (
    LEGAL_ISSUES, FLAGS, generate_exhibit_label, preview_exhibit_labels,
)

st.set_page_config(page_title="CasePulse - Cases", page_icon="CP", layout="wide")


from components.page_init import init_page
db, config = init_page()

st.markdown("## Cases & Evidence Manager")

# ── Case Management ──
cases = db.get_cases()

if not cases:
    st.info("No cases created yet. Create your first case below.")

# Create new case
with st.expander("Create New Case", expanded=not cases):
    col1, col2 = st.columns(2)
    with col1:
        case_name = st.text_input("Case Name", placeholder="e.g., Family Law — Smith v. Smith")
        case_type = st.selectbox("Case Type", ["family", "criminal"],
                                  format_func=lambda x: {"family": "Family Law", "criminal": "Criminal Defence"}[x])
    with col2:
        case_number = st.text_input("Court File Number (optional)", placeholder="e.g., FC-2025-12345")
        exhibit_format = st.selectbox(
            "Exhibit Numbering Format",
            ["alpha", "bates", "numerical", "system"],
            format_func=lambda x: {
                "alpha": "Alphabetical (Exhibit A, B, C...)",
                "bates": "Bates Numbering (BATES_00001)",
                "numerical": "Numerical (Exhibit 1, 2, 3...)",
                "system": "System-Generated (Page A-1)",
            }[x],
        )
    exhibit_prefix = st.text_input(
        "Exhibit Prefix (optional)",
        placeholder="e.g., SMITH for SMITH_00001 or leave blank",
        help="Used in Bates: PREFIX_00001. In Alpha/Numerical: Exhibit PREFIX-A",
    )
    case_desc = st.text_area("Description (optional)", placeholder="Brief description of the case...")

    if st.button("Create Case", type="primary", disabled=not case_name):
        case_id = db.create_case(
            name=case_name, case_type=case_type, case_number=case_number,
            description=case_desc, exhibit_format=exhibit_format,
            exhibit_prefix=exhibit_prefix,
        )
        db.log_action("case_created", f"Created case: {case_name} ({case_type})")
        st.success(f"Case created: {case_name}")
        st.rerun()

if not cases:
    st.stop()

# ── Case Selector ──
st.divider()
case_options = {c["id"]: f"{c['name']} ({c['case_type'].title()})" for c in cases}
selected_case_id = st.selectbox(
    "Select Case",
    list(case_options.keys()),
    format_func=lambda x: case_options[x],
    key="active_case",
)
active_case = db.get_case(selected_case_id)

# Case info
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.caption(f"Type: {active_case['case_type'].title()}")
with col2:
    st.caption(f"File #: {active_case.get('case_number') or 'N/A'}")
with col3:
    st.caption(f"Format: {active_case.get('exhibit_format', 'alpha').title()}")
with col4:
    next_labels = preview_exhibit_labels(selected_case_id, db, 3)
    st.caption(f"Next exhibits: {', '.join(next_labels)}")

# ── Tabs ──
tab_evidence, tab_annotate, tab_collections, tab_settings = st.tabs([
    "Tag Evidence", "Annotations", "Collections", "Case Settings"
])

# ── Tab 1: Tag Evidence ──
with tab_evidence:
    st.markdown("### Tag Evidence Items")

    # Source and filter
    col1, col2, col3 = st.columns(3)
    with col1:
        source_type = st.selectbox("Source", ["Emails", "Chat Messages"], key="ev_source")
    with col2:
        # Get legal issues for this case type
        issues_for_type = LEGAL_ISSUES.get(active_case["case_type"], [])
        issue_filter = st.selectbox(
            "Filter by Issue",
            ["All"] + [label for _, label in issues_for_type],
            key="ev_issue_filter",
        )
    with col3:
        flag_filter = st.selectbox(
            "Filter by Flag",
            ["All"] + [label for _, label in FLAGS],
            key="ev_flag_filter",
        )

    search = st.text_input("Search", placeholder="Search emails/messages...", key="ev_search")

    # Fetch items
    if source_type == "Emails":
        items = db.get_emails(
            keyword=search if search else None,
            date_start=config.date_start,
            date_end=config.date_end,
            limit=200,
        )
        item_type = "email"
    else:
        items = db.get_chat_messages(
            keyword=search if search else None,
            date_start=config.date_start,
            date_end=config.date_end,
            limit=200,
        )
        item_type = "chat"

    if not items:
        st.info(f"No {source_type.lower()} found. Fetch emails or import chats first.")
    else:
        # Bulk operations
        st.markdown("#### Bulk Operations")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            bulk_issue = st.selectbox(
                "Legal Issue",
                [""] + [code for code, _ in issues_for_type],
                format_func=lambda x: dict(issues_for_type).get(x, "Select issue...") if x else "Select issue...",
                key="bulk_issue",
            )
        with col2:
            bulk_flag = st.selectbox(
                "Flag",
                [code for code, _ in FLAGS],
                format_func=lambda x: dict(FLAGS).get(x, x),
                key="bulk_flag",
            )
        with col3:
            bulk_collection = st.text_input("Collection", placeholder="e.g., Financial Bundle", key="bulk_coll")
        with col4:
            auto_exhibit = st.checkbox("Auto-assign exhibit #", key="bulk_exhibit")

        # Select-all
        if f"selected_{item_type}" not in st.session_state:
            st.session_state[f"selected_{item_type}"] = set()

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("Select All Visible"):
                st.session_state[f"selected_{item_type}"] = {i["id"] for i in items}
                st.rerun()
        with col2:
            if st.button("Deselect All"):
                st.session_state[f"selected_{item_type}"] = set()
                st.rerun()

        selected = st.session_state[f"selected_{item_type}"]
        if selected and st.button(
            f"Tag {len(selected)} selected items", type="primary"
        ):
            for item_id in selected:
                exhibit_label = ""
                if auto_exhibit:
                    exhibit_label = generate_exhibit_label(selected_case_id, db)
                db.tag_evidence(
                    item_type, item_id, selected_case_id,
                    legal_issue=bulk_issue,
                    exhibit_label=exhibit_label,
                    flag=bulk_flag,
                    collection=bulk_collection,
                )
            db.log_action("evidence_tagged", f"Tagged {len(selected)} {item_type} items to case {active_case['name']}")
            st.success(f"Tagged {len(selected)} items!")
            st.session_state[f"selected_{item_type}"] = set()
            st.rerun()

        st.markdown("---")

        # Item list
        for item in items:
            item_id = item["id"]
            existing_tag = db.get_evidence_tag(item_type, item_id, selected_case_id)

            # Build display
            if item_type == "email":
                dt = (item.get("date_received") or "")[:16]
                sender = item.get("sender_email", "")
                preview = item.get("subject", "") or (item.get("body_text") or "")[:80]
            else:
                dt = (item.get("timestamp") or "")[:16]
                sender = item.get("sender", "")
                preview = (item.get("message_text") or "")[:80]

            # Tag indicators
            tag_badges = ""
            if existing_tag:
                if existing_tag.get("exhibit_label"):
                    tag_badges += f" **[{existing_tag['exhibit_label']}]**"
                if existing_tag.get("legal_issue"):
                    tag_badges += f" `{existing_tag['legal_issue']}`"
                if existing_tag.get("flag") and existing_tag["flag"] != "none":
                    tag_badges += f" *{existing_tag['flag']}*"

            # Annotations count
            notes = db.get_annotations(item_type, item_id, selected_case_id)
            note_badge = f" ({len(notes)} notes)" if notes else ""

            col1, col2 = st.columns([0.5, 10])
            with col1:
                is_selected = st.checkbox(
                    "s", value=item_id in selected,
                    key=f"sel_{item_type}_{item_id}",
                    label_visibility="collapsed",
                )
                if is_selected and item_id not in selected:
                    selected.add(item_id)
                elif not is_selected and item_id in selected:
                    selected.discard(item_id)

            with col2:
                with st.expander(f"{dt} | {sender} | {preview[:60]}{tag_badges}{note_badge}"):
                    # Full content
                    if item_type == "email":
                        st.markdown(f"**From:** {item.get('sender_name', '')} ({sender})")
                        st.markdown(f"**Subject:** {item.get('subject', '')}")
                        st.markdown(f"**Date:** {item.get('date_received', '')}")
                        body = item.get("body_text", "")
                        if body:
                            st.text_area("Content", body[:2000], height=150,
                                         disabled=True, key=f"body_{item_type}_{item_id}",
                                         label_visibility="collapsed")
                    else:
                        st.markdown(f"**From:** {sender}")
                        st.markdown(f"**Date:** {item.get('timestamp', '')}")
                        st.markdown(f"**Chat:** {item.get('chat_name', '')}")
                        st.text(item.get("message_text", ""))

                    # Inline tagging
                    st.markdown("**Quick Tag:**")
                    qcol1, qcol2, qcol3 = st.columns(3)
                    with qcol1:
                        q_issue = st.selectbox(
                            "Issue",
                            [""] + [code for code, _ in issues_for_type],
                            format_func=lambda x: dict(issues_for_type).get(x, "—") if x else "—",
                            index=([code for code, _ in issues_for_type].index(existing_tag["legal_issue"]) + 1)
                                   if existing_tag and existing_tag.get("legal_issue") in [c for c, _ in issues_for_type]
                                   else 0,
                            key=f"qi_{item_type}_{item_id}",
                        )
                    with qcol2:
                        q_flag = st.selectbox(
                            "Flag",
                            [code for code, _ in FLAGS],
                            format_func=lambda x: dict(FLAGS).get(x, x),
                            index=[code for code, _ in FLAGS].index(existing_tag["flag"])
                                   if existing_tag and existing_tag.get("flag") in [c for c, _ in FLAGS]
                                   else 0,
                            key=f"qf_{item_type}_{item_id}",
                        )
                    with qcol3:
                        if st.button("Tag", key=f"qtag_{item_type}_{item_id}"):
                            exhibit = ""
                            if not existing_tag or not existing_tag.get("exhibit_label"):
                                exhibit = generate_exhibit_label(selected_case_id, db)
                            else:
                                exhibit = existing_tag["exhibit_label"]
                            existing_collection = existing_tag.get("collection", "") if existing_tag else ""
                            db.tag_evidence(
                                item_type, item_id, selected_case_id,
                                legal_issue=q_issue, exhibit_label=exhibit,
                                flag=q_flag, collection=existing_collection,
                            )
                            st.rerun()

                    # Inline annotation
                    st.markdown("**Notes:**")
                    for note in notes:
                        st.caption(f"[{note['created_at'][:16]}] {note['note_text']}")

                    new_note = st.text_input(
                        "Add note",
                        placeholder="e.g., Contradicts para 12 of respondent's affidavit",
                        key=f"note_{item_type}_{item_id}",
                    )
                    if st.button("Save Note", key=f"savenote_{item_type}_{item_id}") and new_note:
                        db.add_annotation(item_type, item_id, new_note, selected_case_id)
                        st.rerun()

# ── Tab 2: All Annotations ──
with tab_annotate:
    st.markdown("### All Annotations")

    note_search = st.text_input("Search notes", placeholder="Search your annotations...", key="note_search")

    if note_search:
        all_notes = db.search_annotations(note_search, selected_case_id)
    else:
        all_notes = db.get_all_annotations_for_case(selected_case_id)

    st.caption(f"{len(all_notes)} annotations")

    for note in all_notes:
        col1, col2 = st.columns([8, 1])
        with col1:
            st.markdown(
                f"**[{note['item_type']}#{note['item_id']}]** "
                f"{note['note_text']}  \n"
                f"_{note['created_at'][:16]}_"
            )
        with col2:
            if st.button("x", key=f"delnote_{note['id']}"):
                db.delete_annotation(note["id"])
                st.rerun()

# ── Tab 3: Collections ──
with tab_collections:
    st.markdown("### Evidence Collections")
    st.markdown("Named groups of evidence items for specific purposes (e.g., 'Financial Disclosure Bundle').")

    collections = db.get_all_collections(selected_case_id)

    if collections:
        for coll in collections:
            tags = db.get_evidence_tags_for_case(selected_case_id, collection=coll)
            with st.expander(f"{coll} ({len(tags)} items)"):
                for tag in tags:
                    exhibit = tag.get("exhibit_label", "")
                    issue = tag.get("legal_issue", "")
                    st.markdown(f"- **{exhibit}** [{tag['item_type']}#{tag['item_id']}] — {issue}")
    else:
        st.info("No collections yet. Assign items to collections when tagging evidence.")

# ── Tab 4: Case Settings ──
with tab_settings:
    st.markdown("### Case Settings")

    new_name = st.text_input("Case Name", value=active_case["name"], key="cs_name")
    new_number = st.text_input("Court File Number", value=active_case.get("case_number", ""), key="cs_number")
    new_desc = st.text_area("Description", value=active_case.get("description", ""), key="cs_desc")

    new_format = st.selectbox(
        "Exhibit Format",
        ["alpha", "bates", "numerical", "system"],
        index=["alpha", "bates", "numerical", "system"].index(active_case.get("exhibit_format", "alpha")),
        format_func=lambda x: {
            "alpha": "Alphabetical (A, B, C...)",
            "bates": "Bates (PREFIX_00001)",
            "numerical": "Numerical (1, 2, 3...)",
            "system": "System (Page PREFIX-1)",
        }[x],
        key="cs_format",
    )
    new_prefix = st.text_input("Exhibit Prefix", value=active_case.get("exhibit_prefix", ""), key="cs_prefix")

    if st.button("Save Settings"):
        db.update_case(
            selected_case_id,
            name=new_name, case_number=new_number, description=new_desc,
            exhibit_format=new_format, exhibit_prefix=new_prefix,
        )
        st.success("Case settings updated!")
        st.rerun()

    st.divider()

    # Case stats
    tags = db.get_evidence_tags_for_case(selected_case_id)
    notes = db.get_all_annotations_for_case(selected_case_id)
    st.markdown("### Case Statistics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tagged Items", len(tags))
    with col2:
        st.metric("Annotations", len(notes))
    with col3:
        st.metric("Collections", len(db.get_all_collections(selected_case_id)))

    # Breakdown by flag
    flag_counts = {}
    for tag in tags:
        f = tag.get("flag", "none")
        flag_counts[f] = flag_counts.get(f, 0) + 1
    if flag_counts:
        st.markdown("**By flag:**")
        for f, count in sorted(flag_counts.items()):
            label = dict(FLAGS).get(f, f)
            st.caption(f"  {label}: {count}")

    # Breakdown by legal issue
    issue_counts = {}
    for tag in tags:
        i = tag.get("legal_issue", "")
        if i:
            issue_counts[i] = issue_counts.get(i, 0) + 1
    if issue_counts:
        st.markdown("**By legal issue:**")
        all_issues = dict(LEGAL_ISSUES.get(active_case["case_type"], []))
        for i, count in sorted(issue_counts.items()):
            label = all_issues.get(i, i)
            st.caption(f"  {label}: {count}")

    st.divider()
    st.markdown("### Danger Zone")
    confirm_delete = st.checkbox(
        f"I want to delete '{active_case['name']}' and all its tags and annotations",
        key="confirm_delete_check",
    )
    if confirm_delete:
        st.warning("Evidence items (emails/chats) will NOT be deleted, only tags and annotations for this case.")
        if st.button("Delete This Case Permanently", type="primary"):
            db.delete_case(selected_case_id)
            db.log_action("case_deleted", f"Deleted case: {active_case['name']}")
            st.rerun()
