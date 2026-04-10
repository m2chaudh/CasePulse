"""Timeline — Central command center for browsing, analyzing, and acting on evidence."""
import streamlit as st
import sys
import json
import sqlite3
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Timeline", page_icon="CP", layout="wide")

st.markdown("## Timeline")

from components.page_init import init_page
db, config = init_page()

stats = db.get_stats()
if stats["total_emails"] == 0 and stats.get("total_chat_messages", 0) == 0:
    st.info("No data collected yet. Go to **Fetch Emails** or **Import Chats** first.")
    st.stop()

# ══════════════════════════════════════════════════════
# FILTERS
# ══════════════════════════════════════════════════════
with st.container():
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_start = st.date_input("From", value=date.fromisoformat(config.date_start), key="tl_start")
    with col2:
        filter_end = st.date_input("To", value=date.fromisoformat(config.date_end), key="tl_end")
    with col3:
        filter_keyword = st.text_input("Search", placeholder="Search subject/content...", key="tl_search")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        selected_senders = db.get_senders(selected_only=True)
        sender_options = ["All senders"] + [s["email"] for s in selected_senders]
        filter_sender = st.selectbox("Sender", sender_options, key="tl_sender")
    with col2:
        all_accounts = db.get_accounts()
        account_options = ["All mailboxes"] + [a["email"] for a in all_accounts]
        filter_account = st.selectbox("Mailbox", account_options, key="tl_account")
    with col3:
        filter_direction = st.selectbox("Direction", ["All", "received", "sent"], key="tl_dir")
    with col4:
        filter_attachments = st.selectbox("Attachments", ["All", "With", "Without"], key="tl_att")
    with col5:
        filter_source = st.selectbox("Source", ["All", "Emails", "Chats"], key="tl_source")

# ══════════════════════════════════════════════════════
# FETCH DATA
# ══════════════════════════════════════════════════════
sender_email = None if filter_sender == "All senders" else filter_sender
direction = None if filter_direction == "All" else filter_direction
has_att = None
if filter_attachments == "With":
    has_att = True
elif filter_attachments == "Without":
    has_att = False

# Get emails
emails_raw = []
if filter_source != "Chats":
    emails_raw = db.get_emails(
        sender_email=sender_email,
        date_start=str(filter_start),
        date_end=str(filter_end),
        keyword=filter_keyword if filter_keyword else None,
        direction=direction,
        has_attachments=has_att,
        limit=10000,
    )

# Get chats
chats_raw = []
if filter_source != "Emails":
    chats_raw = db.get_chat_messages(
        date_start=str(filter_start),
        date_end=str(filter_end),
        keyword=filter_keyword if filter_keyword else None,
        sender=sender_email,
        limit=10000,
    )

# Account filter
account_lookup = {a["id"]: a["email"] for a in all_accounts}
if filter_account != "All mailboxes":
    acc_id = next((a["id"] for a in all_accounts if a["email"] == filter_account), None)
    if acc_id:
        emails_raw = [e for e in emails_raw if e.get("account_id") == acc_id]

# Build unified items
items = []
for e in emails_raw:
    items.append({
        "type": "email", "id": e["id"],
        "timestamp": e.get("date_received", ""),
        "sender": e.get("sender_email", ""),
        "sender_name": e.get("sender_name", ""),
        "subject": e.get("subject", ""),
        "direction": e.get("direction", ""),
        "is_forwarded": bool(e.get("is_forwarded")),
        "has_attachments": bool(e.get("has_attachments")),
        "account": account_lookup.get(e.get("account_id"), ""),
    })
for m in chats_raw:
    items.append({
        "type": "chat", "id": m["id"],
        "timestamp": m.get("timestamp", ""),
        "sender": m.get("sender", ""),
        "sender_name": m.get("sender", ""),
        "subject": m.get("chat_name", ""),
        "direction": "",
        "is_forwarded": False,
        "has_attachments": bool(m.get("has_media")),
        "account": m.get("platform", "chat"),
    })

items.sort(key=lambda x: x["timestamp"] or "")

# ── Thread grouping — link emails in the same RE: chain ──
from casepulse.storage.database import Database as _ThreadDB
thread_map = {}  # normalized subject → list of item indices
for idx, item in enumerate(items):
    if item["type"] == "email":
        subj = _ThreadDB.normalize_subject(item.get("subject", ""))
        if subj:
            if subj not in thread_map:
                thread_map[subj] = []
            thread_map[subj].append(idx)

