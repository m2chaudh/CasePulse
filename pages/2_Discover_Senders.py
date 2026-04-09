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
existing_senders = db.get_senders()
if existing_senders:
    st.info(
        f"**{len(existing_senders):,} contacts already saved** from previous scans. "
        f"Your selections are preserved. Only click Scan again if you changed the date range or added new accounts."
    )

col1, col2 = st.columns([1, 1])
with col1:
    scan_clicked = st.button("Scan for Contacts", type="primary", disabled=not selected_accounts)
with col2:
    if st.button("Stop Scan"):
        st.session_state["scan_cancel"] = True

if scan_clicked:
    import threading
    import time

    st.session_state["scan_running"] = True
    st.session_state["scan_cancel"] = False

    # Shared state for parallel threads
    scan_progress = {}   # {email: "status message"}
    scan_results = {}    # {email: [contacts]}
    scan_errors = {}     # {email: "error message"}
    scan_done = {}       # {email: True/False}

    def scan_one_account(acc_info):
        """Scan a single account in a background thread."""
        acc_email = acc_info["email"]
        scan_progress[acc_email] = "Starting..."
        scan_done[acc_email] = False

        try:
            contacts = []

            if acc_info["provider"] == "microsoft":
                from casepulse.auth.microsoft import MicrosoftAuth
                auth = MicrosoftAuth(client_id=acc_info.get("client_id", ""), account_email=acc_email)
                token = auth.get_access_token()
                if not token:
                    scan_errors[acc_email] = "Token expired. Re-authenticate in Accounts."
                    scan_done[acc_email] = True
                    return

                from casepulse.email_engine.microsoft_fetcher import MicrosoftFetcher
                fetcher = MicrosoftFetcher(token, acc_info["id"], db)
                contacts = fetcher.scan_senders(
                    str(scan_start), str(scan_end),
                    progress_cb=lambda msg, e=acc_email: scan_progress.update({e: msg}),
                )

            elif acc_info["provider"] == "google":
                from casepulse.auth.google_auth import GoogleAuth
                creds_file = acc_info.get("token_file", "")
                auth = GoogleAuth(credentials_file=creds_file, account_email=acc_email)
                service = auth.get_service()
                if not service:
                    scan_errors[acc_email] = "Token expired. Re-authenticate in Accounts."
                    scan_done[acc_email] = True
                    return

                from casepulse.email_engine.gmail_fetcher import GmailFetcher
                fetcher = GmailFetcher(service, acc_info["id"], db)
                contacts = fetcher.scan_senders(
                    str(scan_start), str(scan_end),
                    progress_cb=lambda msg, e=acc_email: scan_progress.update({e: msg}),
                )

            # Save to DB immediately (thread-safe — SQLite WAL mode)
            for c in contacts:
                db.upsert_sender(c["email"], c.get("name", ""))

            scan_results[acc_email] = contacts
            scan_progress[acc_email] = f"Done — {len(contacts)} contacts found"

        except Exception as e:
            scan_errors[acc_email] = str(e)

        scan_done[acc_email] = True

    # Launch all scans in parallel
    threads = []
    for acc in selected_accounts:
        t = threading.Thread(target=scan_one_account, args=(acc,), daemon=True)
        threads.append(t)
        t.start()

    # Create per-account progress containers
    st.markdown("### Scan Progress")
    progress_containers = {}
    for acc in selected_accounts:
        provider_label = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
        st.markdown(f"**{provider_label}: {acc['email']}**")
        progress_containers[acc["email"]] = st.empty()

    summary_container = st.empty()

    # Poll until all done or cancelled
    while not all(scan_done.get(acc["email"], False) for acc in selected_accounts):
        if st.session_state.get("scan_cancel"):
            break

        # Update progress displays
        for acc in selected_accounts:
            email = acc["email"]
            msg = scan_progress.get(email, "Waiting...")
            if email in scan_errors:
                progress_containers[email].error(scan_errors[email])
            elif scan_done.get(email):
                progress_containers[email].success(msg)
            else:
                progress_containers[email].info(msg)

        completed = sum(1 for acc in selected_accounts if scan_done.get(acc["email"]))
        summary_container.caption(
            f"Progress: {completed}/{len(selected_accounts)} accounts complete"
        )

        time.sleep(1)

    # Final update
    for acc in selected_accounts:
        email = acc["email"]
        msg = scan_progress.get(email, "")
        if email in scan_errors:
            progress_containers[email].error(f"Error: {scan_errors[email]}")
        elif scan_done.get(email):
            progress_containers[email].success(msg)
        else:
            progress_containers[email].warning("Cancelled")

    # Wait for threads to finish (they're daemon threads so they'll die if we don't)
    for t in threads:
        t.join(timeout=2)

    st.session_state["scan_running"] = False

    # Final summary
    total_contacts = sum(len(r) for r in scan_results.values())
    all_unique = set()
    for contacts in scan_results.values():
        for c in contacts:
            all_unique.add(c["email"])

    cancelled = st.session_state.get("scan_cancel", False)

    st.markdown("### Scan Summary")
    for acc in selected_accounts:
        email = acc["email"]
        provider_label = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
        if email in scan_results:
            count = len(scan_results[email])
            st.markdown(f"- **{provider_label}: {email}** — {count:,} contacts found")
        elif email in scan_errors:
            st.markdown(f"- **{provider_label}: {email}** — Error: {scan_errors[email]}")
        else:
            st.markdown(f"- **{provider_label}: {email}** — Cancelled")

    if cancelled:
        st.warning(f"Scan stopped. {len(all_unique):,} unique contacts saved from completed accounts.")
    else:
        st.success(f"Scan complete. **{len(all_unique):,}** unique contacts found across all accounts.")

