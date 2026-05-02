"""Add Entry form — Streamlit dialog with the four category forms."""

from __future__ import annotations
from typing import Optional
import streamlit as st
from casepulse.binder.models import (
    BinderCategory, CourtAppearanceMetadata, DelayAttribution, Forum,
    DisclosureMetadata, DisclosureKind,
    CounselCorrespondenceMetadata, CounselParty,
    PersonalEventMetadata,
)
from casepulse.binder.repository import (
    create_binder_entry, create_item_link,
)


_MODE_PREFIX = {
    "in_person": "",
    "virtual": "🎥 (Virtual) ",
    "telephone": "☎ (Phone) ",
    "hybrid": "🔀 (Hybrid) ",
}


def save_court_appearance(
    db, *, case_id: int, date_str: str, time_str: str,
    forum: str, court_name: str, judge: str,
    own_counsel: str, opposing_counsel: str,
    purpose: str,
    outcome: str,
    delay_attribution: Optional[dict],
    mode: str = "in_person",
    join_link: str = "",
) -> int:
    md = CourtAppearanceMetadata(
        forum=Forum(forum),
        court_name=court_name, judge=judge,
        own_counsel=own_counsel, opposing_counsel=opposing_counsel,
        purpose=purpose, mode=mode, join_link=join_link, outcome=outcome,
        delay_attribution=DelayAttribution(**delay_attribution)
            if delay_attribution else None,
    )
    prefix = _MODE_PREFIX.get(mode, "")
    title = f"{prefix}{purpose.replace('_', ' ').title()}"
    if court_name:
        title = f"{title} · {court_name}"
    return create_binder_entry(
        db, case_id=case_id, date=date_str, time=time_str,
        category=BinderCategory.COURT_APPEARANCE,
        title=title, summary=outcome, metadata=md,
    )


