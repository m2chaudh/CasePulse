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

# ── Check for running fetch job ──
running_jobs = db.get_running_jobs("fetch_emails")

if running_jobs:
    job = running_jobs[0]
    st.info(f"**Fetch in progress** (Job #{job['id']})")
    st.markdown(f"**Status:** {job.get('progress', 'Starting...')}")
    st.caption(f"Started: {job['started_at'][:16]} | Accounts: {job.get('account_email', '')}")

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Cancel Fetch", type="secondary"):
            db.cancel_job(job["id"])
            st.success("Cancel requested. Fetch will stop after the current email.")
            st.rerun()
    with col2:
        if st.button("Refresh Progress"):
            st.rerun()

else:
    # Show recent completed job
    recent = db.get_recent_jobs(limit=1)
    if recent and recent[0]["job_type"] == "fetch_emails" and recent[0]["status"] in ("completed", "cancelled"):
        last = recent[0]
        try:
            import json as _json
            result_data = _json.loads(last.get("result", "{}"))
            st.success(
                f"Last fetch ({last['status']}): "
                f"{result_data.get('fetched', 0):,} emails, "
                f"{result_data.get('skipped', 0):,} skipped, "
                f"{result_data.get('attachments', 0):,} attachments"
            )
        except Exception:
            pass

    # Fetch button
    if st.button("Start Fetching (Background)", type="primary", disabled=not fetch_accounts):
        sender_emails = None
        if not include_no_sender_filter and selected_senders:
            sender_emails = [s["email"] for s in selected_senders]

        keyword_list = [k["keyword"] for k in keywords] if keywords else None

        from casepulse.jobs import start_fetch_job
        job_id = start_fetch_job(
            db, fetch_accounts,
            date_start=str(fetch_start), date_end=str(fetch_end),
            sender_emails=sender_emails, keywords=keyword_list,
        )
        st.success(f"Fetch started in background (Job #{job_id}). You can navigate to other pages — progress shows in the sidebar.")
        st.rerun()

st.divider()

# ── Current Data Summary ──
st.markdown("### Current Data")
stats = db.get_stats()

# Per-account breakdown
import sqlite3 as _sql
_conn = _sql.connect(str(db.db_path))
_conn.row_factory = _sql.Row
_per_account = _conn.execute("""
    SELECT a.email, a.provider, COUNT(e.id) as email_count,
           COUNT(DISTINCT e.sender_email) as sender_count
    FROM accounts a LEFT JOIN emails e ON a.id = e.account_id
    GROUP BY a.id ORDER BY email_count DESC
""").fetchall()
_conn.close()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Emails", f"{stats['total_emails']:,}")
with col2:
    st.metric("Total Attachments", f"{stats['total_attachments']:,}")
with col3:
    st.metric("Duplicate Attachments", f"{stats['duplicate_attachments']:,}")
with col4:
    if stats.get("latest_email"):
        earliest = stats['earliest_email'][:10] if stats.get('earliest_email') else '?'
        st.metric("Date Range", f"{earliest} to {stats['latest_email'][:10]}")
    else:
        st.metric("Date Range", "No data")

# Per-account breakdown
if _per_account:
    st.markdown("**Per account:**")
    for r in _per_account:
        provider = "Microsoft" if r["provider"] == "microsoft" else "Gmail"
        st.caption(f"  {provider}: {r['email']} — {r['email_count']:,} emails from {r['sender_count']:,} senders")

# Per-contact breakdown
with st.expander("Emails by Contact"):
    _conn_contacts = _sql.connect(str(db.db_path))
    _conn_contacts.row_factory = _sql.Row
    _contact_counts = _conn_contacts.execute("""
        SELECT e.sender_email, e.sender_name, COUNT(*) as cnt,
               MIN(e.date_received) as first_email, MAX(e.date_received) as last_email
        FROM emails e
        GROUP BY e.sender_email
        ORDER BY cnt DESC
        LIMIT 200
    """).fetchall()
    _conn_contacts.close()

    if _contact_counts:
        search_contacts = st.text_input("Filter contacts", placeholder="Search...", key="contact_breakdown_search")
        filtered_contacts = _contact_counts
        if search_contacts:
            search_lower = search_contacts.lower()
            filtered_contacts = [c for c in _contact_counts
                                  if search_lower in c["sender_email"].lower()
                                  or search_lower in (c["sender_name"] or "").lower()]

        st.caption(f"Showing {len(filtered_contacts)} contacts (top 200 by volume)")
        for c in filtered_contacts:
            name = f"{c['sender_name']} — " if c['sender_name'] else ""
            first = c['first_email'][:10] if c['first_email'] else '?'
            last = c['last_email'][:10] if c['last_email'] else '?'
            st.caption(f"  {name}{c['sender_email']} — **{c['cnt']:,}** emails ({first} to {last})")

# Sync history
sync_history = db.get_sync_history(limit=10)
if sync_history:
    st.markdown("### Sync History")
    all_accounts = db.get_accounts()
    acc_map = {a["id"]: a["email"] for a in all_accounts}
    for sync in sync_history:
        acc_email = acc_map.get(sync["account_id"], "?")
        status_icon = "+" if sync["status"] == "completed" else "..." if sync["status"] == "running" else "x"
        st.markdown(
            f"[{status_icon}] **{acc_email}** — {sync['started_at'][:16]} — "
            f"{sync['emails_fetched']:,} emails, {sync['attachments_downloaded']:,} attachments "
            f"({sync['status']})"
        )

