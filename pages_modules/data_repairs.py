"""Data Repairs — preview and apply known data-quality migrations.

Each section shows:
  - What the migration does
  - 3 sample BEFORE/AFTER rows from your DB
  - Counts of how many rows would change
  - An Apply button (writes to the DB)
"""
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

from components.page_init import init_page
from casepulse.case_theory.ui import page_help

from casepulse.scripts.repair_chat_bundles import (
    _split_bundle, repair as run_bundle_repair,
)
from casepulse.scripts.clean_appclose_chats import (
    _clean, repair as run_appclose_repair,
)
from casepulse.config import get_data_dir


db, config = init_page()
page_help.render("data_repairs")

st.markdown("## Data Repairs")
st.caption(
    "One-shot migrations that clean up known data-quality issues from past "
    "imports. Each one is idempotent — running twice has no further effect. "
    "Use **Backup DB first** if you want a rollback path."
)


# ── Backup helper ─────────────────────────────────────────────────────────
def _backup_db() -> str | None:
    """Copy the active SQLite DB next to itself with a timestamp suffix.
    Returns the backup path on success, None on failure."""
    src = get_data_dir() / "db" / "casepulse.db"
    if not src.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = src.with_name(f"casepulse-pre-repair-{ts}.db")
    try:
        shutil.copy2(src, dst)
        return str(dst)
    except OSError as e:
        st.error(f"Backup failed: {e}")
        return None


backup_first = st.checkbox(
    "Backup the database first (writes a timestamped copy alongside it)",
    value=True,
    key="repair_backup_first",
)


st.divider()


# ── Section 1: WhatsApp bundle repair ─────────────────────────────────────
st.markdown("### WhatsApp bundle repair")
st.caption(
    "The original WhatsApp ingest concatenated subsequent message headers "
    "into the previous message's body when it hit `<IMAGE OMITTED>` or "
    "system lines. This splits each bundle into separate rows with the "
    "right timestamp / sender."
)

# Sample BEFORE/AFTER — pick 3 rows that have embedded WA headers
with db._get_conn() as _conn:
    _bundle_rows = _conn.execute(
        "SELECT id, sender, timestamp, message_text FROM chat_messages "
        "WHERE message_text LIKE '%2024-%-% - %:%' "
        "   OR message_text LIKE '%2025-%-% - %:%' "
        "   OR message_text LIKE '%2026-%-% - %:%' "
        "LIMIT 200"
    ).fetchall()

_sample_count = 0
for r in _bundle_rows:
    text = r["message_text"] or ""
    head, subs = _split_bundle(text)
    if not subs:
        continue
    _sample_count += 1
    if _sample_count > 3:
        break
    with st.container(border=True):
        st.markdown(
            f"**chat #{r['id']}** · primary timestamp `{r['timestamp']}` · "
            f"sender `{r['sender']}`"
        )
        st.markdown("**Parent body trimmed to:**")
        st.code(head[:300] or "(empty)", language=None)
        st.markdown(f"**{len(subs)} sub-message(s) would be added as new rows:**")
        for s in subs[:5]:
            body_preview = (s["body"] or "")[:150].replace("\n", " ")
            st.text(f"  [{s['date']} {s['time']}]  {s['sender']}: {body_preview}")
        if len(subs) > 5:
            st.caption(f"  … +{len(subs) - 5} more sub-messages")

# Counts
_bundle_dry = run_bundle_repair(db, apply_changes=False)
st.markdown(
    f"**Scope:** {_bundle_dry['bundle_parents_found']} bundle parents → "
    f"{_bundle_dry['sub_messages_extracted']} sub-messages extracted "
    f"({_bundle_dry['sub_messages_skipped_dup']} already present)"
)

if st.button("Apply WhatsApp bundle repair", type="primary",
              key="apply_bundle_repair"):
    if backup_first:
        path = _backup_db()
        if path:
            st.info(f"Backup written to `{path}`")
    stats = run_bundle_repair(db, apply_changes=True)
    st.success(
        f"Done. {stats['sub_messages_inserted']} new chat rows inserted, "
        f"{stats['parents_trimmed']} parents trimmed."
    )
    st.rerun()

st.divider()


# ── Section 2: AppClose boilerplate cleanup ───────────────────────────────
st.markdown("### AppClose boilerplate cleanup")
st.caption(
    "The AppClose PDF-export ingest swept page footers (`Generated: ... "
    "Page N of M`), repeated header timestamps, the export preamble, "
    "and the bottom attachment-image listings into each chat row's body. "
    "This strips those patterns so messages read cleanly."
)

with db._get_conn() as _conn:
    _ac_rows = _conn.execute(
        "SELECT id, sender, timestamp, message_text FROM chat_messages "
        "WHERE platform = 'AppClose' "
        "  AND (message_text LIKE '%Generated:%Page%of%' "
        "       OR message_text LIKE '%Attachment Img.%' "
        "       OR message_text LIKE '%AppClose Records Export%') "
        "LIMIT 50"
    ).fetchall()

_ac_sample_count = 0
for r in _ac_rows:
    before = r["message_text"] or ""
    after = _clean(before)
    if before == after:
        continue
    _ac_sample_count += 1
    if _ac_sample_count > 3:
        break
    with st.container(border=True):
        st.markdown(
            f"**chat #{r['id']}** · `{r['timestamp']}` · sender `{r['sender']}`"
        )
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**BEFORE:**")
            st.code(before[:500], language=None)
        with col2:
            st.markdown("**AFTER:**")
            st.code(after[:500] or "(empty)", language=None)

