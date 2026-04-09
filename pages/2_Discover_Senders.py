"""Discover Senders page — Scan mailboxes and select relevant contacts."""
import streamlit as st
import sys
import json as _json
import sqlite3
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
                db.upsert_sender(c["email"], c.get("name", ""), account_id=acc_info["id"])

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
    "criminal_lawyer": "Criminal Lawyer",
    "daycare": "Daycare",
    "disclosure": "Disclosure",
    "docusign": "DocuSign",
    "employer": "Employer",
    "evidence": "Evidence",
    "ex_spouse": "Ex-Spouse",
    "expenses": "Expenses",
    "family": "Family",
    "family_law_assistant": "Family Law Assistant",
    "family_lawyer": "Family Law Lawyer",
    "financial": "Financial",
    "insurance": "Insurance",
    "mediation": "Mediation",
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

    # Email frequency per sender
    rows = conn.execute(
        "SELECT sender_email, COUNT(*) as cnt FROM emails GROUP BY sender_email"
    ).fetchall()

    # Build sender-to-account mapping from scan data
    if selected_account_id:
        senders_in_account = db.get_senders_for_account(selected_account_id)
    import json as _json

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

# ── AI Tools ──
st.markdown("---")
st.markdown("### AI Tools")

ai_tab1, ai_tab2 = st.tabs(["Auto-Tag", "AI Assistant"])

