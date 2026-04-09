"""Discover Senders page — Scan mailboxes and select relevant contacts."""
import streamlit as st
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Discover Senders", page_icon="CP", layout="wide")

st.markdown("## Discover Senders")
st.markdown("Scan your accounts to find all contacts, then select the ones relevant to your case.")


from components.page_init import init_page
db, config = init_page()

accounts = db.get_accounts()
if not accounts:
    st.warning("No accounts connected. Go to **Accounts** first.")
    st.stop()

# ── Date Range Selection ──
st.markdown("### Date Range to Scan")
col1, col2 = st.columns(2)
with col1:
    scan_start = st.date_input(
        "From",
        value=date.fromisoformat(config.date_start),
        key="scan_start",
    )
with col2:
    scan_end = st.date_input(
        "To",
        value=date.fromisoformat(config.date_end),
        key="scan_end",
    )

# ── Account Selection ──
st.markdown("### Accounts to Scan")
selected_accounts = []
for acc in accounts:
    provider_label = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
    if st.checkbox(f"{provider_label}: {acc['email']}", value=True, key=f"scan_{acc['id']}"):
        selected_accounts.append(acc)

# ── Scan Button ──
if st.button("Scan for Contacts", type="primary", disabled=not selected_accounts):
    all_contacts = {}

    with st.status("Scanning mailboxes...", expanded=True) as status:
        for acc in selected_accounts:
            st.write(f"Scanning {acc['email']}...")

            try:
                if acc["provider"] == "microsoft":
                    from casepulse.auth.microsoft import MicrosoftAuth
                    auth = MicrosoftAuth(client_id=acc.get("client_id", ""), account_email=acc["email"])
                    token = auth.get_access_token()
                    if not token:
                        st.warning(f"Token expired for {acc['email']}. Please re-authenticate in Accounts.")
                        continue

                    from casepulse.email_engine.microsoft_fetcher import MicrosoftFetcher
                    fetcher = MicrosoftFetcher(token, acc["id"], db)
                    contacts = fetcher.scan_senders(
                        str(scan_start), str(scan_end),
                        progress_cb=lambda msg: st.write(msg),
                    )

                elif acc["provider"] == "google":
                    from casepulse.auth.google_auth import GoogleAuth
                    creds_file = acc.get("token_file", "")
                    auth = GoogleAuth(credentials_file=creds_file, account_email=acc["email"])
                    service = auth.get_service()
                    if not service:
                        st.warning(f"Token expired for {acc['email']}. Please re-authenticate in Accounts.")
                        continue

                    from casepulse.email_engine.gmail_fetcher import GmailFetcher
                    fetcher = GmailFetcher(service, acc["id"], db)
                    contacts = fetcher.scan_senders(
                        str(scan_start), str(scan_end),
                        progress_cb=lambda msg: st.write(msg),
                    )

                # Merge contacts
                for c in contacts:
                    email = c["email"]
                    if email in all_contacts:
                        all_contacts[email]["count"] += c["count"]
                    else:
                        all_contacts[email] = c
                        # Register in database
                        db.upsert_sender(email, c.get("name", ""))

                st.write(f"Found {len(contacts)} contacts in {acc['email']}")

            except Exception as e:
                st.error(f"Error scanning {acc['email']}: {str(e)}")

        status.update(label=f"Scan complete — {len(all_contacts)} unique contacts found", state="complete")

st.divider()

# ── Sender Selection ──
senders = db.get_senders()

if not senders:
    st.info("No contacts found yet. Click **Scan for Contacts** above to discover senders in your mailboxes.")
    st.stop()

# Category options for legal case
categories = [
    "other", "my_lawyer", "opposing_lawyer", "ex_spouse",
    "police", "cas_worker", "therapist", "court", "mediator",
    "financial", "family", "witness", "school", "employer",
]
category_labels = {
    "other": "Other",
    "my_lawyer": "My Lawyer",
    "opposing_lawyer": "Opposing Lawyer",
    "ex_spouse": "Ex-Spouse",
    "police": "Police",
    "cas_worker": "CAS Worker",
    "therapist": "Therapist",
    "court": "Court",
    "mediator": "Mediator",
    "financial": "Financial",
    "family": "Family",
    "witness": "Witness",
    "school": "School",
    "employer": "Employer",
}

# Auto-detect known patterns for smart sorting
NOREPLY_PATTERNS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "notifications", "newsletter",
    "updates@", "info@", "support@", "billing@", "alert",
]

def is_noreply(email: str) -> bool:
    lower = email.lower()
    return any(p in lower for p in NOREPLY_PATTERNS)

st.markdown("### Select Relevant Contacts")
st.markdown("Check the contacts relevant to your case. Sorted by email frequency — your key contacts are at the top.")