st.divider()

# ── Sender Selection ──
senders = db.get_senders()

if not senders:
    st.info("No contacts found yet. Click **Scan for Contacts** above to discover senders in your mailboxes.")
    st.stop()

# Category options for legal case
category_labels = {
    "benefits": "Benefits",
    "cas_worker": "CAS Worker",
    "court": "Court",
    "daycare": "Daycare",
    "disclosure": "Disclosure",
    "docusign": "DocuSign",
    "employer": "Employer",
    "ex_spouse": "Ex-Spouse",
    "expenses": "Expenses",
    "family": "Family",
    "financial": "Financial",
    "insurance": "Insurance",
    "mediator": "Mediator",
    "moving": "Moving",
    "my_lawyer": "My Lawyer",
    "opposing_lawyer": "Opposing Lawyer",
    "police": "Police",
    "school": "School",
    "therapist": "Therapist",
    "travel": "Travel",
    "witness": "Witness",
    "other": "Other",
}
categories = list(category_labels.keys())

from casepulse.storage.database import Database as _DB

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

# ── Mailbox filter ──
all_accounts = db.get_accounts()
mailbox_options = ["All mailboxes"] + [a["email"] for a in all_accounts]
selected_mailbox = st.selectbox("View contacts from", mailbox_options, key="mailbox_filter")

# Get account_id for filtering
selected_account_id = None
if selected_mailbox != "All mailboxes":
    for a in all_accounts:
        if a["email"] == selected_mailbox:
            selected_account_id = a["id"]
            break