# ── Tab 1: Auto-Tag ──
with ai_tab1:
    st.markdown("AI suggests categories based on name, email, and recent subjects. You review before applying.")

    ai_scope = st.radio(
        "Tag which contacts?",
        ["Untagged only (skip already tagged)", "All visible (re-tag everything shown)", "All selected"],
        horizontal=True,
        key="ai_tag_scope",
    )

    ai_batch_size = st.slider("Contacts per batch", 5, 50, 15, key="ai_batch_size",
                               help="Smaller = more frequent progress. Larger = fewer LLM calls.")

    if st.button("Run AI Auto-Tag", type="primary", key="run_ai_tag"):
        # Determine scope
        if "Untagged" in ai_scope:
            to_tag = [s for s in filtered
                      if not _DB.parse_categories(s.get("category"))
                      and s.get("category", "other") in ("other", "", None)]
        elif "All visible" in ai_scope:
            to_tag = filtered
        else:
            to_tag = [s for s in senders if s["selected"]
                      and not _DB.parse_categories(s.get("category"))]

        already_tagged = len(filtered) - len(to_tag) if "Untagged" in ai_scope else 0

        if not to_tag:
            st.warning("No contacts to tag. All visible contacts already have categories assigned.")
        else:
            if already_tagged > 0:
                st.info(f"Skipping {already_tagged} already-tagged contacts. Tagging {len(to_tag)} untagged contacts.")

            # Build contact info
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

            n_batches = (len(contact_infos) + ai_batch_size - 1) // ai_batch_size
            st.info(f"Processing {len(contact_infos)} contacts in {n_batches} batches...")

            from casepulse.llm.api_provider import create_provider
            try:
                llm = create_provider(
                    config.llm_provider, model=config.llm_model,
                    api_key=config.llm_api_key, base_url=config.llm_base_url,
                )
            except Exception as e:
                st.error(f"Could not initialize AI: {e}")
                st.stop()

            cat_list = ", ".join(f"{code} ({label})" for code, label in category_labels.items())
            suggestions = {}
            progress = st.progress(0, text="Starting...")

            for batch_start in range(0, len(contact_infos), ai_batch_size):
                batch = contact_infos[batch_start:batch_start + ai_batch_size]
                batch_num = batch_start // ai_batch_size + 1
                progress.progress(
                    batch_start / len(contact_infos),
                    text=f"Batch {batch_num}/{n_batches} — {len(suggestions)} tagged so far..."
                )

                contacts_text = ""
                for i, c in enumerate(batch):
                    subj_str = "; ".join(c["subjects"]) if c["subjects"] else "no emails"
                    contacts_text += f"{i+1}. {c['email']}, Name: {c['name']}, Subjects: {subj_str}\n"

                prompt = f"""Categorize for a family law and criminal defence case. Categories: {cat_list}

1-3 categories per contact, confidence 0-100%. Format EXACTLY:
1. cat1,cat2 | 85%

{contacts_text}"""

                try:
                    response = llm.query(
                        system_prompt="You categorize email contacts for legal cases. Use only provided category codes. Be precise.",
                        user_prompt=prompt,
                    )

                    for line in response.strip().split("\n"):
                        line = line.strip()
                        if not line or not line[0].isdigit():
                            continue
                        try:
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
                    st.warning(f"Batch {batch_num} error: {e}")

            progress.progress(1.0, text=f"Done! {len(suggestions)} contacts tagged.")
            if suggestions:
                st.session_state["ai_suggestions"] = suggestions
                st.session_state.pop("ai_approved", None)

    # ── Review suggestions ──
    if "ai_suggestions" in st.session_state and st.session_state["ai_suggestions"]:
        suggestions = st.session_state["ai_suggestions"]
        st.markdown(f"### Review AI Suggestions ({len(suggestions)} contacts)")

        if "ai_approved" not in st.session_state:
            st.session_state["ai_approved"] = {sid: True for sid in suggestions}

        # Bulk review actions
        st.markdown("**Quick review:**")
        rcol1, rcol2, rcol3, rcol4, rcol5 = st.columns(5)
        with rcol1:
            if st.button("Approve All", key="ai_approve_all"):
                st.session_state["ai_approved"] = {sid: True for sid in suggestions}
                st.rerun()
        with rcol2:
            if st.button("Reject All", key="ai_reject_all"):
                st.session_state["ai_approved"] = {sid: False for sid in suggestions}
                st.rerun()
        with rcol3:
            conf_threshold = st.number_input("Min confidence %", 0, 100, 70, key="ai_conf_thresh")
        with rcol4:
            if st.button(f"Approve >= {conf_threshold}%", key="ai_approve_conf"):
                for sid, sug in suggestions.items():
                    st.session_state["ai_approved"][sid] = sug["confidence"] >= conf_threshold
                st.rerun()
        with rcol5:
            # Filter by category
            ai_cat_filter = st.selectbox(
                "Approve category",
                ["—"] + list(category_labels.keys()),
                format_func=lambda x: category_labels.get(x, "—"),
                key="ai_cat_approve",
            )
            if ai_cat_filter != "—":
                if st.button(f"Approve all {category_labels[ai_cat_filter]}", key="ai_approve_cat"):
                    for sid, sug in suggestions.items():
                        if ai_cat_filter in sug["categories"]:
                            st.session_state["ai_approved"][sid] = True
                    st.rerun()

        # Stats
        approved_count = sum(1 for v in st.session_state["ai_approved"].values() if v)
        rejected_count = len(suggestions) - approved_count
        avg_conf = sum(s["confidence"] for s in suggestions.values()) / len(suggestions) if suggestions else 0
        st.caption(f"Approved: {approved_count} | Rejected: {rejected_count} | Avg confidence: {avg_conf:.0f}%")

        # Initialize manual overrides storage
        if "ai_manual_cats" not in st.session_state:
            st.session_state["ai_manual_cats"] = {}

        # List suggestions
        for sid, sug in suggestions.items():
            is_approved = st.session_state["ai_approved"].get(sid, True)

            col1, col2, col3, col4 = st.columns([0.5, 3, 3, 1])
            with col1:
                approved = st.checkbox(
                    "a", value=is_approved,
                    key=f"ai_approve_{sid}", label_visibility="collapsed",
                )
                st.session_state["ai_approved"][sid] = approved
            with col2:
                name_str = f"**{sug['name']}** — " if sug["name"] else ""
                st.markdown(f"{name_str}{sug['email']}")
            with col3:
                if approved:
                    # Show AI suggestion
                    cat_labels_str = ", ".join(category_labels.get(c, c) for c in sug["categories"])
                    st.markdown(cat_labels_str)
                else:
                    # Show manual category picker when rejected
                    manual = st.multiselect(
                        "Assign manually",
                        categories,
                        default=st.session_state["ai_manual_cats"].get(sid, []),
                        key=f"ai_manual_{sid}",
                        format_func=lambda x: category_labels.get(x, x),
                        placeholder="Pick categories...",
                        label_visibility="collapsed",
                    )
                    st.session_state["ai_manual_cats"][sid] = manual
            with col4:
                if approved:
                    st.markdown(f"**{sug['confidence']}%**")
                else:
                    st.caption("manual")

        # Apply / discard
        manual_count = sum(1 for sid in suggestions
                          if not st.session_state["ai_approved"].get(sid)
                          and st.session_state["ai_manual_cats"].get(sid))

        col1, col2 = st.columns(2)
        with col1:
            total_apply = approved_count + manual_count
            if st.button(f"Apply {total_apply} ({approved_count} AI + {manual_count} manual)",
                         type="primary", key="apply_ai_tags"):
                applied = 0
                for sid, sug in suggestions.items():
                    if st.session_state["ai_approved"].get(sid):
                        # Apply AI suggestion
                        existing = _DB.parse_categories(
                            next((s.get("category") for s in senders if s["id"] == sid), "")
                        )
                        merged = list(dict.fromkeys(existing + sug["categories"]))
                        db.set_sender_category(sid, merged)
                        applied += 1
                    elif st.session_state["ai_manual_cats"].get(sid):
                        # Apply manual override
                        existing = _DB.parse_categories(
                            next((s.get("category") for s in senders if s["id"] == sid), "")
                        )
                        merged = list(dict.fromkeys(existing + st.session_state["ai_manual_cats"][sid]))
                        db.set_sender_category(sid, merged)
                        applied += 1
                db.log_action("ai_auto_tag", f"Applied tags to {applied} contacts ({approved_count} AI, {manual_count} manual)")
                st.success(f"Applied tags to {applied} contacts!")
                del st.session_state["ai_suggestions"]
                st.session_state.pop("ai_approved", None)
                st.session_state.pop("ai_manual_cats", None)
                st.rerun()
        with col2:
            if st.button("Discard All Suggestions", key="discard_ai_tags"):
                del st.session_state["ai_suggestions"]
                st.session_state.pop("ai_approved", None)
                st.session_state.pop("ai_manual_cats", None)
                st.rerun()

