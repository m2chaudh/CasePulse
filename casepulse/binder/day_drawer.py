"""Day drawer — chronological strip with inline actions."""

from __future__ import annotations
from datetime import date
import streamlit as st
from casepulse.binder.models import AggregatedItem, CrossRef
from casepulse.binder.aggregator import aggregate
from casepulse.binder.calendar_component import (
    _emoji_for, _COLORS, item_color_key,
)


def format_time_label(item: AggregatedItem) -> str:
    if item.when.hour == 0 and item.when.minute == 0:
        return "—"
    return item.when.strftime("%H:%M")


def source_badge(item: AggregatedItem) -> str:
    color = _COLORS.get(item_color_key(item), "#475569")
    emoji = _emoji_for(item)
    return f"<span style='background:{color};color:white;padding:2px 6px;border-radius:3px;font-size:0.78em'>{emoji}</span>"


def format_cross_ref(cr: CrossRef) -> str:
    label = cr.label or f"{cr.target_type} #{cr.target_id}"
    if cr.target_type == "argument":
        return f"✓ In {label} · {cr.relationship}"
    return f"↪ {cr.relationship.replace('_', ' ')} {label}"


def render_day_drawer(db, *, case_id: int, day: date, chip_filter=None) -> None:
    """Render the chronological day drawer for one date."""
    items = aggregate(db, case_id=case_id,
                      date_start=day, date_end=day, chip_filter=chip_filter)

    # Tiny status line — exactly what the drawer is rendering. Useful for
    # spotting state mismatches between calendar and drawer.
    chip_label = (chip_filter.chip_id if chip_filter is not None else "all")
    st.caption(
        f"Drawer showing **{day.isoformat()}** · filter **{chip_label}** · "
        f"{len(items)} items"
    )

    cols = st.columns([1, 4, 1])
    with cols[0]:
        if st.button("‹ Prev", key="binder_day_prev"):
            from datetime import timedelta
            st.session_state["binder_selected_date"] = (day - timedelta(days=1)).isoformat()
    with cols[1]:
        st.markdown(f"### 📅 {day.strftime('%a, %B %d, %Y')}")
    with cols[2]:
        if st.button("Next ›", key="binder_day_next"):
            from datetime import timedelta
            st.session_state["binder_selected_date"] = (day + timedelta(days=1)).isoformat()

    a1, a2 = st.columns(2)
    with a1:
        if st.button("+ Add Entry", key="binder_day_add", type="primary"):
            st.session_state["binder_open_add_entry"] = True
            st.session_state["binder_add_entry_date"] = day.isoformat()
    with a2:
        if st.button("+ Attach to this day", key="binder_day_attach"):
            st.session_state["binder_open_attach"] = True
            st.session_state["binder_attach_date"] = day.isoformat()

    if not items:
        st.caption("No entries on this day.")
        return

    st.caption("Chronological · earliest first")

    # Walk items chronologically, but collapse runs of consecutive chats
    # from the same conversation into a single bubble cluster (one inline
    # view per day per conversation) instead of one row + open-dialog per
    # message.
    i = 0
    while i < len(items):
        it = items[i]
        if it.source == "chat":
            # Find the run length: consecutive chats with same platform+chat_name
            j = i
            key = (it.metadata.get("platform", ""), it.metadata.get("chat_name", ""))
            while (j < len(items)
                    and items[j].source == "chat"
                    and (items[j].metadata.get("platform", ""),
                         items[j].metadata.get("chat_name", "")) == key):
                j += 1
            _render_chat_cluster(items[i:j], db)
            i = j
            continue

        # Non-chat: existing single-row pattern
        c1, c2 = st.columns([1, 9])
        with c1:
            st.markdown(f"<div style='opacity:0.6'>{format_time_label(it)}</div>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown(
                f"{source_badge(it)} **{it.title}**",
                unsafe_allow_html=True,
            )
            if it.summary:
                st.caption(it.summary)
            for cr in it.cross_refs:
                st.markdown(f"<small>{format_cross_ref(cr)}</small>",
                            unsafe_allow_html=True)
            _render_inline_actions(it)
        st.divider()
        i += 1


# --- Chat bubble cluster --------------------------------------------------

# Senders that are "self" — render right-aligned with a teal/mint bubble.
# Heuristic: the user's own name typically appears as one of these.
_SELF_SENDERS = {"You", "Mani", "Manish", "Manish Chaudhary"}

# Colour palette for non-self senders — first-seen gets the first colour,
# second-seen gets the second, etc. Keeps multi-party AppClose threads
# distinguishable.
_SENDER_COLOURS = [
    "#6e87f4",  # blue (Manisha in mockups)
    "#d9774e",  # orange
    "#10a37f",  # green
    "#a855f7",  # purple
    "#ef4444",  # red
]


def _is_self(sender: str) -> bool:
    return sender in _SELF_SENDERS


def _sender_colour(sender: str, palette: dict[str, str]) -> str:
    if sender not in palette:
        palette[sender] = _SENDER_COLOURS[len(palette) % len(_SENDER_COLOURS)]
    return palette[sender]