# ── Build email frequency + domain data upfront ──
email_counts = {}
domain_counts = {}
two_way_senders = set()
senders_in_account = None  # set of sender emails for the selected account
try:
    import sqlite3
    conn = sqlite3.connect(str(db.db_path))
    conn.row_factory = sqlite3.Row

    # Email frequency per sender (optionally filtered by account)
    if selected_account_id:
        rows = conn.execute(
            "SELECT sender_email, COUNT(*) as cnt FROM emails WHERE account_id = ? GROUP BY sender_email",
            (selected_account_id,)
        ).fetchall()
        # Also build the set of senders that appear in this account
        senders_in_account = set()
        all_in_account = conn.execute(
            """SELECT DISTINCT sender_email FROM emails WHERE account_id = ?
               UNION
               SELECT DISTINCT sender_email FROM emails WHERE account_id = ? AND direction = 'sent'""",
            (selected_account_id, selected_account_id)
        ).fetchall()
        for r in all_in_account:
            senders_in_account.add(r["sender_email"].lower())
        # Also include recipients from sent emails in this account
        recip_rows_acct = conn.execute(
            "SELECT recipients FROM emails WHERE account_id = ?",
            (selected_account_id,)
        ).fetchall()
        import json as _json
        for r in recip_rows_acct:
            recips = r["recipients"]
            if recips:
                try:
                    rlist = _json.loads(recips) if isinstance(recips, str) else recips
                    for addr in rlist:
                        email_addr = addr if isinstance(addr, str) else addr.get("email", addr.get("address", ""))
                        if email_addr:
                            senders_in_account.add(email_addr.lower())
                except Exception:
                    pass
    else:
        rows = conn.execute(
            "SELECT sender_email, COUNT(*) as cnt FROM emails GROUP BY sender_email"
        ).fetchall()

    for r in rows:
        email_counts[r["sender_email"]] = r["cnt"]

    # Two-way detection: senders who also appear in recipients
    sent_to = set()
    if selected_account_id:
        recip_rows = conn.execute(
            "SELECT DISTINCT recipients FROM emails WHERE direction = 'sent' AND account_id = ?",
            (selected_account_id,)
        ).fetchall()
    else:
        recip_rows = conn.execute("SELECT DISTINCT recipients FROM emails WHERE direction = 'sent'").fetchall()

    for r in recip_rows:
        recips = r["recipients"]
        if recips:
            try:
                rlist = _json.loads(recips) if isinstance(recips, str) else recips
                for addr in rlist:
                    email_addr = addr if isinstance(addr, str) else addr.get("email", addr.get("address", ""))
                    if email_addr:
                        sent_to.add(email_addr.lower())
            except Exception:
                pass
    received_from = set(e.lower() for e in email_counts.keys())
    two_way_senders = sent_to & received_from

    conn.close()
except Exception:
    pass

# Build domain data from senders
for s in senders:
    parts = s["email"].split("@")
    if len(parts) == 2:
        domain = parts[1].lower()
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

# ── Filter controls ──
st.markdown("### Filter & Find")

col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    search = st.text_input("Search by name or email", placeholder="e.g., manisha, lawyer, police...", key="sender_search")
with col2:
    show_filter = st.selectbox("Show", [
        "All", "Selected", "Unselected", "People only",
        "Two-way only", "Top 50", "Top 100", "Top 200",
    ], key="show_filter")
with col3:
    sort_by = st.selectbox("Sort by", ["Frequency", "Name", "Email", "Domain", "Category"], key="sort_by")
with col4:
    cat_filter = st.selectbox(
        "Category",
        ["All categories"] + list(category_labels.values()),
        key="cat_filter",
    )

# Domain filter
top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:30]
domain_options = ["All domains"] + [f"{d} ({c})" for d, c in top_domains]
col1, col2 = st.columns([1, 1])
with col1:
    domain_filter = st.selectbox("Filter by domain", domain_options, key="domain_filter",
                                  help="Select all contacts from a specific email domain (e.g., a law firm)")
with col2:
    subject_search = st.text_input(
        "Search by email subject/content",
        placeholder="e.g., ticket, itinerary, court order...",
        key="subject_search",
        help="Find senders by what they sent you",
    )

# ── Build sender set matching subject/content search ──
subject_match_senders = None
if subject_search:
    try:
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

# ── Build and filter the list ──
filtered = list(senders)

# Mailbox filter — only show contacts that appear in the selected account
if senders_in_account is not None:
    filtered = [s for s in filtered if s["email"].lower() in senders_in_account]

# Subject search
if subject_match_senders is not None:
    filtered = [s for s in filtered if s["email"] in subject_match_senders]

# Text search (name/email)
if search:
    search_lower = search.lower()
    filtered = [s for s in filtered if search_lower in s["email"].lower() or
                search_lower in (s.get("display_name") or "").lower()]

# Domain filter
if domain_filter != "All domains":
    selected_domain = domain_filter.split(" (")[0]
    filtered = [s for s in filtered if s["email"].lower().endswith(f"@{selected_domain}")]

# Show filter
if show_filter == "Selected":
    filtered = [s for s in filtered if s["selected"]]
elif show_filter == "Unselected":
    filtered = [s for s in filtered if not s["selected"]]
elif show_filter == "People only":
    filtered = [s for s in filtered if not is_noreply(s["email"])]
elif show_filter == "Two-way only":
    filtered = [s for s in filtered if s["email"].lower() in two_way_senders]
elif show_filter.startswith("Top "):
    top_n = int(show_filter.split(" ")[1])
    filtered.sort(key=lambda s: email_counts.get(s["email"], 0), reverse=True)
    filtered = filtered[:top_n]