# ── Cleanup Tools ──
st.divider()
with st.expander("Data Management"):
    st.markdown("### Delete Emails by Account")
    st.markdown("Remove all fetched emails from a specific account. Contacts and selections are NOT affected.")

    all_accounts = db.get_accounts()
    if all_accounts:
        for acc in all_accounts:
            _conn2 = _sql.connect(str(db.db_path))
            _conn2.row_factory = _sql.Row
            count = _conn2.execute("SELECT COUNT(*) as c FROM emails WHERE account_id = ?", (acc["id"],)).fetchone()["c"]
            _conn2.close()

            col1, col2 = st.columns([3, 1])
            with col1:
                provider = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
                st.markdown(f"**{provider}: {acc['email']}** — {count:,} emails")
            with col2:
                if count > 0:
                    if st.button(f"Delete {count:,} emails", key=f"del_emails_{acc['id']}"):
                        st.session_state[f"confirm_del_{acc['id']}"] = True

            if st.session_state.get(f"confirm_del_{acc['id']}"):
                confirm = st.checkbox(
                    f"I confirm: delete all {count:,} emails from {acc['email']}",
                    key=f"confirm_check_{acc['id']}",
                )
                if confirm:
                    if st.button(f"Confirm Delete", key=f"confirm_btn_{acc['id']}", type="primary"):
                        _conn3 = _sql.connect(str(db.db_path))
                        # Delete attachments first
                        _conn3.execute("""DELETE FROM attachments WHERE email_id IN
                                         (SELECT id FROM emails WHERE account_id = ?)""", (acc["id"],))
                        _conn3.execute("DELETE FROM emails WHERE account_id = ?", (acc["id"],))
                        _conn3.execute("DELETE FROM sync_log WHERE account_id = ?", (acc["id"],))
                        _conn3.execute("UPDATE accounts SET last_synced = NULL WHERE id = ?", (acc["id"],))
                        _conn3.commit()
                        _conn3.close()
                        db.log_action("emails_deleted", f"Deleted {count} emails from {acc['email']}")
                        st.session_state.pop(f"confirm_del_{acc['id']}", None)
                        st.success(f"Deleted {count:,} emails from {acc['email']}")
                        st.rerun()

    st.divider()

    st.markdown("### Delete Emails by Contact")
    st.markdown("Remove emails from specific senders. Useful for cleaning up irrelevant contacts.")

    _conn_del = _sql.connect(str(db.db_path))
    _conn_del.row_factory = _sql.Row
    _sender_counts = _conn_del.execute("""
        SELECT sender_email, sender_name, COUNT(*) as cnt
        FROM emails GROUP BY sender_email ORDER BY cnt DESC LIMIT 100
    """).fetchall()
    _conn_del.close()

    if _sender_counts:
        del_search = st.text_input("Search contacts to delete", placeholder="Search...", key="del_contact_search")
        del_filtered = _sender_counts
        if del_search:
            dl = del_search.lower()
            del_filtered = [s for s in _sender_counts
                            if dl in s["sender_email"].lower() or dl in (s["sender_name"] or "").lower()]

        del_options = {s["sender_email"]: f"{s['sender_name'] or ''} ({s['sender_email']}) — {s['cnt']:,} emails"
                       for s in del_filtered[:50]}

        contacts_to_delete = st.multiselect(
            "Select contacts to delete emails from",
            list(del_options.keys()),
            format_func=lambda x: del_options.get(x, x),
            key="del_contacts_select",
        )

        if contacts_to_delete:
            total_to_delete = sum(s["cnt"] for s in del_filtered if s["sender_email"] in contacts_to_delete)
            confirm_del_contacts = st.checkbox(
                f"Confirm: delete {total_to_delete:,} emails from {len(contacts_to_delete)} contacts",
                key="confirm_del_contacts",
            )
            if confirm_del_contacts:
                if st.button(f"Delete {total_to_delete:,} emails", type="primary", key="del_contacts_btn"):
                    _conn_dc = _sql.connect(str(db.db_path))
                    deleted = 0
                    for email_addr in contacts_to_delete:
                        _conn_dc.execute("""DELETE FROM attachments WHERE email_id IN
                                            (SELECT id FROM emails WHERE sender_email = ?)""", (email_addr,))
                        cur = _conn_dc.execute("DELETE FROM emails WHERE sender_email = ?", (email_addr,))
                        deleted += cur.rowcount
                    _conn_dc.commit()
                    _conn_dc.close()
                    db.log_action("emails_deleted_by_contact",
                                  f"Deleted {deleted} emails from {len(contacts_to_delete)} contacts: {', '.join(contacts_to_delete[:5])}")
                    st.success(f"Deleted {deleted:,} emails from {len(contacts_to_delete)} contacts")
                    st.rerun()

    st.divider()

    st.markdown("### Clear All Email Data")
    st.markdown("Delete ALL fetched emails, attachments, and sync history across all accounts. Contacts and selections are preserved.")
    clear_all = st.checkbox("I want to clear all email data and start fresh", key="clear_all_emails")
    if clear_all:
        total = stats["total_emails"]
        if st.button(f"Delete ALL {total:,} emails", type="primary", key="clear_all_btn"):
            _conn4 = _sql.connect(str(db.db_path))
            _conn4.execute("DELETE FROM attachments")
            _conn4.execute("DELETE FROM emails")
            _conn4.execute("DELETE FROM sync_log")
            _conn4.execute("UPDATE accounts SET last_synced = NULL")
            _conn4.commit()
            _conn4.close()
            db.log_action("all_emails_deleted", f"Cleared all {total} emails")
            st.success(f"Deleted all {total:,} emails. You can re-fetch anytime.")
            st.rerun()