def _render_chat_cluster(cluster: list[AggregatedItem], db) -> None:
    """Render a run of chats from the same conversation as a WhatsApp/
    AppClose-style bubble cluster — one bubble per message, sender-coloured
    name, time inline. Replaces N pop-out rows with one continuous view."""
    first = cluster[0]
    platform = first.metadata.get("platform", "chat")
    chat_name = first.metadata.get("chat_name", "")

    # Look up ChatVault deep-link anchors for the cluster's chat_message ids
    from casepulse.chatvault_integration import (
        get_anchors_for_messages, url_for,
    )
    _msg_ids = [it.source_id for it in cluster if it.source == "chat"]
    _anchors = get_anchors_for_messages(db, _msg_ids) if _msg_ids else {}
    _first_anchor = next(
        (_anchors[m] for m in _msg_ids if m in _anchors), None
    )

    # Header for the cluster
    header = f"💬 {platform}"
    if chat_name:
        header += f" / {chat_name}"
    header += f"  ·  {len(cluster)} message(s)"
    if _first_anchor:
        if _first_anchor.get("broken"):
            header += (
                "  ·  <span style='color:#dc2626' "
                "title='ChatVault source folder is unreachable. "
                "Repair on Setup → ChatVault Exports.'>"
                "⚠ ChatVault unreachable</span>"
            )
        else:
            cv_url = url_for(
                _first_anchor["export_name"], _first_anchor["anchor_id"]
            )
            header += (
                f"  ·  <a href='{cv_url}' target='_blank' "
                f"style='color:#268bd2; text-decoration:none'>"
                f"View in ChatVault →</a>"
            )

    # WhatsApp-style for whatsapp, white-background AppClose-style otherwise
    is_whatsapp = "whatsapp" in platform.lower()
    bg = "#efeae2" if is_whatsapp else "#ffffff"
    self_bubble_bg = "#d9fdd3" if is_whatsapp else "#dbeafe"
    other_bubble_bg = "#ffffff" if is_whatsapp else "#f3f4f6"
    border_other = "" if is_whatsapp else "border: 1px solid #e5e7eb;"
    border_self = "" if is_whatsapp else "border: 1px solid #bfdbfe;"
    self_label_colour = "#00a884" if is_whatsapp else "#1f4e79"

    palette: dict[str, str] = {}

    parts: list[str] = []
    parts.append(
        f"<div style='background:{bg}; padding:14px; border-radius:8px; "
        f"margin: 6px 0;'>"
    )
    parts.append(
        f"<div style='font-size:0.78em; opacity:0.6; margin-bottom:8px'>"
        f"{header}</div>"
    )

    for it in cluster:
        sender = it.metadata.get("sender", "?") or "?"
        is_me = _is_self(sender)
        align = "flex-end" if is_me else "flex-start"
        bubble_bg = self_bubble_bg if is_me else other_bubble_bg
        border = border_self if is_me else border_other
        radius = ("8px 8px 0 8px" if is_me else "8px 8px 8px 0")
        sender_colour = (self_label_colour if is_me
                          else _sender_colour(sender, palette))
        sender_label = "You" if is_me else sender
        time_label = it.when.strftime("%I:%M %p").lstrip("0")
        body = (it.summary or "").replace("<", "&lt;").replace(">", "&gt;")
        body = body.replace("\n", "<br>")

        media_hint = ""
        if it.metadata.get("has_media"):
            mt = it.metadata.get("media_type", "media")
            media_hint = (
                f"<div style='font-size:0.78em; opacity:0.6; "
                f"margin-top:4px'>📎 {mt}</div>"
            )

        # Per-bubble ChatVault deep-link arrow, when this msg has an anchor
        anchor_link = ""
        if it.source == "chat" and it.source_id in _anchors:
            a = _anchors[it.source_id]
            if a.get("broken"):
                anchor_link = (
                    " <span style='color:#dc2626' "
                    "title='ChatVault source unreachable'>⚠</span>"
                )
            else:
                anchor_url = url_for(a["export_name"], a["anchor_id"])
                anchor_link = (
                    f" <a href='{anchor_url}' target='_blank' "
                    f"style='color:#268bd2; text-decoration:none' "
                    f"title='Open in ChatVault'>↗</a>"
                )

        parts.append(
            f"<div style='display:flex; justify-content:{align}; margin: 3px 0;'>"
            f"<div style='max-width:75%; padding:6px 10px 4px; "
            f"background:{bubble_bg}; border-radius:{radius}; {border}'>"
            f"<div style='font-size:12.5px; font-weight:600; "
            f"color:{sender_colour}; margin-bottom:2px'>{sender_label}</div>"
            f"<div style='white-space:pre-wrap; font-size:14px; "
            f"line-height:1.4; color:#111827'>{body}</div>"
            f"{media_hint}"
            f"<div style='font-size:11px; color:#667781; text-align:right; "
            f"margin-top:2px'>{time_label}{anchor_link}</div>"
            f"</div>"
            f"</div>"
        )

    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
    st.divider()


def _render_inline_actions(it: AggregatedItem) -> None:
    # Phase A: Open / Edit only. The "+ Link" inline action ships with the
    # Link picker dialog in Phase B.
    cols = st.columns([1, 1, 6])
    with cols[0]:
        if st.button("Open", key=f"binder_open_{it.source}_{it.source_id}"):
            st.session_state["binder_open_dialog_source"] = it.source
            st.session_state["binder_open_dialog_id"] = it.source_id
            st.rerun()
    with cols[1]:
        # Edit currently meaningful only for timeline_event entries (binder
        # entries we created); imported items are read-only — but the Open
        # dialog for a timeline_event also offers Delete.
        if it.source == "timeline_event":
            if st.button("Edit", key=f"binder_edit_{it.source}_{it.source_id}"):
                st.session_state["binder_open_dialog_source"] = it.source
                st.session_state["binder_open_dialog_id"] = it.source_id
                st.rerun()
        else:
            st.button(
                "Edit",
                key=f"binder_edit_{it.source}_{it.source_id}",
                disabled=True,
                help="Imported items aren't editable. Tag/annotate from the "
                     "Cases page or create a binder entry that links to this item.",
            )