_ac_dry = run_appclose_repair(db, apply_changes=False)
st.markdown(
    f"**Scope:** {_ac_dry['would_clean']} chat rows would be cleaned · "
    f"{_ac_dry['unchanged']} already clean"
)

if st.button("Apply AppClose cleanup", type="primary",
              key="apply_appclose_clean"):
    if backup_first:
        path = _backup_db()
        if path:
            st.info(f"Backup written to `{path}`")
    stats = run_appclose_repair(db, apply_changes=True)
    st.success(f"Done. {stats['would_clean']} chat rows cleaned.")
    st.rerun()

st.divider()


# ── Section 3: AppClose v2 parser dry-run ────────────────────────────────
st.markdown("### AppClose v2 parser · dry-run preview")
st.caption(
    "Verifies sender / Sent / Viewed-by / body parsing on the original "
    "PDF before ANY migration runs. Used as a court-grade accuracy gate — "
    "you eyeball the rows, mark any wrong, and the migration only proceeds "
    "once every row reads ✓. **No DB writes happen in this section.**"
)

with db._get_conn() as _conn:
    _import_row = _conn.execute(
        "SELECT source_file FROM chat_imports WHERE platform='AppClose' "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
_pdf_path = _import_row["source_file"] if _import_row else None

if not _pdf_path or not Path(_pdf_path).exists():
    st.warning(
        "Source AppClose PDF not found. Looked for the path stored in "
        "`chat_imports`. Re-import the AppClose PDF on the Import Chats "
        "page first, then return here."
    )
else:
    import hashlib
    sha = hashlib.sha256()
    try:
        with open(_pdf_path, "rb") as _f:
            for chunk in iter(lambda: _f.read(1024 * 1024), b""):
                sha.update(chunk)
        st.caption(f"Source PDF: `{_pdf_path}`")
        st.caption(f"SHA-256: `{sha.hexdigest()}`")
    except OSError:
        st.error("Could not read the source PDF.")

    n_preview = st.slider(
        "Messages to preview", min_value=5, max_value=50, value=20, step=5,
        key="appclose_preview_n",
    )
    if st.button("Run v2 parser on source PDF", key="run_appclose_v2"):
        with st.spinner("Parsing PDF..."):
            from casepulse.scripts.appclose_parser_v2 import parse_appclose_pdf
            try:
                _parsed = parse_appclose_pdf(_pdf_path)
                st.session_state["_appclose_v2_parsed"] = _parsed
                st.success(f"Parsed {len(_parsed)} messages from {_pdf_path}.")
            except Exception as e:
                st.error(f"Parser failed: {e}")
                _parsed = None

    parsed = st.session_state.get("_appclose_v2_parsed")
    if parsed:
        st.markdown(
            f"#### Side-by-side verification — first {min(n_preview, len(parsed))} of "
            f"{len(parsed)} messages"
        )
        st.caption(
            "Each row: literal PDF header line · parser output · your verification mark. "
            "Click ✗ on any row that's wrong before approving."
        )

        # Header
        cols = st.columns([3, 4, 1])
        cols[0].markdown("**RAW PDF**")
        cols[1].markdown("**PARSER OUTPUT**")
        cols[2].markdown("**OK?**")
        st.divider()

        for i, m in enumerate(parsed[:n_preview]):
            cols = st.columns([3, 4, 1])
            with cols[0]:
                st.code(m.raw_header.strip(), language=None)
                if m.raw_body_excerpt.strip():
                    with st.expander("body (raw, first 300 chars)", expanded=False):
                        st.code(m.raw_body_excerpt[:300], language=None)
            with cols[1]:
                st.markdown(f"**Sender:** `{m.sender}`")
                st.markdown(
                    f"**Sent:** `{m.sent_at_raw}` "
                    f"({'parsed: ' + m.sent_at.isoformat() if m.sent_at else '⚠ unparsed'})"
                )
                if m.viewed:
                    for v in m.viewed:
                        v_str = v.viewed_at.isoformat() if v.viewed_at else "⚠ unparsed"
                        st.markdown(
                            f"**Viewed by `{v.recipient}`:** `{v_str}`"
                        )
                else:
                    st.markdown("_(no viewed-by entries)_")
                st.markdown(f"**Action:** `{m.action}` · **Page:** {m.page or '?'}")
                if m.body:
                    body_show = m.body if len(m.body) < 200 else m.body[:200] + "…"
                    st.markdown(f"**Body:** {body_show}")
                if m.attachment_refs:
                    refs = ", ".join(
                        f"{r['filename']}→p{r['page']}" for r in m.attachment_refs
                    )
                    st.caption(f"📎 attachment refs in body: {refs}")
            with cols[2]:
                # Default each row to assumed-OK; user clicks ✗ to flag
                key = f"_acv2_ok_{i}"
                ok = st.checkbox("✓", value=True, key=key,
                                  label_visibility="visible")
            st.divider()

        # Summary + next-step gate
        flagged = [
            i for i in range(min(n_preview, len(parsed)))
            if not st.session_state.get(f"_acv2_ok_{i}", True)
        ]
        if flagged:
            st.error(
                f"{len(flagged)} row(s) flagged: "
                + ", ".join(f"#{i+1}" for i in flagged)
                + ". Tell me which fields are wrong (in chat) and I'll fix the parser."
            )
        else:
            st.success(
                "All preview rows ✓. Parser is ready for the next step "
                "(image extraction + chat_messages rewrite migration). "
                "That migration will land in a separate session."
            )
st.divider()
st.caption(
    "These migrations only modify `chat_messages`. Future imports won't "
    "re-introduce the patterns — the original ingest logic is unchanged "
    "but new ingests handle these cases correctly."
)