# Category filter (handles both old single-string and new multi-category format)
if cat_filter != "All categories":
    cat_code = [k for k, v in category_labels.items() if v == cat_filter]
    if cat_code:
        target = cat_code[0]
        filtered = [s for s in filtered if target in _DB.parse_categories(s.get("category"))]

# Sort
if sort_by == "Frequency":
    filtered.sort(key=lambda s: email_counts.get(s["email"], 0), reverse=True)
elif sort_by == "Name":
    filtered.sort(key=lambda s: (s.get("display_name") or s["email"]).lower())
elif sort_by == "Email":
    filtered.sort(key=lambda s: s["email"].lower())
elif sort_by == "Domain":
    filtered.sort(key=lambda s: (s["email"].split("@")[-1], s["email"]))
elif sort_by == "Category":
    filtered.sort(key=lambda s: (s.get("category") or "zzz", s["email"].lower()))

# ── Stats ──
selected_count = sum(1 for s in senders if s["selected"])
total_count = len(senders)
noreply_count = sum(1 for s in senders if is_noreply(s["email"]))
two_way_count = sum(1 for s in senders if s["email"].lower() in two_way_senders)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Total Contacts", f"{total_count:,}")
with col2:
    st.metric("Selected", selected_count)
with col3:
    st.metric("Showing", f"{len(filtered):,}")
with col4:
    st.metric("Two-Way", two_way_count, help="Contacts you both sent to and received from — real conversations")
with col5:
    st.metric("Auto/Noreply", noreply_count)

# ── Bulk actions ──
col1, col2, col3, col4, col5 = st.columns([1, 1, 1.2, 1.2, 1])
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
with col3:
    if st.button("Select All Two-Way", help="Select all contacts with two-way communication"):
        for s in senders:
            if s["email"].lower() in two_way_senders:
                db.set_sender_selected(s["id"], True)
        st.rerun()
with col4:
    confirm_clear = st.checkbox(f"Clear all {selected_count} selections", key="confirm_clear")
with col5:
    if confirm_clear:
        if st.button("Confirm Clear", type="primary"):
            for s in senders:
                if s["selected"]:
                    db.set_sender_selected(s["id"], False)
            st.rerun()

# ── Bulk category assignment ──
if show_filter == "Selected" or len(filtered) <= 100:
    st.markdown("**Bulk assign categories to all visible contacts:**")
    bcol1, bcol2, bcol3 = st.columns([3, 1, 1])
    with bcol1:
        bulk_cats = st.multiselect(
            "Categories to add",
            categories,
            format_func=lambda x: category_labels.get(x, x),
            key="bulk_cat_assign",
            label_visibility="collapsed",
            placeholder="Select categories to add...",
        )
    with bcol2:
        if st.button(f"Add to {len(filtered)} visible", key="apply_bulk_cat", disabled=not bulk_cats):
            for s in filtered:
                existing = _DB.parse_categories(s.get("category"))
                merged = list(dict.fromkeys(existing + bulk_cats))  # preserve order, no dupes
                db.set_sender_category(s["id"], merged)
            labels = ", ".join(category_labels.get(c, c) for c in bulk_cats)
            st.success(f"Added {labels} to {len(filtered)} contacts")
            st.rerun()
    with bcol3:
        if st.button(f"Replace on {len(filtered)}", key="replace_bulk_cat", disabled=not bulk_cats,
                      help="Replace all existing categories with the selected ones"):
            for s in filtered:
                db.set_sender_category(s["id"], bulk_cats)
            labels = ", ".join(category_labels.get(c, c) for c in bulk_cats)
            st.success(f"Set {len(filtered)} contacts to {labels}")
            st.rerun()

