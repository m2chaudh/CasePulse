"""Timeline page — Chronological view of all collected emails."""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Timeline", page_icon="CP", layout="wide")

st.markdown("## Timeline")
st.markdown("Chronological view of all emails and chat messages.")


from components.page_init import init_page
db, config = init_page()

stats = db.get_stats()
if stats["total_emails"] == 0 and stats.get("total_chat_messages", 0) == 0:
    st.info("No data collected yet. Go to **Fetch Emails** or **Import Chats** first.")
    st.stop()

# ── Filters ──
st.markdown("### Filters")

col1, col2, col3 = st.columns(3)
with col1:
    filter_start = st.date_input(
        "From",
        value=date.fromisoformat(config.date_start),
        key="tl_start",
    )
with col2:
    filter_end = st.date_input(
        "To",
        value=date.fromisoformat(config.date_end),
        key="tl_end",
    )
with col3:
    filter_keyword = st.text_input("Search", placeholder="Search emails...", key="tl_search")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    selected_senders = db.get_senders(selected_only=True)
    sender_options = ["All senders"] + [s["email"] for s in selected_senders]
    filter_sender = st.selectbox("Sender", sender_options, key="tl_sender")
with col2:
    all_accounts = db.get_accounts()
    account_options = ["All accounts"] + [a["email"] for a in all_accounts]
    filter_account = st.selectbox("Mailbox", account_options, key="tl_account")
with col3:
    filter_direction = st.selectbox("Direction", ["All", "received", "sent"], key="tl_dir")
with col4:
    filter_attachments = st.selectbox("Attachments", ["All", "With attachments", "Without attachments"], key="tl_att")
with col5:
    filter_source = st.selectbox("Source", ["All", "Emails only", "Chats only"], key="tl_source")

# ── Fetch data ──
sender_email = None if filter_sender == "All senders" else filter_sender
direction = None if filter_direction == "All" else filter_direction
has_att = None
if filter_attachments == "With attachments":
    has_att = True
elif filter_attachments == "Without attachments":
    has_att = False

# Use unified timeline
if filter_source == "All":
    timeline_items = db.get_unified_timeline(
        date_start=str(filter_start),
        date_end=str(filter_end),
        keyword=filter_keyword if filter_keyword else None,
        sender=sender_email,
        limit=5000,
    )
elif filter_source == "Emails only":
    emails_raw = db.get_emails(
        sender_email=sender_email,
        date_start=str(filter_start),
        date_end=str(filter_end),
        keyword=filter_keyword if filter_keyword else None,
        direction=direction,
        has_attachments=has_att,
        limit=5000,
    )
    timeline_items = [{
        "type": "email", "timestamp": e.get("date_received", ""),
        "sender": e.get("sender_email", ""), "sender_name": e.get("sender_name", ""),
        "subject": e.get("subject", ""), "body_preview": (e.get("body_text", "") or "")[:300],
        "direction": e.get("direction", ""), "is_forwarded": bool(e.get("is_forwarded")),
        "has_attachments": bool(e.get("has_attachments")), "source_id": e["id"],
        "platform": "email",
    } for e in emails_raw]
else:
    chat_raw = db.get_chat_messages(
        date_start=str(filter_start),
        date_end=str(filter_end),
        keyword=filter_keyword if filter_keyword else None,
        sender=sender_email,
        limit=5000,
    )
    timeline_items = [{
        "type": "chat", "timestamp": m.get("timestamp", ""),
        "sender": m.get("sender", ""), "sender_name": m.get("sender", ""),
        "subject": m.get("chat_name", ""), "body_preview": (m.get("message_text", "") or "")[:300],
        "direction": "", "is_forwarded": False,
        "has_attachments": bool(m.get("has_media")), "source_id": m["id"],
        "platform": m.get("platform", "chat"),
    } for m in chat_raw]