def render_court_form(case_id: int, default_date: str) -> dict:
    """Render the court-appearance form. Returns the field dict on submit, {} otherwise."""
    with st.form("binder_form_court", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            date_str = st.text_input("Date (YYYY-MM-DD)", value=default_date)
            time_str = st.text_input("Time (HH:MM, optional)", value="")
            forum = st.radio(
                "Forum",
                ["criminal", "family", "civil"], horizontal=True,
            )
            mode = st.radio(
                "Mode",
                ["in_person", "virtual", "telephone", "hybrid"],
                horizontal=True,
                format_func=lambda m: m.replace("_", " ").title(),
                help="In-person, Zoom/Teams (Virtual), Phone, or a mixed-mode hearing.",
            )
        with c2:
            court_name = st.text_input("Court name", value="")
            judge = st.text_input("Judge", value="")
            own_counsel = st.text_input("Own counsel", value="")
            opposing_counsel = st.text_input("Opposing counsel", value="")
        purpose = st.selectbox(
            "Purpose",
            ["first_appearance", "set_date", "trial", "motion",
             "case_conference", "settlement_conference", "sentencing", "other"],
        )
        join_link = ""
        if mode in ("virtual", "telephone", "hybrid"):
            join_link = st.text_input(
                "Join link / dial-in",
                value="",
                placeholder="https://zoom.us/j/... or 1-855-... or CaseLines URL",
                help="Saved with the entry. Click in the Open dialog later to copy.",
            )
        outcome = st.text_area("Outcome / notes", value="")

        delay_attribution = None
        with st.expander("Optional: log delay attribution (criminal only)"):
            attr_cat = st.selectbox(
                "Attribution category",
                ["", "defence", "crown", "inherent", "exceptional"],
            )
            attr_days = st.number_input("Days", min_value=0, value=0, step=1)
            attr_note = st.text_input("Attribution note", value="")
            if attr_cat:
                delay_attribution = {
                    "category": attr_cat, "days": int(attr_days), "note": attr_note,
                }

        submitted = st.form_submit_button("Save court appearance", type="primary")
        if submitted:
            return {
                "date_str": date_str, "time_str": time_str,
                "forum": forum, "court_name": court_name, "judge": judge,
                "own_counsel": own_counsel, "opposing_counsel": opposing_counsel,
                "purpose": purpose, "mode": mode, "join_link": join_link,
                "outcome": outcome,
                "delay_attribution": delay_attribution,
            }
    return {}


def save_disclosure(
    db, *, case_id: int, date_str: str, time_str: str,
    kind: str, direction: str, page_count: int, items: str,
    completion_status: str,
    expected_completion_date: Optional[str],
    follow_up_email_id: Optional[int],
) -> int:
    md = DisclosureMetadata(
        kind=DisclosureKind(kind), direction=direction,
        page_count=page_count, items=items,
        completion_status=completion_status,
        expected_completion_date=expected_completion_date,
        follow_up_email_id=follow_up_email_id,
        outstanding_flag=False,
    )
    title = f"Disclosure · {direction}"
    if kind != "other":
        title = f"{kind.title()} {title}"
    return create_binder_entry(
        db, case_id=case_id, date=date_str, time=time_str,
        category=BinderCategory.DISCLOSURE,
        title=title, summary=items, metadata=md,
    )


def render_disclosure_form(case_id: int, default_date: str) -> dict:
    with st.form("binder_form_disclosure", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            date_str = st.text_input("Date (YYYY-MM-DD)", value=default_date)
            time_str = st.text_input("Time (HH:MM, optional)", value="")
            kind = st.radio(
                "Kind",
                ["crown", "financial", "discovery", "other"], horizontal=True,
            )
            direction = st.radio(
                "Direction", ["received", "requested"], horizontal=True,
            )
        with c2:
            page_count = st.number_input("Page count", min_value=0, value=0, step=1)
            completion_status = st.radio(
                "Completion status", ["complete", "expecting_more"],
                horizontal=True,
            )
            expected_date = ""
            if completion_status == "expecting_more":
                expected_date = st.text_input(
                    "Expected completion date (YYYY-MM-DD)", value="",
                )
        items = st.text_area("Items / contents", value="")
        submitted = st.form_submit_button("Save disclosure entry", type="primary")
        if submitted:
            return {
                "date_str": date_str, "time_str": time_str,
                "kind": kind, "direction": direction,
                "page_count": int(page_count), "items": items,
                "completion_status": completion_status,
                "expected_completion_date": expected_date or None,
                "follow_up_email_id": None,
            }
    return {}


def save_counsel_correspondence(
    db, *, case_id: int, date_str: str, time_str: str,
    party: str, linked_email_id: Optional[int],
    summary: str, response_required: bool,
    response_due_date: Optional[str],
) -> int:
    md = CounselCorrespondenceMetadata(
        party=CounselParty(party),
        linked_email_id=linked_email_id,
        summary=summary,
        response_required=response_required,
        response_due_date=response_due_date,
        response_sent_email_id=None,
    )
    title = f"{party.replace('_', ' ').title()} correspondence"
    entry_id = create_binder_entry(
        db, case_id=case_id, date=date_str, time=time_str,
        category=BinderCategory.COUNSEL_CORRESPONDENCE,
        title=title, summary=summary, metadata=md,
    )
    if linked_email_id is not None:
        with db._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO evidence_tags
                    (item_type, item_id, case_id, legal_issue)
                   VALUES ('email', ?, ?, 'counsel_correspondence')""",
                (linked_email_id, case_id),
            )
    return entry_id


def render_counsel_form(case_id: int, default_date: str) -> dict:
    with st.form("binder_form_counsel", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            date_str = st.text_input("Date (YYYY-MM-DD)", value=default_date)
            time_str = st.text_input("Time (HH:MM, optional)", value="")
            party = st.radio(
                "Party",
                ["crown", "opposing_counsel", "own_counsel", "OCL", "other"],
                horizontal=True,
            )
        with c2:
            linked_email_id = st.number_input(
                "Linked email id (optional)", min_value=0, value=0, step=1,
            )
            response_required = st.checkbox("Response required")
            response_due_date = ""
            if response_required:
                response_due_date = st.text_input(
                    "Response due date (YYYY-MM-DD)", value="",
                )
        summary = st.text_area("Summary", value="")
        submitted = st.form_submit_button("Save counsel correspondence", type="primary")
        if submitted:
            return {
                "date_str": date_str, "time_str": time_str,
                "party": party,
                "linked_email_id": int(linked_email_id) if linked_email_id else None,
                "summary": summary,
                "response_required": response_required,
                "response_due_date": response_due_date or None,
            }
    return {}


def save_personal_event(
    db, *, case_id: int, date_str: str, time_str: str,
    time_end: str, location: str, evidence_relevance: str,
    witness_ids: list[int], photo_metadata_ids: list[int],
    document_ids: list[int], attachment_ids: list[int],
    email_ids: list[int],
) -> int:
    md = PersonalEventMetadata(
        time_end=time_end or None,
        location=location,
        evidence_relevance=evidence_relevance,
    )
    title = location or "Personal event"
    entry_id = create_binder_entry(
        db, case_id=case_id, date=date_str, time=time_str,
        category=BinderCategory.PERSONAL_EVENT,
        title=title, summary="", metadata=md,
    )
    pairs: list[tuple[str, int]] = []
    pairs += [("witness", w) for w in witness_ids]
    pairs += [("photo", p) for p in photo_metadata_ids]
    pairs += [("document", d) for d in document_ids]
    pairs += [("attachment", a) for a in attachment_ids]
    pairs += [("email", e) for e in email_ids]
    for ftype, fid in pairs:
        create_item_link(
            db, case_id=case_id,
            from_type=ftype, from_id=fid,
            to_type="timeline_event", to_id=entry_id,
            relationship="part_of",
        )
    return entry_id


def render_personal_event_form(db, case_id: int, default_date: str) -> dict:
    """Render the personal-event form with multi-selects pulled from DB."""
    with db._get_conn() as conn:
        wrows = conn.execute(
            "SELECT id, name FROM witnesses WHERE case_id=?", (case_id,),
        ).fetchall()
        drows = conn.execute(
            """SELECT d.id, d.filename FROM documents d
               JOIN evidence_tags t ON t.item_type='document' AND t.item_id=d.id
               WHERE t.case_id=?""", (case_id,)).fetchall()
    witness_opts = {f"{r['name']} (#{r['id']})": r["id"] for r in wrows}
    doc_opts = {f"{r['filename']} (#{r['id']})": r["id"] for r in drows}

    with st.form("binder_form_personal", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            date_str = st.text_input("Date (YYYY-MM-DD)", value=default_date)
            time_str = st.text_input("Start time (HH:MM)", value="")
            time_end = st.text_input("End time (HH:MM)", value="")
        with c2:
            location = st.text_input("Location", value="")
            evidence_relevance = st.selectbox(
                "Evidence relevance",
                ["context", "alibi", "corroboration", "contradiction"],
            )
        witnesses_pick = st.multiselect("Witnesses", list(witness_opts.keys()))
        documents_pick = st.multiselect("Documents", list(doc_opts.keys()))
        st.caption(
            "Photos / attachments / emails — link via '+ Link' on the day drawer "
            "after creating the event (Phase B)."
        )
        submitted = st.form_submit_button("Save personal event", type="primary")
        if submitted:
            return {
                "date_str": date_str, "time_str": time_str,
                "time_end": time_end, "location": location,
                "evidence_relevance": evidence_relevance,
                "witness_ids": [witness_opts[w] for w in witnesses_pick],
                "photo_metadata_ids": [],
                "document_ids": [doc_opts[d] for d in documents_pick],
                "attachment_ids": [], "email_ids": [],
            }
    return {}


@st.dialog("Add Binder Entry")
def open_add_entry_dialog(db, *, case_id: int, default_date: str) -> None:
    """Top-level Add Entry dialog. Renders a category radio + the matching
    sub-form. On submit, dispatches to the correct save_* handler."""
    cat = st.radio(
        "Category",
        ["court_appearance", "disclosure", "counsel_correspondence", "personal_event"],
        format_func=lambda c: c.replace("_", " ").title(),
        horizontal=True,
    )
    if cat == "court_appearance":
        fields = render_court_form(case_id, default_date)
        if fields:
            save_court_appearance(db, case_id=case_id, **fields)
            st.success("Court appearance saved.")
            st.rerun()
    elif cat == "disclosure":
        fields = render_disclosure_form(case_id, default_date)
        if fields:
            save_disclosure(db, case_id=case_id, **fields)
            st.success("Disclosure entry saved.")
            st.rerun()
    elif cat == "counsel_correspondence":
        fields = render_counsel_form(case_id, default_date)
        if fields:
            save_counsel_correspondence(db, case_id=case_id, **fields)
            st.success("Counsel correspondence saved.")
            st.rerun()
    elif cat == "personal_event":
        fields = render_personal_event_form(db, case_id, default_date)
        if fields:
            save_personal_event(db, case_id=case_id, **fields)
            st.success("Personal event saved.")
            st.rerun()
