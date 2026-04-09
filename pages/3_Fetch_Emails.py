"""Fetch Emails page — Download emails matching selected senders and keywords."""
import streamlit as st
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Fetch Emails", page_icon="CP", layout="wide")

st.markdown("## Fetch Emails")
st.markdown("Download emails from your accounts based on selected senders, keywords, and date range.")


from components.page_init import init_page
db, config = init_page()

# ── Pre-flight checks ──
accounts = db.get_accounts()
if not accounts:
    st.warning("No accounts connected. Go to **Accounts** first.")
    st.stop()

selected_senders = db.get_senders(selected_only=True)
keywords = db.get_keywords(active_only=True)

# ── Summary ──
st.markdown("### Fetch Configuration")

col1, col2 = st.columns(2)
with col1:
    fetch_start = st.date_input(
        "From date",
        value=date.fromisoformat(config.date_start),
        key="fetch_start",
    )
with col2:
    fetch_end = st.date_input(
        "To date",
        value=date.fromisoformat(config.date_end),
        key="fetch_end",
    )

# Show selected senders
st.markdown(f"**Selected senders:** {len(selected_senders)}")
if selected_senders:
    with st.expander("View selected senders"):
        for s in selected_senders:
            name = s.get("display_name") or ""
            cat = s.get("category", "other")
            label = f"{s['email']}"
            if name:
                label = f"{name} ({s['email']})"
            if cat != "other":
                label += f" [{cat}]"
            st.markdown(f"- {label}")
else:
    st.info("No senders selected. Go to **Discover Senders** to select contacts, or fetch ALL emails (not recommended for large mailboxes).")

# Show keywords
st.markdown(f"**Active keywords:** {len(keywords)}")
if keywords:
    st.markdown(", ".join(f"`{k['keyword']}`" for k in keywords))
else:
    st.caption("No keyword filter — all emails from selected senders will be fetched.")

# Account selection for fetch
st.markdown("### Accounts to Fetch From")
fetch_accounts = []
for acc in accounts:
    provider_label = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
    if st.checkbox(f"{provider_label}: {acc['email']}", value=True, key=f"fetch_{acc['id']}"):
        fetch_accounts.append(acc)

st.divider()

# ── Fetch Options ──
include_no_sender_filter = st.checkbox(
    "Include ALL emails (ignore sender filter)",
    value=not bool(selected_senders),
    help="Fetch every email in the date range, regardless of sender",
)

# ── Fetch Button ──
col1, col2 = st.columns([1, 1])
with col1:
    fetch_clicked = st.button("Start Fetching", type="primary", disabled=not fetch_accounts)
with col2:
    if st.button("Stop Fetch"):
        st.session_state["fetch_cancel"] = True

if fetch_clicked:
    st.session_state["fetch_cancel"] = False
    sender_emails = None
    if not include_no_sender_filter and selected_senders:
        sender_emails = [s["email"] for s in selected_senders]

    keyword_list = [k["keyword"] for k in keywords] if keywords else None

    total_results = {
        "emails_fetched": 0,
        "attachments_downloaded": 0,
        "duplicates_skipped": 0,
        "errors": [],
    }

    cancelled = False

    with st.status("Fetching emails...", expanded=True) as status:
        for acc in fetch_accounts:
            if st.session_state.get("fetch_cancel"):
                st.write("Fetch cancelled by user.")
                cancelled = True
                break

            st.write(f"--- Fetching from {acc['email']} ---")

            try:
                if acc["provider"] == "microsoft":
                    from casepulse.auth.microsoft import MicrosoftAuth
                    auth = MicrosoftAuth(client_id=acc.get("client_id", ""), account_email=acc["email"])
                    token = auth.get_access_token()
                    if not token:
                        st.warning(f"Token expired for {acc['email']}. Please re-authenticate.")
                        continue

                    from casepulse.email_engine.microsoft_fetcher import MicrosoftFetcher
                    fetcher = MicrosoftFetcher(token, acc["id"], db)
                    result = fetcher.fetch_emails(
                        str(fetch_start), str(fetch_end),
                        sender_emails=sender_emails,
                        keywords=keyword_list,
                        progress_cb=lambda msg: st.write(msg),
                    )

                elif acc["provider"] == "google":
                    from casepulse.auth.google_auth import GoogleAuth
                    creds_file = acc.get("token_file", "")
                    auth = GoogleAuth(credentials_file=creds_file, account_email=acc["email"])
                    service = auth.get_service()
                    if not service:
                        st.warning(f"Token expired for {acc['email']}. Please re-authenticate.")
                        continue

                    from casepulse.email_engine.gmail_fetcher import GmailFetcher
                    fetcher = GmailFetcher(service, acc["id"], db)
                    result = fetcher.fetch_emails(
                        str(fetch_start), str(fetch_end),
                        sender_emails=sender_emails,
                        keywords=keyword_list,
                        progress_cb=lambda msg: st.write(msg),
                    )

                total_results["emails_fetched"] += result["emails_fetched"]
                total_results["attachments_downloaded"] += result["attachments_downloaded"]
                total_results["duplicates_skipped"] += result["duplicates_skipped"]
                total_results["errors"].extend(result.get("errors", []))

                st.write(
                    f"Done: {result['emails_fetched']} emails, "
                    f"{result['attachments_downloaded']} attachments, "
                    f"{result['duplicates_skipped']} duplicates skipped"
                )

            except Exception as e:
                st.error(f"Error fetching from {acc['email']}: {str(e)}")
                total_results["errors"].append(str(e))

        if cancelled:
            status.update(label=f"Fetch stopped — {total_results['emails_fetched']} emails saved from completed accounts", state="complete")
        else:
            status.update(label="Fetch complete!", state="complete")

    # Summary
    st.markdown("### Fetch Results")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Emails Fetched", total_results["emails_fetched"])
    with col2:
        st.metric("Attachments Downloaded", total_results["attachments_downloaded"])
    with col3:
        st.metric("Duplicates Skipped", total_results["duplicates_skipped"])

    if total_results["errors"]:
        with st.expander(f"Errors ({len(total_results['errors'])})"):
            for err in total_results["errors"]:
                st.error(err)

    st.success("Emails fetched! Go to **Timeline** to view them or **Ask** to query with AI.")

st.divider()

# ── Current Data Summary ──
st.markdown("### Current Data")
stats = db.get_stats()
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Emails", f"{stats['total_emails']:,}")
with col2:
    st.metric("Total Attachments", f"{stats['total_attachments']:,}")
with col3:
    st.metric("Duplicate Attachments", f"{stats['duplicate_attachments']:,}")
with col4:
    if stats["earliest_email"]:
        st.metric("Date Range", f"{stats['earliest_email'][:10]} to {stats['latest_email'][:10]}")
    else:
        st.metric("Date Range", "No data")

# Sync history
sync_history = db.get_sync_history(limit=10)
if sync_history:
    st.markdown("### Sync History")
    for sync in sync_history:
        acc = db.get_accounts()
        acc_email = ""
        for a in acc:
            if a["id"] == sync["account_id"]:
                acc_email = a["email"]
                break
        status_icon = "+" if sync["status"] == "completed" else "x"
        st.markdown(
            f"[{status_icon}] **{acc_email}** — {sync['started_at']} — "
            f"{sync['emails_fetched']} emails, {sync['attachments_downloaded']} attachments "
            f"({sync['status']})"
        )
