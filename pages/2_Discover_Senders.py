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
        st.session_state["scan_complete"] = True

st.divider()

# ── Sender Selection ──
senders = db.get_senders()

if senders:
    st.markdown("### Select Relevant Contacts")
    st.markdown("Check the contacts relevant to your case. You can also assign categories.")

    # Category options for legal case
    categories = [
        "other", "my_lawyer", "opposing_lawyer", "ex_spouse",
        "police", "cas_worker", "therapist", "court", "mediator",
        "financial", "family", "witness",
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
    }

    # Filter controls
    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("Search contacts", placeholder="Filter by name or email...", key="sender_search")
    with col2:
        show_selected = st.checkbox("Show selected only", key="show_selected")

    # Filter senders
    filtered = senders
    if search:
        search_lower = search.lower()
        filtered = [s for s in filtered if search_lower in s["email"].lower() or
                    search_lower in (s.get("display_name") or "").lower()]
    if show_selected:
        filtered = [s for s in filtered if s["selected"]]

    # Select/Deselect all
    col1, col2, col3 = st.columns([1, 1, 3])
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

    # Count selected
    selected_count = sum(1 for s in senders if s["selected"])
    st.caption(f"{selected_count} contacts selected out of {len(senders)} total")

    # Display senders as interactive table
    for sender in filtered:
        col1, col2, col3, col4 = st.columns([0.5, 3, 2, 2])

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
            if name:
                st.markdown(f"**{name}**  \n{sender['email']}")
            else:
                st.markdown(f"**{sender['email']}**")

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
            st.caption(f"Category: {category_labels.get(sender.get('category', 'other'), 'Other')}")

else:
    st.info("No contacts found yet. Click **Scan for Contacts** above to discover senders in your mailboxes.")

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
    st.markdown("")  # Spacer
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