# ── AI Auto-Tag ──
st.markdown("---")
with st.expander("Auto-Tag with AI", expanded=False):
    st.markdown(
        "Let AI suggest categories for your contacts based on their name, email address, "
        "and recent email subjects. You review and approve before anything is saved."
    )

    ai_scope = st.radio(
        "Tag which contacts?",
        ["Untagged only", "All visible", "All selected"],
        horizontal=True,
        key="ai_tag_scope",
    )

    ai_batch_size = st.slider("Contacts per batch", 5, 50, 15, key="ai_batch_size",
                               help="Smaller = more frequent progress updates. Larger = fewer LLM calls but slower feedback.")

    if st.button("Run AI Auto-Tag", type="primary", key="run_ai_tag"):
        # Determine which contacts to tag
        if ai_scope == "Untagged only":
            to_tag = [s for s in filtered if not _DB.parse_categories(s.get("category"))]
        elif ai_scope == "All visible":
            to_tag = filtered
        else:
            to_tag = [s for s in senders if s["selected"]]

        if not to_tag:
            st.warning("No contacts to tag with the selected scope.")
        else:
            # Build contact info with recent subjects for context
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(db.db_path))
            conn.row_factory = _sqlite3.Row

            contact_infos = []
            for s in to_tag:
                subjects = conn.execute(
                    "SELECT subject FROM emails WHERE sender_email = ? ORDER BY date_received DESC LIMIT 3",
                    (s["email"],)
                ).fetchall()
                subj_list = [r["subject"][:50] for r in subjects if r["subject"]]
                contact_infos.append({
                    "id": s["id"],
                    "email": s["email"],
                    "name": s.get("display_name") or "",
                    "subjects": subj_list,
                })
            conn.close()

            st.info(f"Tagging {len(contact_infos)} contacts in batches of {ai_batch_size}. "
                    f"Estimated: {(len(contact_infos) + ai_batch_size - 1) // ai_batch_size} LLM calls.")

            # Build LLM
            from casepulse.llm.api_provider import create_provider
            try:
                llm = create_provider(
                    config.llm_provider,
                    model=config.llm_model,
                    api_key=config.llm_api_key,
                    base_url=config.llm_base_url,
                )
            except Exception as e:
                st.error(f"Could not initialize AI provider: {e}")
                st.stop()

            cat_list = ", ".join(f"{code} ({label})" for code, label in category_labels.items())

            suggestions = {}
            progress = st.progress(0, text="Starting AI auto-tag...")

            # Process in batches
            for batch_start in range(0, len(contact_infos), ai_batch_size):
                batch = contact_infos[batch_start:batch_start + ai_batch_size]
                progress.progress(
                    batch_start / len(contact_infos),
                    text=f"Tagging {batch_start + 1}–{min(batch_start + ai_batch_size, len(contact_infos))} of {len(contact_infos)}..."
                )

                # Build prompt
                contacts_text = ""
                for i, c in enumerate(batch):
                    subj_str = "; ".join(c["subjects"]) if c["subjects"] else "no emails fetched"
                    contacts_text += f"{i+1}. Email: {c['email']}, Name: {c['name']}, Recent subjects: {subj_str}\n"

                prompt = f"""Categorize these contacts. Categories: {cat_list}

Rules: 1-3 categories per contact, confidence 0-100%. Use email domain, name, subjects as clues.
Format EXACTLY (one line each, no extra text):
1. cat1,cat2 | 85%

{contacts_text}"""

                try:
                    response = llm.query(
                        system_prompt="You are a legal case assistant categorizing email contacts. Be precise. Use only the provided category codes.",
                        user_prompt=prompt,
                    )

                    # Parse response
                    for line in response.strip().split("\n"):
                        line = line.strip()
                        if not line or not line[0].isdigit():
                            continue
                        try:
                            # Parse "1. cat1,cat2 | 85%"
                            num_part = line.split(".", 1)
                            if len(num_part) < 2:
                                continue
                            idx = int(num_part[0].strip()) - 1
                            rest = num_part[1].strip()

                            if "|" in rest:
                                cats_str, conf_str = rest.rsplit("|", 1)
                            else:
                                cats_str = rest
                                conf_str = "50%"

                            cats = [c.strip().lower().replace(" ", "_") for c in cats_str.split(",")]
                            cats = [c for c in cats if c in category_labels]
                            confidence = int(conf_str.strip().replace("%", ""))

                            if 0 <= idx < len(batch) and cats:
                                contact = batch[idx]
                                suggestions[contact["id"]] = {
                                    "email": contact["email"],
                                    "name": contact["name"],
                                    "categories": cats,
                                    "confidence": confidence,
                                }
                        except (ValueError, IndexError):
                            continue

                except Exception as e:
                    st.warning(f"AI error on batch: {e}")

            progress.progress(1.0, text=f"Done! {len(suggestions)} contacts tagged.")

            if suggestions:
                st.session_state["ai_suggestions"] = suggestions

    # Show suggestions for review
    if "ai_suggestions" in st.session_state and st.session_state["ai_suggestions"]:
        suggestions = st.session_state["ai_suggestions"]
        st.markdown(f"### Review AI Suggestions ({len(suggestions)} contacts)")
        st.markdown("Check the ones you want to apply, then click **Apply Approved**.")

        if "ai_approved" not in st.session_state:
            st.session_state["ai_approved"] = {sid: True for sid in suggestions}

        # Approve/reject all
        acol1, acol2 = st.columns(2)
        with acol1:
            if st.button("Approve All"):
                st.session_state["ai_approved"] = {sid: True for sid in suggestions}
                st.rerun()
        with acol2:
            if st.button("Reject All"):
                st.session_state["ai_approved"] = {sid: False for sid in suggestions}
                st.rerun()

        for sid, sug in suggestions.items():
            col1, col2, col3, col4 = st.columns([0.5, 3, 3, 1])
            with col1:
                approved = st.checkbox(
                    "a", value=st.session_state["ai_approved"].get(sid, True),
                    key=f"ai_approve_{sid}", label_visibility="collapsed",
                )
                st.session_state["ai_approved"][sid] = approved
            with col2:
                name_str = f"**{sug['name']}** — " if sug["name"] else ""
                st.markdown(f"{name_str}{sug['email']}")
            with col3:
                cat_labels = ", ".join(category_labels.get(c, c) for c in sug["categories"])
                st.markdown(f"{cat_labels}")
            with col4:
                conf = sug["confidence"]
                st.markdown(f"**{conf}%**")

        # Apply button
        approved_count = sum(1 for v in st.session_state["ai_approved"].values() if v)
        if st.button(f"Apply {approved_count} Approved Suggestions", type="primary", key="apply_ai_tags"):
            applied = 0
            for sid, sug in suggestions.items():
                if st.session_state["ai_approved"].get(sid):
                    existing = _DB.parse_categories(
                        next((s.get("category") for s in senders if s["id"] == sid), "")
                    )
                    merged = list(dict.fromkeys(existing + sug["categories"]))
                    db.set_sender_category(sid, merged)
                    applied += 1
            db.log_action("ai_auto_tag", f"Applied AI tags to {applied} contacts")
            st.success(f"Applied tags to {applied} contacts!")
            del st.session_state["ai_suggestions"]
            del st.session_state["ai_approved"]
            st.rerun()

        if st.button("Discard All Suggestions", key="discard_ai_tags"):
            del st.session_state["ai_suggestions"]
            if "ai_approved" in st.session_state:
                del st.session_state["ai_approved"]
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