# ── Filter controls ──
col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    search = st.text_input("Search contacts", placeholder="Filter by name or email...", key="sender_search")
with col2:
    show_filter = st.selectbox("Show", ["All", "Selected", "Unselected", "People only"], key="show_filter")
with col3:
    sort_by = st.selectbox("Sort by", ["Frequency", "Name", "Email", "Category"], key="sort_by")
with col4:
    cat_filter = st.selectbox(
        "Category",
        ["All categories"] + list(category_labels.values()),
        key="cat_filter",
    )

# Subject/content search — find senders by what they sent
subject_search = st.text_input(
    "Search by email subject or content",
    placeholder="e.g., ticket, itinerary, booking, invoice, court order...",
    key="subject_search",
    help="Find senders who sent emails containing this text in the subject or body — useful for finding noreply senders like airlines, courts, banks",
)

# Build sender set matching subject/content search
subject_match_senders = None
if subject_search:
    try:
        import sqlite3
        conn = sqlite3.connect(str(db.db_path))
        conn.row_factory = sqlite3.Row
        search_term = f"%{subject_search}%"
        rows = conn.execute(
            """SELECT DISTINCT sender_email, sender_name, COUNT(*) as cnt
               FROM emails
               WHERE subject LIKE ? OR body_text LIKE ?
               GROUP BY sender_email
               ORDER BY cnt DESC""",
            (search_term, search_term)
        ).fetchall()
        subject_match_senders = {r["sender_email"]: r["cnt"] for r in rows}
        conn.close()

        if subject_match_senders:
            st.success(
                f"Found **{len(subject_match_senders)}** senders with emails matching \"{subject_search}\" "
                f"({sum(subject_match_senders.values())} emails total)"
            )
        else:
            st.warning(f"No emails found matching \"{subject_search}\". Try fetching emails first, then search.")
    except Exception:
        pass

# Build and filter the list
filtered = list(senders)

# If subject search is active, only show matching senders
if subject_match_senders is not None:
    filtered = [s for s in filtered if s["email"] in subject_match_senders]

# Text search (name/email)
if search:
    search_lower = search.lower()
    filtered = [s for s in filtered if search_lower in s["email"].lower() or
                search_lower in (s.get("display_name") or "").lower()]

# Show filter
if show_filter == "Selected":
    filtered = [s for s in filtered if s["selected"]]
elif show_filter == "Unselected":
    filtered = [s for s in filtered if not s["selected"]]
elif show_filter == "People only":
    filtered = [s for s in filtered if not is_noreply(s["email"])]

# Category filter
if cat_filter != "All categories":
    cat_code = [k for k, v in category_labels.items() if v == cat_filter]
    if cat_code:
        filtered = [s for s in filtered if s.get("category") == cat_code[0]]