# ── Tab 2: AI Assistant — executes actions directly ──
with ai_tab2:
    st.markdown(
        "Tell AI what to do — it will **execute the actions directly**. Examples:\n"
        "- *Tag all @goldfamilylaw.ca as My Lawyer*\n"
        "- *Tag all Manisha contacts as Ex-Spouse*\n"
        "- *Canada Life is benefits*\n"
        "- *Select all police contacts*\n"
        "- *Deselect all noreply addresses*"
    )

    if "ai_chat_history" not in st.session_state:
        st.session_state["ai_chat_history"] = []

    # Display chat history
    for msg in st.session_state["ai_chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if ai_prompt := st.chat_input("Tell AI what to do with your contacts...", key="ai_discover_chat"):
        st.session_state["ai_chat_history"].append({"role": "user", "content": ai_prompt})
        with st.chat_message("user"):
            st.markdown(ai_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Processing..."):
                try:
                    from casepulse.llm.api_provider import create_provider
                    llm = create_provider(
                        config.llm_provider, model=config.llm_model,
                        api_key=config.llm_api_key, base_url=config.llm_base_url,
                    )

                    import sqlite3 as _sqlite3
                    conn = _sqlite3.connect(str(db.db_path))
                    conn.row_factory = _sqlite3.Row

                    # Get all contacts for context
                    all_senders_data = conn.execute(
                        "SELECT id, email, display_name, category FROM senders"
                    ).fetchall()
                    all_senders_list = [dict(r) for r in all_senders_data]

                    # Top domains
                    domains = conn.execute(
                        "SELECT SUBSTR(email, INSTR(email, '@')+1) as domain, COUNT(*) as cnt FROM senders GROUP BY domain ORDER BY cnt DESC LIMIT 30"
                    ).fetchall()
                    domain_text = ", ".join(f"{r['domain']}({r['cnt']})" for r in domains)
                    conn.close()

                    cat_codes = list(category_labels.keys())
                    cat_list = ", ".join(f"{code}" for code in cat_codes)

                    system_prompt = f"""You are a contact tagging engine. You parse user instructions and output ONLY a JSON array of actions.

Available category codes: {cat_list}
Top email domains: {domain_text}

Output format — ONLY valid JSON, no other text:
[
  {{"action": "tag", "match": "search_term", "match_type": "domain|name|email", "category": "category_code"}},
  {{"action": "tag", "match": "search_term", "match_type": "domain|name|email", "category": "category_code"}},
  {{"action": "select", "match": "search_term", "match_type": "domain|name|email"}},
  {{"action": "deselect", "match": "search_term", "match_type": "domain|name|email"}}
]

match_type:
- "domain" = match the email domain (e.g., "goldfamilylaw.ca")
- "name" = match display name or email contains this text (e.g., "manisha", "nirlep")
- "email" = exact email match

Examples:
User: "Tag all @goldfamilylaw.ca as My Lawyer"
Output: [{{"action":"tag","match":"goldfamilylaw.ca","match_type":"domain","category":"my_lawyer"}}]

User: "Manisha is ex wife, nirlep is her lawyer"
Output: [{{"action":"tag","match":"manisha","match_type":"name","category":"ex_spouse"}},{{"action":"tag","match":"nirlep","match_type":"name","category":"opposing_lawyer"}}]

User: "Canada Life is benefits, Michelle Abel is my lawyer"
Output: [{{"action":"tag","match":"canadalife","match_type":"name","category":"benefits"}},{{"action":"tag","match":"michelle abel","match_type":"name","category":"my_lawyer"}}]

ONLY output the JSON array. No explanations."""

                    response = llm.query(
                        system_prompt=system_prompt,
                        user_prompt=ai_prompt,
                    )

                    # Parse JSON actions from response
                    import json as _json
                    # Extract JSON from response (might have markdown backticks)
                    json_text = response.strip()
                    if "```" in json_text:
                        json_text = json_text.split("```")[1]
                        if json_text.startswith("json"):
                            json_text = json_text[4:]
                        json_text = json_text.strip()

                    actions = _json.loads(json_text)

                    if not isinstance(actions, list):
                        actions = [actions]

                    # Execute actions
                    results = []
                    total_affected = 0

                    for act in actions:
                        action_type = act.get("action", "")
                        match_term = act.get("match", "").lower()
                        match_type = act.get("match_type", "name")
                        category = act.get("category", "")

                        if not match_term:
                            continue

                        # Find matching contacts
                        matched = []
                        for s in all_senders_list:
                            email_lower = s["email"].lower()
                            name_lower = (s.get("display_name") or "").lower()

                            if match_type == "domain":
                                if email_lower.endswith(f"@{match_term}") or match_term in email_lower.split("@")[-1]:
                                    matched.append(s)
                            elif match_type == "email":
                                if email_lower == match_term:
                                    matched.append(s)
                            else:  # name
                                if match_term in name_lower or match_term in email_lower:
                                    matched.append(s)

                        if not matched:
                            results.append(f"No contacts found matching '{match_term}'")
                            continue

                        if action_type == "tag" and category:
                            cat_label = category_labels.get(category, category)
                            for s in matched:
                                existing = _DB.parse_categories(s.get("category"))
                                if category not in existing:
                                    merged = list(dict.fromkeys(existing + [category]))
                                    db.set_sender_category(s["id"], merged)
                            results.append(f"Tagged **{len(matched)}** contacts matching '{match_term}' as **{cat_label}**")
                            total_affected += len(matched)

                        elif action_type == "select":
                            for s in matched:
                                db.set_sender_selected(s["id"], True)
                            results.append(f"Selected **{len(matched)}** contacts matching '{match_term}'")
                            total_affected += len(matched)

                        elif action_type == "deselect":
                            for s in matched:
                                db.set_sender_selected(s["id"], False)
                            results.append(f"Deselected **{len(matched)}** contacts matching '{match_term}'")
                            total_affected += len(matched)

                    # Show results
                    if results:
                        result_text = "**Done!** Here's what I did:\n\n" + "\n".join(f"- {r}" for r in results)
                        result_text += f"\n\n**Total: {total_affected} contacts updated.**"
                        st.markdown(result_text)
                        st.session_state["ai_chat_history"].append({"role": "assistant", "content": result_text})
                        db.log_action("ai_assistant", f"Executed {len(actions)} actions on {total_affected} contacts")
                    else:
                        st.warning("Could not parse any actions from AI response.")
                        st.caption(f"Raw response: {response[:500]}")
                        st.session_state["ai_chat_history"].append({"role": "assistant", "content": "Could not parse actions."})

                except _json.JSONDecodeError:
                    # LLM didn't return valid JSON — fall back to showing raw response
                    st.markdown(response)
                    st.caption("(AI responded with text instead of actions — try rephrasing your request)")
                    st.session_state["ai_chat_history"].append({"role": "assistant", "content": response})

                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state["ai_chat_history"].append({"role": "assistant", "content": error_msg})

    if st.session_state["ai_chat_history"] and st.button("Clear Chat", key="clear_ai_discover_chat"):
        st.session_state["ai_chat_history"] = []
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
# Pre-fetch recent subjects for all contacts on this page in one query
_page_emails = [s["email"] for s in page_items]
_page_subjects = {}
try:
    _list_conn = sqlite3.connect(str(db.db_path))
    _list_conn.row_factory = sqlite3.Row
    for _pe in _page_emails:
        if subject_match_senders is not None and _pe in subject_match_senders:
            _search_term = f"%{subject_search}%"
            _rows = _list_conn.execute(
                """SELECT subject, date_received FROM emails
                   WHERE sender_email = ? AND (subject LIKE ? OR body_text LIKE ?)
                   ORDER BY date_received DESC LIMIT 3""",
                (_pe, _search_term, _search_term)
            ).fetchall()
            _match_count = subject_match_senders.get(_pe, 0)
            _page_subjects[_pe] = {"rows": _rows, "match_count": _match_count, "is_search": True}
        else:
            _rows = _list_conn.execute(
                """SELECT subject, date_received FROM emails
                   WHERE sender_email = ?
                   ORDER BY date_received DESC LIMIT 3""",
                (_pe,)
            ).fetchall()
            _page_subjects[_pe] = {"rows": _rows, "match_count": 0, "is_search": False}
    _list_conn.close()
except Exception:
    pass

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

        # Show recent email subjects + dates (pre-fetched above)
        subj_data = _page_subjects.get(email_addr)
        if subj_data and subj_data["rows"]:
            if subj_data["is_search"]:
                extra = f" +{subj_data['match_count'] - 3} more" if subj_data["match_count"] > 3 else ""
                lines = [f"{r['date_received'][:10]} — {r['subject'][:55]}" for r in subj_data["rows"]]
                st.caption(f"Matching: " + " | ".join(lines) + extra)
            else:
                lines = [f"{r['date_received'][:10]} — {r['subject'][:55]}" for r in subj_data["rows"]]
                st.caption(" | ".join(lines))

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