# Page navigation — use callbacks to avoid session state conflicts
def go_prev():
    st.session_state.sender_page = max(0, st.session_state.sender_page - 1)

def go_next():
    st.session_state.sender_page = min(total_pages - 1, st.session_state.sender_page + 1)

def jump_page():
    st.session_state.sender_page = st.session_state._page_jump_val - 1

if total_pages > 1:
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 3, 1])
    with nav_col1:
        st.button("Prev", disabled=st.session_state.sender_page == 0,
                  key="prev_top", on_click=go_prev)
    with nav_col2:
        st.button("Next", disabled=st.session_state.sender_page >= total_pages - 1,
                  key="next_top", on_click=go_next)
    with nav_col3:
        st.markdown(
            f"**Page {st.session_state.sender_page + 1} of {total_pages}** "
            f"({page_start + 1}–{page_end} of {len(filtered):,}) — "
            f"Selections are saved automatically across pages"
        )
    with nav_col4:
        st.selectbox(
            "Jump to page",
            list(range(1, total_pages + 1)),
            index=st.session_state.sender_page,
            key="_page_jump_val",
            on_change=jump_page,
            label_visibility="collapsed",
        )

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
        tags = ""
        if is_auto:
            tags += " *(auto)*"
        if email_addr.lower() in two_way_senders:
            tags += " **[two-way]**"
        if name:
            st.markdown(f"**{name}**{tags}  \n{email_addr}")
        else:
            st.markdown(f"**{email_addr}**{tags}")

        # Show recent email subjects + dates under every contact
        try:
            conn = sqlite3.connect(str(db.db_path))
            conn.row_factory = sqlite3.Row

            if subject_match_senders is not None and email_addr in subject_match_senders:
                # Subject search active — show matching emails
                search_term = f"%{subject_search}%"
                subj_rows = conn.execute(
                    """SELECT subject, date_received FROM emails
                       WHERE sender_email = ? AND (subject LIKE ? OR body_text LIKE ?)
                       ORDER BY date_received DESC LIMIT 3""",
                    (email_addr, search_term, search_term)
                ).fetchall()
                match_count = subject_match_senders.get(email_addr, 0)
                extra = f" +{match_count - 3} more" if match_count > 3 else ""
                if subj_rows:
                    lines = [f"{r['date_received'][:10]} — {r['subject'][:55]}" for r in subj_rows]
                    st.caption(f"Matching: " + " | ".join(lines) + extra)
            else:
                # No subject search — show most recent emails from this sender
                subj_rows = conn.execute(
                    """SELECT subject, date_received FROM emails
                       WHERE sender_email = ?
                       ORDER BY date_received DESC LIMIT 3""",
                    (email_addr,)
                ).fetchall()
                if subj_rows:
                    lines = [f"{r['date_received'][:10]} — {r['subject'][:55]}" for r in subj_rows]
                    st.caption(" | ".join(lines))

            conn.close()
        except Exception:
            pass

    with col3:
        current_cats = _DB.parse_categories(sender.get("category"))
        selected_cats = st.multiselect(
            "Categories",
            categories,
            default=current_cats,
            key=f"cat_{sender['id']}",
            format_func=lambda x: category_labels.get(x, x),
            label_visibility="collapsed",
            placeholder="Assign categories...",
        )
        if selected_cats != current_cats:
            db.set_sender_category(sender["id"], selected_cats)

    with col4:
        st.caption(f"{freq} emails" if freq else "scanned")