# Also keep emails reference for attachment lookups below
emails = db.get_emails(
    sender_email=sender_email,
    date_start=str(filter_start),
    date_end=str(filter_end),
    keyword=filter_keyword if filter_keyword else None,
    direction=direction,
    has_attachments=has_att,
    limit=5000,
)

# Apply account filter
if filter_account != "All accounts":
    timeline_items = [t for t in timeline_items if t.get("account") == filter_account or t["type"] == "chat"]

email_count = sum(1 for t in timeline_items if t["type"] == "email")
chat_count = sum(1 for t in timeline_items if t["type"] == "chat")
st.markdown(f"**{len(timeline_items)} items** in timeline ({email_count} emails, {chat_count} chat messages)")

st.divider()

# ── Visual Timeline Chart ──
if timeline_items and len(timeline_items) > 1:
    try:
        import plotly.express as px
        import pandas as pd

        # Build timeline data
        timeline_data = []
        for item in timeline_items:
            dt = item.get("timestamp", "")
            if not dt:
                continue
            try:
                if "T" in dt:
                    parsed_date = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                else:
                    parsed_date = datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                continue

            sender = item.get("sender", "unknown")
            item_type = item.get("type", "email")
            label = item.get("subject", "") or item.get("body_preview", "")[:60]
            timeline_data.append({
                "date": parsed_date,
                "sender": sender,
                "label": (label[:60] + "...") if len(label) > 60 else label,
                "type": item_type,
                "platform": item.get("platform", ""),
            })

        if timeline_data:
            df = pd.DataFrame(timeline_data)

            fig = px.scatter(
                df,
                x="date",
                y="sender",
                color="type",
                hover_data=["label", "platform"],
                title="Communication Timeline",
                color_discrete_map={
                    "email": "#00d4ff",
                    "chat": "#ff9f43",
                },
            )
            fig.update_layout(
                height=max(300, len(df["sender"].unique()) * 30 + 100),
                xaxis_title="Date",
                yaxis_title="",
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

    except ImportError:
        st.caption("Install plotly for visual timeline: pip install plotly")
    except Exception as e:
        st.caption(f"Could not render chart: {e}")

st.divider()

# ── Email List ──
st.markdown("### Emails")

# Build account lookup for display
account_lookup = {a["id"]: a["email"] for a in db.get_accounts()}

for email in emails:
    dt = email.get("date_received", "")[:19] if email.get("date_received") else "Unknown date"
    sender = email.get("sender_email", "Unknown")
    sender_name = email.get("sender_name", "")
    subject = email.get("subject", "(no subject)")
    direction = email.get("direction", "")
    is_fwd = email.get("is_forwarded")
    source_account = account_lookup.get(email.get("account_id"), "")

    # Direction indicator
    dir_icon = "<-" if direction == "received" else "->" if direction == "sent" else "  "
    fwd_tag = " [FWD]" if is_fwd else ""
    account_tag = f" [{source_account}]" if source_account else ""

    display_sender = f"{sender_name} ({sender})" if sender_name else sender

    with st.expander(f"{dt} | {dir_icon} {display_sender} | {subject}{fwd_tag}{account_tag}"):
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**From:** {display_sender}")

            # Recipients
            recipients = email.get("recipients", "")
            if recipients:
                if isinstance(recipients, str):
                    try:
                        recipients = json.loads(recipients)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if isinstance(recipients, list):
                    recip_str = ", ".join(
                        r.get("email", str(r)) if isinstance(r, dict) else str(r)
                        for r in recipients
                    )
                    st.markdown(f"**To:** {recip_str}")

            st.markdown(f"**Date:** {dt}")
            st.markdown(f"**Subject:** {subject}")

            if is_fwd:
                orig_sender = email.get("original_sender", "")
                orig_date = email.get("original_date", "")
                if orig_sender:
                    st.markdown(f"**Originally from:** {orig_sender}")
                if orig_date:
                    st.markdown(f"**Original date:** {orig_date}")

        with col2:
            st.markdown(f"**Direction:** {direction}")
            if source_account:
                st.markdown(f"**Mailbox:** {source_account}")
            st.markdown(f"**Attachments:** {'Yes' if email.get('has_attachments') else 'No'}")

        # Body
        body = email.get("body_text", "")
        if body:
            st.markdown("---")
            st.text_area("Email body", value=body, height=200, key=f"body_{email['id']}",
                         disabled=True, label_visibility="collapsed")

        # Attachments
        if email.get("has_attachments"):
            attachments = db.get_attachments_for_email(email["id"])
            if attachments:
                st.markdown("**Attachments:**")
                for att in attachments:
                    dup_tag = " (duplicate)" if att.get("is_duplicate") else ""
                    from casepulse.attachments.extractor import get_file_size_human
                    size = get_file_size_human(att.get("size_bytes", 0))
                    st.markdown(f"- {att['filename']} ({size}){dup_tag}")

                    if att.get("extracted_text"):
                        with st.expander(f"Extracted text from {att['filename']}"):
                            st.text(att["extracted_text"][:2000])

# ── Export ──
st.divider()
st.markdown("### Export")

# Build export data upfront so download buttons work on first click
md_lines = ["# CasePulse Timeline\n"]
md_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
md_lines.append(f"Date range: {filter_start} to {filter_end}\n")
md_lines.append(f"Total items: {len(emails)}\n")
md_lines.append("---\n")

current_date = ""
for email in emails:
    dt = email.get("date_received", "")[:10]
    if dt != current_date:
        current_date = dt
        md_lines.append(f"\n## {current_date}\n")

    time_str = email.get("date_received", "")[11:16] if email.get("date_received") else ""
    sender = email.get("sender_email", "")
    subject = email.get("subject", "(no subject)")
    direction = email.get("direction", "")
    fwd = " [FORWARDED]" if email.get("is_forwarded") else ""

    md_lines.append(f"### {time_str} — {sender} ({direction}){fwd}")
    md_lines.append(f"**Subject:** {subject}\n")

    body = email.get("body_text", "")
    if body:
        preview = body[:500].replace("\n", "\n> ")
        md_lines.append(f"> {preview}\n")

    attachments = db.get_attachments_for_email(email["id"])
    if attachments:
        md_lines.append("**Attachments:**")
        for att in attachments:
            md_lines.append(f"- {att['filename']}")
        md_lines.append("")

md_content = "\n".join(md_lines)

export_data = []
for email in emails:
    entry = {
        "id": email["id"],
        "date": email.get("date_received", ""),
        "sender": email.get("sender_email", ""),
        "sender_name": email.get("sender_name", ""),
        "recipients": email.get("recipients", ""),
        "subject": email.get("subject", ""),
        "body": email.get("body_text", ""),
        "direction": email.get("direction", ""),
        "is_forwarded": bool(email.get("is_forwarded")),
        "original_sender": email.get("original_sender", ""),
        "attachments": [],
    }
    attachments = db.get_attachments_for_email(email["id"])
    for att in attachments:
        entry["attachments"].append({
            "filename": att["filename"],
            "content_type": att.get("content_type", ""),
            "size_bytes": att.get("size_bytes", 0),
            "extracted_text": att.get("extracted_text", ""),
            "is_duplicate": bool(att.get("is_duplicate")),
        })
    export_data.append(entry)

json_content = json.dumps(export_data, indent=2, default=str)

col1, col2 = st.columns(2)
with col1:
    st.download_button(
        "Download Timeline (Markdown)",
        data=md_content,
        file_name=f"casepulse_timeline_{filter_start}_{filter_end}.md",
        mime="text/markdown",
    )
with col2:
    st.download_button(
        "Download Timeline (JSON)",
        data=json_content,
        file_name=f"casepulse_emails_{filter_start}_{filter_end}.json",
        mime="application/json",
    )
