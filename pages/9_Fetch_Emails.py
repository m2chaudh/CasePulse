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
from casepulse.case_theory.ui import page_help
db, config = init_page()
page_help.render("fetch_emails")

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
        format="YYYY-MM-DD",
    )
with col2:
    fetch_end = st.date_input(
        "To date",
        value=date.fromisoformat(config.date_end),
        key="fetch_end",
        format="YYYY-MM-DD",
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

    # ── Browse & Delete by Contact ──
    st.markdown("### Browse & Delete Emails by Contact")
    st.markdown("Expand any contact to see their emails. Delete individually or in bulk.")

    _dm_conn = _sql.connect(str(db.db_path))
    _dm_conn.row_factory = _sql.Row
    _sender_list = _dm_conn.execute("""
        SELECT sender_email, sender_name, COUNT(*) as cnt,
               MIN(date_received) as first_email, MAX(date_received) as last_email
        FROM emails GROUP BY sender_email ORDER BY cnt DESC
    """).fetchall()
    _dm_conn.close()

    if _sender_list:
        dm_search = st.text_input("Search contacts", placeholder="Search by name or email...", key="dm_search")
        dm_filtered = list(_sender_list)
        if dm_search:
            dl = dm_search.lower()
            dm_filtered = [s for s in dm_filtered
                           if dl in s["sender_email"].lower() or dl in (s["sender_name"] or "").lower()]

        st.caption(f"{len(dm_filtered)} contacts, {sum(s['cnt'] for s in dm_filtered):,} emails")

        # Bulk delete by contact selection
        dm_bulk = st.multiselect(
            "Select contacts to bulk delete",
            [s["sender_email"] for s in dm_filtered[:100]],
            format_func=lambda x: f"{x} ({next((s['cnt'] for s in dm_filtered if s['sender_email'] == x), '?')} emails)",
            key="dm_bulk_del",
        )
        if dm_bulk:
            total_bulk = sum(s["cnt"] for s in dm_filtered if s["sender_email"] in dm_bulk)
            confirm_bulk = st.checkbox(f"Confirm: delete {total_bulk:,} emails from {len(dm_bulk)} contacts", key="dm_bulk_confirm")
            if confirm_bulk and st.button(f"Delete {total_bulk:,} emails", type="primary", key="dm_bulk_btn"):
                _dc = _sql.connect(str(db.db_path))
                for addr in dm_bulk:
                    _dc.execute("DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE sender_email = ?)", (addr,))
                    _dc.execute("DELETE FROM emails WHERE sender_email = ?", (addr,))
                _dc.commit()
                _dc.close()
                db.log_action("emails_deleted_by_contact", f"Deleted {total_bulk} emails from {len(dm_bulk)} contacts")
                st.success(f"Deleted {total_bulk:,} emails")
                st.rerun()

        st.markdown("---")

        # Per-contact expandable browser
        for sender in dm_filtered[:50]:
            s_email = sender["sender_email"]
            s_name = sender["sender_name"] or ""
            s_count = sender["cnt"]
            first = sender["first_email"][:10] if sender["first_email"] else "?"
            last = sender["last_email"][:10] if sender["last_email"] else "?"

            label = f"{s_name} ({s_email})" if s_name else s_email
            with st.expander(f"{label} — {s_count:,} emails ({first} to {last})"):
                # Load individual emails for this sender
                _em_conn = _sql.connect(str(db.db_path))
                _em_conn.row_factory = _sql.Row
                _emails = _em_conn.execute(
                    """SELECT id, subject, date_received, direction, has_attachments
                       FROM emails WHERE sender_email = ?
                       ORDER BY date_received DESC LIMIT 200""",
                    (s_email,)
                ).fetchall()
                _em_conn.close()

                # Delete all from this contact
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button(f"Delete all {s_count:,}", key=f"dm_del_all_{s_email}", type="secondary"):
                        _dc2 = _sql.connect(str(db.db_path))
                        _dc2.execute("DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE sender_email = ?)", (s_email,))
                        _dc2.execute("DELETE FROM emails WHERE sender_email = ?", (s_email,))
                        _dc2.commit()
                        _dc2.close()
                        db.log_action("emails_deleted_by_contact", f"Deleted {s_count} emails from {s_email}")
                        st.rerun()

                # Individual emails
                for em in _emails:
                    dt = em["date_received"][:16] if em["date_received"] else "?"
                    subj = em["subject"] or "(no subject)"
                    direction = em["direction"] or ""
                    att = " [att]" if em["has_attachments"] else ""

                    ecol1, ecol2, ecol3 = st.columns([0.5, 8, 1])
                    with ecol1:
                        pass
                    with ecol2:
                        st.caption(f"{dt} | {direction} | {subj[:80]}{att}")
                    with ecol3:
                        if st.button("x", key=f"dm_del_email_{em['id']}"):
                            _dc3 = _sql.connect(str(db.db_path))
                            _dc3.execute("DELETE FROM attachments WHERE email_id = ?", (em["id"],))
                            _dc3.execute("DELETE FROM emails WHERE id = ?", (em["id"],))
                            _dc3.commit()
                            _dc3.close()
                            st.rerun()

    st.divider()

    # ── Delete by Account ──
    st.markdown("### Delete by Account")
    all_accounts = db.get_accounts()
    for acc in all_accounts:
        _ac = _sql.connect(str(db.db_path))
        count = _ac.execute("SELECT COUNT(*) as c FROM emails WHERE account_id = ?", (acc["id"],)).fetchone()[0]
        _ac.close()
        if count > 0:
            provider = "Microsoft" if acc["provider"] == "microsoft" else "Gmail"
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"{provider}: {acc['email']} — {count:,} emails")
            with col2:
                confirm_acc = st.checkbox(f"Delete", key=f"del_acc_confirm_{acc['id']}")
                if confirm_acc and st.button("Confirm", key=f"del_acc_btn_{acc['id']}"):
                    _ac2 = _sql.connect(str(db.db_path))
                    _ac2.execute("DELETE FROM attachments WHERE email_id IN (SELECT id FROM emails WHERE account_id = ?)", (acc["id"],))
                    _ac2.execute("DELETE FROM emails WHERE account_id = ?", (acc["id"],))
                    _ac2.execute("UPDATE accounts SET last_synced = NULL WHERE id = ?", (acc["id"],))
                    _ac2.commit()
                    _ac2.close()
                    db.log_action("emails_deleted", f"Deleted {count} emails from {acc['email']}")
                    st.rerun()

    st.divider()

    # ── Clear All ──
    st.markdown("### Clear All Email Data")
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