# Mark items with their thread info
for subj, indices in thread_map.items():
    if len(indices) > 1:
        for i, idx in enumerate(indices):
            items[idx]["thread_id"] = subj
            items[idx]["thread_count"] = len(indices)
            items[idx]["thread_pos"] = i + 1  # 1 of 5, 2 of 5, etc.

# ══════════════════════════════════════════════════════
# STATS BAR
# ══════════════════════════════════════════════════════
email_count = sum(1 for i in items if i["type"] == "email")
chat_count = sum(1 for i in items if i["type"] == "chat")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Items", f"{len(items):,}")
with col2:
    st.metric("Emails", f"{email_count:,}")
with col3:
    st.metric("Chat Messages", f"{chat_count:,}")
with col4:
    if items:
        first_date = items[0]["timestamp"][:10] if items[0]["timestamp"] else "?"
        last_date = items[-1]["timestamp"][:10] if items[-1]["timestamp"] else "?"
        st.metric("Range", f"{first_date} to {last_date}")

# ══════════════════════════════════════════════════════
# VISUAL CHART
# ══════════════════════════════════════════════════════
if items and len(items) > 1:
    try:
        import plotly.express as px
        import pandas as pd

        chart_data = []
        for item in items[:2000]:  # Cap chart data for performance
            dt = item.get("timestamp", "")
            if not dt:
                continue
            try:
                parsed = datetime.fromisoformat(dt.replace("Z", "+00:00")) if "T" in dt else datetime.fromisoformat(dt)
            except (ValueError, TypeError):
                continue
            chart_data.append({
                "date": parsed,
                "sender": item.get("sender", "?")[:30],
                "type": item["type"],
            })

        if chart_data:
            with st.expander("Visual Timeline", expanded=False):
                df = pd.DataFrame(chart_data)
                fig = px.scatter(df, x="date", y="sender", color="type",
                                 color_discrete_map={"email": "#00d4ff", "chat": "#ff9f43"},
                                 title="Communication Pattern")
                fig.update_layout(height=max(300, len(df["sender"].unique()) * 25 + 100),
                                  xaxis_title="", yaxis_title="", showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass

st.divider()

# ══════════════════════════════════════════════════════
# PAGINATION
# ══════════════════════════════════════════════════════
ITEMS_PER_PAGE = 50

if "tl_page" not in st.session_state:
    st.session_state.tl_page = 0

total_pages = max(1, (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
if st.session_state.tl_page >= total_pages:
    st.session_state.tl_page = total_pages - 1

page_start = st.session_state.tl_page * ITEMS_PER_PAGE
page_end = min(page_start + ITEMS_PER_PAGE, len(items))
page_items = items[page_start:page_end]

def tl_prev():
    st.session_state.tl_page = max(0, st.session_state.tl_page - 1)
def tl_next():
    st.session_state.tl_page = min(total_pages - 1, st.session_state.tl_page + 1)
def tl_jump():
    st.session_state.tl_page = st.session_state._tl_jump - 1

col1, col2, col3, col4 = st.columns([1, 1, 3, 1])
with col1:
    st.button("Prev", disabled=st.session_state.tl_page == 0, key="tl_prev", on_click=tl_prev)
with col2:
    st.button("Next", disabled=st.session_state.tl_page >= total_pages - 1, key="tl_next", on_click=tl_next)
with col3:
    st.markdown(f"**Page {st.session_state.tl_page + 1} of {total_pages}** ({page_start + 1}–{page_end} of {len(items):,})")
with col4:
    st.selectbox("Jump", list(range(1, total_pages + 1)), index=st.session_state.tl_page,
                 key="_tl_jump", on_change=tl_jump, label_visibility="collapsed")

# ══════════════════════════════════════════════════════
# COMPACT TABLE + DETAIL PANEL
# ══════════════════════════════════════════════════════
# Category color mapping
cat_colors = {
    "my_lawyer": "blue", "family_lawyer": "blue", "criminal_lawyer": "blue",
    "opposing_lawyer": "red", "ex_spouse": "red",
    "police": "orange", "cas_worker": "violet", "court": "green",
    "therapist": "green", "financial": "yellow",
}

# Get evidence tags for display (if any case exists)
cases = db.get_cases()
tag_map = {}
if cases:
    for case in cases:
        tags = db.get_evidence_tags_for_case(case["id"])
        for t in tags:
            key = f"{t['item_type']}_{t['item_id']}"
            tag_map[key] = t

# Get sender categories
from casepulse.storage.database import Database as _DB
sender_cats = {}
for s in db.get_senders():
    cats = _DB.parse_categories(s.get("category"))
    if cats:
        sender_cats[s["email"]] = cats

current_month = ""

for item in page_items:
    ts = item.get("timestamp", "")
    item_date = ts[:10] if ts else ""
    item_time = ts[11:16] if len(ts) > 11 else ""
    item_month = item_date[:7] if item_date else ""

    # Month separator
    if item_month and item_month != current_month:
        current_month = item_month
        try:
            month_label = datetime.strptime(item_month, "%Y-%m").strftime("%B %Y")
        except ValueError:
            month_label = item_month
        st.markdown(f"### {month_label}")

    # Build compact row
    sender = item.get("sender", "")
    sender_name = item.get("sender_name", "")
    subject = item.get("subject", "") or "(no subject)"
    direction = item.get("direction", "")
    item_type = item["type"]
    tag_key = f"{item_type}_{item['id']}"
    evidence_tag = tag_map.get(tag_key)

    # Direction icon
    dir_icon = "<-" if direction == "received" else "->" if direction == "sent" else ""

    # Build badges
    badges = ""
    if item.get("is_forwarded"):
        badges += " `FWD`"
    if item.get("has_attachments"):
        badges += " `ATT`"
    if evidence_tag:
        label = evidence_tag.get("exhibit_label", "")
        if label:
            badges += f" **[{label}]**"
        flag = evidence_tag.get("flag", "")
        if flag and flag != "none":
            badges += f" *{flag}*"
    if item_type == "chat":
        badges += " `CHAT`"
    # Thread indicator
    if item.get("thread_count") and item["thread_count"] > 1:
        badges += f" `thread {item['thread_pos']}/{item['thread_count']}`"

    # Sender category color
    sender_cat_list = sender_cats.get(sender, [])
    cat_badge = ""
    if sender_cat_list:
        primary_cat = sender_cat_list[0]
        cat_badge = f" `{primary_cat}`"

    # Display name
    display = sender_name if sender_name and sender_name != sender else sender
    account_tag = f" [{item.get('account', '')}]" if item.get("account") else ""

    # Compact row with expander
    header = f"{item_date} {item_time} | {dir_icon} {display} | {subject[:70]}{badges}{cat_badge}"

    with st.expander(header):
        # ── Detail Panel ──
        if item_type == "email":
            email_data = db.get_email_by_id(item["id"])
            if email_data:
                # Headers
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**From:** {email_data.get('sender_name', '')} <{email_data.get('sender_email', '')}>")

                    recips = email_data.get("recipients", "")
                    if recips:
                        try:
                            rlist = json.loads(recips) if isinstance(recips, str) else recips
                            if isinstance(rlist, list):
                                to_str = ", ".join(r.get("email", str(r)) if isinstance(r, dict) else str(r) for r in rlist)
                                st.markdown(f"**To:** {to_str}")
                        except Exception:
                            pass

                    st.markdown(f"**Date:** {email_data.get('date_received', '')[:19]}")
                    st.markdown(f"**Subject:** {email_data.get('subject', '')}")
                    if email_data.get("is_forwarded"):
                        st.markdown(f"**Originally from:** {email_data.get('original_sender', '')} ({email_data.get('original_date', '')})")

                with col2:
                    st.caption(f"Direction: {email_data.get('direction', '')}")
                    st.caption(f"Mailbox: {account_lookup.get(email_data.get('account_id'), '')}")
                    if evidence_tag:
                        st.caption(f"Exhibit: {evidence_tag.get('exhibit_label', 'none')}")
                        st.caption(f"Flag: {evidence_tag.get('flag', 'none')}")

                # Body
                body = email_data.get("body_text", "") or ""
                if body:
                    st.markdown("---")
                    st.text_area("Email content", body, height=250,
                                 disabled=True, key=f"body_{item['id']}",
                                 label_visibility="collapsed")

                # Attachments
                attachments = db.get_attachments_for_email(item["id"])
                if attachments:
                    st.markdown(f"**Attachments ({len(attachments)}):**")
                    for att in attachments:
                        from casepulse.attachments.extractor import get_file_size_human
                        size = get_file_size_human(att.get("size_bytes", 0))
                        dup = " (duplicate)" if att.get("is_duplicate") else ""

                        st.markdown(f"**{att['filename']}** ({size}){dup}")

                        fpath = att.get("file_path", "")
                        if fpath and Path(fpath).exists():
                            ext = Path(fpath).suffix.lower()
                            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                                st.image(fpath, width=300)
                            else:
                                st.download_button(
                                    f"Download {att['filename']}",
                                    Path(fpath).read_bytes(),
                                    file_name=att["filename"],
                                    mime="application/pdf" if ext == ".pdf" else "application/octet-stream",
                                    key=f"dl_att_{att['id']}",
                                )

                        # Show extracted text inline (preview + expandable full)
                        if att.get("extracted_text"):
                            extracted = att["extracted_text"]
                            # Show first 500 chars inline
                            st.caption(extracted[:500])
                            if len(extracted) > 500:
                                with st.expander(f"Full text from {att['filename']} ({len(extracted):,} chars)"):
                                    st.text(extracted[:5000])

        elif item_type == "chat":
            chat_data = None
            chat_msgs = db.get_chat_messages(limit=1)
            # Get the specific chat message
            conn_chat = sqlite3.connect(str(db.db_path))
            conn_chat.row_factory = sqlite3.Row
            chat_row = conn_chat.execute("SELECT * FROM chat_messages WHERE id = ?", (item["id"],)).fetchone()
            conn_chat.close()

            if chat_row:
                chat_data = dict(chat_row)
                st.markdown(f"**From:** {chat_data.get('sender', '')}")
                st.markdown(f"**Chat:** {chat_data.get('chat_name', '')}")
                st.markdown(f"**Date:** {chat_data.get('timestamp', '')}")
                st.markdown(f"**Platform:** {chat_data.get('platform', '')}")
                st.markdown("---")
                st.text(chat_data.get("message_text", ""))

                if chat_data.get("has_media") and chat_data.get("media_path"):
                    mpath = chat_data["media_path"]
                    if Path(mpath).exists():
                        ext = Path(mpath).suffix.lower()
                        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                            st.image(mpath, width=300)

        # ── Inline Actions ──
        st.markdown("---")
        act_col1, act_col2, act_col3, act_col4 = st.columns(4)

        with act_col1:
            # Quick annotate
            note = st.text_input("Add note", placeholder="e.g., contradicts para 12...",
                                  key=f"tl_note_{item_type}_{item['id']}", label_visibility="collapsed")
            if note and st.button("Save Note", key=f"tl_save_note_{item_type}_{item['id']}"):
                case_id = cases[0]["id"] if cases else None
                db.add_annotation(item_type, item["id"], note, case_id)
                st.success("Note saved")

        with act_col2:
            # Quick flag
            from casepulse.legal.exhibits import FLAGS
            flag_options = [code for code, _ in FLAGS]
            current_flag = evidence_tag.get("flag", "none") if evidence_tag else "none"
            new_flag = st.selectbox("Flag", flag_options, index=flag_options.index(current_flag),
                                     format_func=lambda x: dict(FLAGS).get(x, x),
                                     key=f"tl_flag_{item_type}_{item['id']}", label_visibility="collapsed")
            if new_flag != current_flag and cases:
                db.tag_evidence(item_type, item["id"], cases[0]["id"], flag=new_flag)

        with act_col3:
            # Quick tag to case
            if cases:
                from casepulse.legal.exhibits import generate_exhibit_label
                if st.button("Tag as Exhibit", key=f"tl_exhibit_{item_type}_{item['id']}"):
                    label = generate_exhibit_label(cases[0]["id"], db)
                    db.tag_evidence(item_type, item["id"], cases[0]["id"], exhibit_label=label)
                    st.success(f"Tagged as {label}")

        with act_col4:
            # Ask AI about this item
            if st.button("Ask AI", key=f"tl_ai_{item_type}_{item['id']}"):
                st.session_state["ai_context_item"] = {
                    "type": item_type,
                    "id": item["id"],
                    "sender": sender,
                    "subject": subject,
                    "date": item_date,
                }

        # Show existing annotations
        annotations = db.get_annotations(item_type, item["id"])
        if annotations:
            for ann in annotations[:5]:
                st.caption(f"Note [{ann['created_at'][:10]}]: {ann['note_text']}")

# ── AI Context Query (if triggered from a timeline item) ──
if "ai_context_item" in st.session_state:
    ctx = st.session_state["ai_context_item"]
    st.divider()
    st.markdown(f"### Ask AI about: {ctx['sender']} — {ctx['subject']} ({ctx['date']})")

    ai_question = st.text_input("What do you want to know?",
                                 placeholder="Summarize this email / Find contradictions / What's the legal significance?",
                                 key="tl_ai_question")

    if ai_question and st.button("Ask", key="tl_ai_ask"):
        # Get the full content
        context_text = ""
        if ctx["type"] == "email":
            email_data = db.get_email_by_id(ctx["id"])
            if email_data:
                context_text = (
                    f"From: {email_data.get('sender_email', '')}\n"
                    f"To: {email_data.get('recipients', '')}\n"
                    f"Date: {email_data.get('date_received', '')}\n"
                    f"Subject: {email_data.get('subject', '')}\n\n"
                    f"{email_data.get('body_text', '')}"
                )
        elif ctx["type"] == "chat":
            conn_c = sqlite3.connect(str(db.db_path))
            conn_c.row_factory = sqlite3.Row
            chat_r = conn_c.execute("SELECT * FROM chat_messages WHERE id = ?", (ctx["id"],)).fetchone()
            conn_c.close()
            if chat_r:
                context_text = f"Chat from {chat_r['sender']} ({chat_r['timestamp']}):\n{chat_r['message_text']}"

        if context_text:
            with st.spinner("Asking AI..."):
                try:
                    from casepulse.llm.api_provider import create_provider
                    llm = create_provider(config.llm_provider, model=config.llm_model,
                                          api_key=config.llm_api_key, base_url=config.llm_base_url)
                    answer = llm.query(
                        system_prompt="You are a legal case analyst. Answer precisely based on the provided email/message. Cite specific text.",
                        user_prompt=ai_question,
                        context_chunks=[context_text],
                    )
                    st.markdown(answer)
                except Exception as e:
                    st.error(f"AI error: {e}")

    if st.button("Close AI Panel", key="tl_ai_close"):
        del st.session_state["ai_context_item"]
        st.rerun()

# ══════════════════════════════════════════════════════
# BOTTOM PAGINATION
# ══════════════════════════════════════════════════════
if total_pages > 1:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.button("Prev Page", disabled=st.session_state.tl_page == 0, key="tl_prev_bot", on_click=tl_prev)
    with col2:
        st.markdown(f"**Page {st.session_state.tl_page + 1} of {total_pages}**")
    with col3:
        st.button("Next Page", disabled=st.session_state.tl_page >= total_pages - 1, key="tl_next_bot", on_click=tl_next)

# ══════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════
st.divider()
st.markdown("### Quick Export")

# Build export data upfront
md_lines = [f"# CasePulse Timeline\n", f"**Range:** {filter_start} to {filter_end}\n",
            f"**Items:** {len(items)}\n", "---\n"]
current_dt = ""
for item in items:
    ts = str(item.get("timestamp", ""))
    if ts[:10] != current_dt:
        current_dt = ts[:10]
        md_lines.append(f"\n## {current_dt}\n")
    sender = item.get("sender", "")
    subject = item.get("subject", "")
    md_lines.append(f"### {ts[11:16]} — {sender}\n**{subject}**\n")

md_content = "\n".join(md_lines)
json_data = json.dumps([{
    "date": i.get("timestamp", ""), "sender": i.get("sender", ""),
    "subject": i.get("subject", ""), "type": i["type"],
    "direction": i.get("direction", ""),
} for i in items], indent=2, default=str)

col1, col2, col3 = st.columns(3)
with col1:
    st.download_button("Download Markdown", md_content,
                        file_name=f"timeline_{filter_start}_{filter_end}.md", mime="text/markdown")
with col2:
    st.download_button("Download JSON", json_data,
                        file_name=f"timeline_{filter_start}_{filter_end}.json", mime="application/json")
with col3:
    st.page_link("pages/8_Export.py", label="Full Export Options", icon=None)