# Bottom pagination
if total_pages > 1:
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        st.button("Prev Page", disabled=st.session_state.sender_page == 0,
                  key="prev_bottom", on_click=go_prev)
    with col2:
        st.markdown(f"**Page {st.session_state.sender_page + 1} of {total_pages}**")
    with col3:
        st.button("Next Page", disabled=st.session_state.sender_page >= total_pages - 1,
                  key="next_bottom", on_click=go_next)

st.divider()

# ── Saved Selection Views ──
st.markdown("### Saved Selection Views")
st.markdown("Save your current selections as a named view. Load them back anytime — useful for different cases or strategies.")

saved = db.get_saved_selections()

# Save current
col1, col2 = st.columns([3, 1])
with col1:
    save_name = st.text_input(
        "Save current selections as",
        placeholder="e.g., Family Case Contacts, Criminal Defence, All Lawyers...",
        key="save_sel_name",
    )
with col2:
    st.markdown("")
    st.markdown("")
    if st.button("Save", disabled=not save_name or selected_count == 0):
        db.save_selection(save_name.strip())
        db.log_action("selection_saved", f"Saved selection '{save_name}' with {selected_count} contacts")
        st.success(f"Saved '{save_name}' with {selected_count} contacts")
        st.rerun()

# Show saved views
if saved:
    for sv in saved:
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 0.5])
        with col1:
            st.markdown(f"**{sv['name']}** — {sv['sender_count']} contacts")
            st.caption(f"Saved: {sv['updated_at'][:16]}")
        with col2:
            if st.button("Load", key=f"load_{sv['id']}", help="Replace current selections with this view"):
                db.load_selection(sv["name"], merge=False)
                db.log_action("selection_loaded", f"Loaded selection '{sv['name']}'")
                st.rerun()
        with col3:
            if st.button("Merge", key=f"merge_{sv['id']}", help="Add this view's contacts to current selections"):
                db.load_selection(sv["name"], merge=True)
                db.log_action("selection_merged", f"Merged selection '{sv['name']}'")
                st.rerun()
        with col4:
            if st.button("Update", key=f"update_{sv['id']}", help="Overwrite this view with current selections"):
                db.save_selection(sv["name"])
                db.log_action("selection_updated", f"Updated selection '{sv['name']}' with {selected_count} contacts")
                st.rerun()
        with col5:
            if st.button("x", key=f"del_{sv['id']}"):
                db.delete_saved_selection(sv["name"])
                st.rerun()
else:
    st.caption("No saved views yet. Select contacts and save them above.")

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