# Sort
# We need email counts from the database for frequency sort
email_counts = {}
try:
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT sender_email, COUNT(*) as cnt FROM emails
           GROUP BY sender_email"""
    ).fetchall()
    for r in rows:
        email_counts[r["sender_email"]] = r["cnt"]
    conn.close()
except Exception:
    pass

if sort_by == "Frequency":
    filtered.sort(key=lambda s: email_counts.get(s["email"], 0), reverse=True)
elif sort_by == "Name":
    filtered.sort(key=lambda s: (s.get("display_name") or s["email"]).lower())
elif sort_by == "Email":
    filtered.sort(key=lambda s: s["email"].lower())
elif sort_by == "Category":
    filtered.sort(key=lambda s: (s.get("category") or "zzz", s["email"].lower()))

# ── Stats ──
selected_count = sum(1 for s in senders if s["selected"])
total_count = len(senders)
noreply_count = sum(1 for s in senders if is_noreply(s["email"]))

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Contacts", total_count)
with col2:
    st.metric("Selected", selected_count)
with col3:
    st.metric("Showing", len(filtered))
with col4:
    st.metric("Auto-Ignored", noreply_count, help="noreply, newsletters, notifications")

# ── Bulk actions ──
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("Select All Visible"):
        for s in filtered:
            db.set_sender_selected(s["id"], True)
        st.rerun()
with col2:
    if st.button("Deselect All Visible"):
        for s in filtered:
            db.set_sender_selected(s["id"], False)
        st.rerun()

# ── Pagination ──
ITEMS_PER_PAGE = 50

if "sender_page" not in st.session_state:
    st.session_state.sender_page = 0

total_pages = max(1, (len(filtered) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

# Clamp current page
if st.session_state.sender_page >= total_pages:
    st.session_state.sender_page = total_pages - 1

page_start = st.session_state.sender_page * ITEMS_PER_PAGE
page_end = min(page_start + ITEMS_PER_PAGE, len(filtered))
page_items = filtered[page_start:page_end]

# Page navigation
if total_pages > 1:
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
    with col1:
        if st.button("First", disabled=st.session_state.sender_page == 0):
            st.session_state.sender_page = 0
            st.rerun()
    with col2:
        if st.button("Prev", disabled=st.session_state.sender_page == 0):
            st.session_state.sender_page -= 1
            st.rerun()
    with col3:
        st.markdown(f"**Page {st.session_state.sender_page + 1} of {total_pages}** ({page_start + 1}–{page_end} of {len(filtered)})")
    with col4:
        if st.button("Next", disabled=st.session_state.sender_page >= total_pages - 1):
            st.session_state.sender_page += 1
            st.rerun()
    with col5:
        if st.button("Last", disabled=st.session_state.sender_page >= total_pages - 1):
            st.session_state.sender_page = total_pages - 1
            st.rerun()

st.markdown("---")

# ── Contact list ──
for sender in page_items:
    email_addr = sender["email"]
    freq = email_counts.get(email_addr, 0)
    is_auto = is_noreply(email_addr)

    col1, col2, col3, col4 = st.columns([0.5, 4, 2, 1.5])

    with col1:
        selected = st.checkbox(
            "sel", value=bool(sender["selected"]),
            key=f"sel_{sender['id']}",
            label_visibility="collapsed",
        )
        if selected != bool(sender["selected"]):
            db.set_sender_selected(sender["id"], selected)

    with col2:
        name = sender.get("display_name") or ""
        auto_tag = " *(auto/noreply)*" if is_auto else ""
        if name:
            st.markdown(f"**{name}**{auto_tag}  \n{email_addr}")
        else:
            st.markdown(f"**{email_addr}**{auto_tag}")

        # Show matching subjects when subject search is active
        if subject_match_senders is not None and email_addr in subject_match_senders:
            try:
                import sqlite3
                conn = sqlite3.connect(str(db.db_path))
                conn.row_factory = sqlite3.Row
                search_term = f"%{subject_search}%"
                subj_rows = conn.execute(
                    """SELECT subject, date_received FROM emails
                       WHERE sender_email = ? AND (subject LIKE ? OR body_text LIKE ?)
                       ORDER BY date_received DESC LIMIT 3""",
                    (email_addr, search_term, search_term)
                ).fetchall()
                conn.close()
                if subj_rows:
                    previews = [f"*{r['subject'][:60]}* ({r['date_received'][:10]})" for r in subj_rows]
                    match_count = subject_match_senders[email_addr]
                    extra = f" +{match_count - 3} more" if match_count > 3 else ""
                    st.caption(f"Matching: {' | '.join(previews)}{extra}")
            except Exception:
                pass

    with col3:
        cat = st.selectbox(
            "Category",
            categories,
            index=categories.index(sender.get("category", "other")),
            key=f"cat_{sender['id']}",
            format_func=lambda x: category_labels.get(x, x),
            label_visibility="collapsed",
        )
        if cat != sender.get("category", "other"):
            db.set_sender_category(sender["id"], cat)

    with col4:
        st.caption(f"{freq} emails" if freq else "scanned")

# Bottom pagination
if total_pages > 1:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("Prev Page", disabled=st.session_state.sender_page == 0, key="prev_bottom"):
            st.session_state.sender_page -= 1
            st.rerun()
    with col2:
        st.markdown(f"**Page {st.session_state.sender_page + 1} of {total_pages}**")
    with col3:
        if st.button("Next Page", disabled=st.session_state.sender_page >= total_pages - 1, key="next_bottom"):
            st.session_state.sender_page += 1
            st.rerun()

st.divider()

# ── Keyword Management ──
st.markdown("### Keywords")
st.markdown("Add keywords to filter emails during fetch. Only emails containing at least one keyword will be included.")

keywords = db.get_keywords(active_only=False)

# Add keyword
col1, col2 = st.columns([3, 1])
with col1:
    new_keyword = st.text_input("Add keyword", placeholder="Enter a keyword...", key="new_kw")
with col2:
    st.markdown("")
    st.markdown("")
    if st.button("Add", disabled=not new_keyword):
        db.add_keyword(new_keyword.strip())
        st.rerun()

# Show existing keywords
if keywords:
    for kw in keywords:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            active = st.checkbox(
                kw["keyword"],
                value=bool(kw["active"]),
                key=f"kw_{kw['id']}",
            )
            if active != bool(kw["active"]):
                db.toggle_keyword(kw["id"], active)
        with col3:
            if st.button("Remove", key=f"rm_kw_{kw['id']}"):
                db.delete_keyword(kw["id"])
                st.rerun()
else:
    st.caption("No keywords added. Keywords are optional — if none are set, all emails from selected senders will be fetched.")
