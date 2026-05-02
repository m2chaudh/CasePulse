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


def save_court_appearance(
    db, *, case_id: int, date_str: str, time_str: str,
    forum: str, court_name: str, judge: str,
    own_counsel: str, opposing_counsel: str,
    purpose: str, outcome: str,
    delay_attribution: Optional[dict],
) -> int:
    md = CourtAppearanceMetadata(
        forum=Forum(forum),
        court_name=court_name, judge=judge,
        own_counsel=own_counsel, opposing_counsel=opposing_counsel,
        purpose=purpose, outcome=outcome,
        delay_attribution=DelayAttribution(**delay_attribution)
            if delay_attribution else None,
    )
    title = f"{purpose.replace('_', ' ').title()}"
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
                "purpose": purpose, "outcome": outcome,
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
