"""Contradiction Analysis — find inconsistencies across emails and chats."""
import streamlit as st
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Contradictions", page_icon="CP", layout="wide")

st.markdown("## Contradiction Analysis")
st.markdown("Find inconsistencies, changing narratives, and contradictions across emails and chats.")

from components.page_init import init_page
db, config = init_page()

from casepulse.storage.database import Database as _DB

stats = db.get_stats()
if stats["total_emails"] == 0:
    st.info("Fetch emails first before running contradiction analysis.")
    st.stop()

# ══════════════════════════════════════════════════════
# SELECT CONTACTS TO ANALYZE
# ══════════════════════════════════════════════════════
st.markdown("### Who to Analyze")
st.markdown("Select the contacts whose statements you want to check for contradictions.")

senders = db.get_senders(selected_only=True)
category_labels = {
    "ex_spouse": "Ex-Spouse", "opposing_lawyer": "Opposing Lawyer",
    "cas_worker": "CAS Worker", "police": "Police", "therapist": "Therapist",
    "my_lawyer": "My Lawyer", "family_lawyer": "Family Law Lawyer",
}

# Show key contacts with email counts
import sqlite3
conn = sqlite3.connect(str(db.db_path))
conn.row_factory = sqlite3.Row
email_counts = {}
for r in conn.execute("SELECT sender_email, COUNT(*) as cnt FROM emails GROUP BY sender_email").fetchall():
    email_counts[r["sender_email"]] = r["cnt"]
conn.close()

# Group by category
target_contacts = []
for s in senders:
    cats = _DB.parse_categories(s.get("category"))
    count = email_counts.get(s["email"], 0)
    if count == 0:
        continue
    target_contacts.append({
        "email": s["email"],
        "name": s.get("display_name") or "",
        "categories": cats,
        "email_count": count,
    })

# Sort by relevance (ex-spouse and opposing lawyers first)
priority_cats = {"ex_spouse", "opposing_lawyer", "cas_worker", "police"}
target_contacts.sort(key=lambda x: (
    0 if any(c in priority_cats for c in x["categories"]) else 1,
    -x["email_count"],
))

if not target_contacts:
    st.warning("No contacts with fetched emails found. Fetch emails first.")
    st.stop()

# Select contacts
selected_targets = st.multiselect(
    "Contacts to analyze",
    [c["email"] for c in target_contacts],
    default=[c["email"] for c in target_contacts[:5] if any(cat in priority_cats for cat in c["categories"])],
    format_func=lambda x: f"{next((c['name'] for c in target_contacts if c['email'] == x), '')} ({x}) — {email_counts.get(x, 0)} emails",
    key="contra_targets",
)

# Settings
col1, col2 = st.columns(2)
with col1:
    batch_size = st.slider("Emails per AI batch", 5, 30, 15, key="contra_batch",
                            help="Smaller = more accurate. Larger = faster.")
with col2:
    st.markdown(f"**AI Provider:** {config.llm_provider} ({config.llm_model})")
    st.caption("Change in Home > Settings. Tip: Use Ollama for extraction, switch to Gemini/Claude for contradiction detection.")

# ══════════════════════════════════════════════════════
# RUN ANALYSIS
# ══════════════════════════════════════════════════════
if st.button("Run Contradiction Analysis", type="primary", disabled=not selected_targets):
    targets = [c for c in target_contacts if c["email"] in selected_targets]

    total_emails = sum(c["email_count"] for c in targets)
    est_calls = (total_emails // batch_size) + len(targets) * 2
    st.info(f"Analyzing {len(targets)} contacts, ~{total_emails} emails. Estimated ~{est_calls} AI calls.")

    from casepulse.llm.api_provider import create_provider
    from casepulse.analysis.contradictions import run_full_analysis

    try:
        llm = create_provider(
            config.llm_provider, model=config.llm_model,
            api_key=config.llm_api_key, base_url=config.llm_base_url,
        )
    except Exception as e:
        st.error(f"Could not initialize AI: {e}")
        st.stop()

    progress = st.empty()
    results = run_full_analysis(
        db, llm, targets, batch_size=batch_size,
        progress_cb=lambda msg: progress.info(msg),
    )

    st.session_state["contra_results"] = results
    progress.success(
        f"Analysis complete: {results['total_statements']} statements, "
        f"{results['total_contradictions']} contradictions, "
        f"{results['total_cross_source']} cross-source conflicts, "
        f"{results.get('total_doc_conflicts', 0)} document vs evidence conflicts"
    )

# ══════════════════════════════════════════════════════
# RESULTS
# ══════════════════════════════════════════════════════
if "contra_results" in st.session_state:
    results = st.session_state["contra_results"]

    st.divider()

    # Summary
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Statements", results["total_statements"])
    with col2:
        st.metric("Contradictions", results["total_contradictions"])
    with col3:
        st.metric("Cross-Source", results["total_cross_source"])
    with col4:
        st.metric("Doc vs Evidence", results.get("total_doc_conflicts", 0))
    with col5:
        st.metric("Contacts", results["analyzed_contacts"])

    tab_contras, tab_docs, tab_cross, tab_stmts, tab_export = st.tabs([
        "Contradictions", "Documents vs Evidence", "Email vs Chat", "All Statements", "Export Report"
    ])

    # ── Tab 1: Contradictions ──
    with tab_contras:
        st.markdown("### Contradictions Found")

        for sender_email, contras in results["contradictions"].items():
            if not contras:
                continue

            name = next((c["name"] for c in target_contacts if c["email"] == sender_email), sender_email)
            st.markdown(f"#### {name} ({sender_email}) — {len(contras)} contradictions")

            # Sort by severity
            severity_order = {"high": 0, "medium": 1, "low": 2}
            contras.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

            for i, c in enumerate(contras):
                severity = c.get("severity", "?")
                sev_color = "red" if severity == "high" else "orange" if severity == "medium" else "blue"
                contra_type = c.get("contradiction_type", "?")

                st.markdown(f"**{i+1}. [{severity.upper()}] {contra_type}**")

                col1, col2 = st.columns(2)
                with col1:
                    a = c.get("statement_a", {})
                    st.markdown(f"**Statement A** [{a.get('date', '?')}]")
                    st.info(a.get("statement", ""))
                    st.caption(f"Source: {a.get('source_type', '')} — {a.get('source_subject', '')}")

                with col2:
                    b = c.get("statement_b", {})
                    st.markdown(f"**Statement B** [{b.get('date', '?')}]")
                    st.error(b.get("statement", ""))
                    st.caption(f"Source: {b.get('source_type', '')} — {b.get('source_subject', '')}")

                st.markdown(f"**Explanation:** {c.get('explanation', '')}")
                st.markdown("---")

        if not any(results["contradictions"].values()):
            st.info("No contradictions found. This could mean statements are consistent, or try analyzing more contacts.")

    # ── Tab 2: Documents vs Evidence ──
    with tab_docs:
        st.markdown("### Document Claims vs Actual Evidence")
        st.markdown(
            "Where allegations in **affidavits, police reports, and court filings** "
            "are contradicted or unsupported by the **actual email and chat evidence**."
        )

        doc_conflicts = results.get("doc_vs_communication", [])
        if doc_conflicts:
            # Sort by severity
            severity_order = {"high": 0, "medium": 1, "low": 2}
            doc_conflicts.sort(key=lambda x: severity_order.get(x.get("severity", "low"), 3))

            for i, c in enumerate(doc_conflicts):
                severity = c.get("severity", "?")

                st.markdown(f"**{i+1}. [{severity.upper()}] {c.get('type', '')}**")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**What the document claims:**")
                    st.error(c.get("document_claim", ""))
                with col2:
                    st.markdown("**What the actual evidence shows:**")
                    st.success(c.get("actual_evidence", ""))

                st.markdown(f"**Defense value:** {c.get('defense_value', '')}")
                st.markdown("---")
        else:
            st.info(
                "No document vs evidence conflicts found. To use this feature:\n"
                "1. Import documents (affidavits, police reports) via the **Documents** page\n"
                "2. Make sure text is extracted (PDFs processed)\n"
                "3. Re-run the analysis"
            )

    # ── Tab 3: Cross-Source ──
    with tab_cross:
        st.markdown("### Email vs Chat Contradictions")
        st.markdown("Things said in formal emails that contradict informal chat messages.")

        for sender_email, conflicts in results.get("cross_source", {}).items():
            if not conflicts:
                continue

            name = next((c["name"] for c in target_contacts if c["email"] == sender_email), sender_email)
            st.markdown(f"#### {name} — {len(conflicts)} cross-source conflicts")

            for i, c in enumerate(conflicts):
                st.markdown(f"**{i+1}. [{c.get('severity', '?').upper()}]**")

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**In Email:**")
                    st.info(c.get("email_statement", ""))
                with col2:
                    st.markdown("**In Chat:**")
                    st.error(c.get("chat_statement", ""))

                st.markdown(f"**Why it matters:** {c.get('explanation', '')}")
                st.markdown("---")

        if not any(results.get("cross_source", {}).values()):
            st.info("No cross-source contradictions found.")

    # ── Tab 3: All Statements ──
    with tab_stmts:
        st.markdown("### Extracted Statements")

        for sender_email, stmts in results["statements"].items():
            if not stmts:
                continue

            name = next((c["name"] for c in target_contacts if c["email"] == sender_email), sender_email)
            with st.expander(f"{name} ({sender_email}) — {len(stmts)} statements"):
                for s in sorted(stmts, key=lambda x: x.get("date", "")):
                    source_icon = "E" if s["source_type"] == "email" else "C"
                    st.caption(
                        f"[{source_icon}] {s.get('date', '?')} | `{s.get('category', '?')}` | "
                        f"{s.get('statement', '')} — *{s.get('source_subject', '')}*"
                    )

    # ── Tab 4: Export ──
    with tab_export:
        st.markdown("### Export Contradiction Report")

        report_lines = ["# Contradiction Analysis Report\n"]
        report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report_lines.append(f"**Statements:** {results['total_statements']}")
        report_lines.append(f"**Contradictions:** {results['total_contradictions']}")
        report_lines.append(f"**Cross-Source Conflicts:** {results['total_cross_source']}\n")
        report_lines.append("---\n")

        for sender_email, contras in results["contradictions"].items():
            if not contras:
                continue
            name = next((c["name"] for c in target_contacts if c["email"] == sender_email), sender_email)
            report_lines.append(f"\n## {name} ({sender_email})\n")

            for i, c in enumerate(contras):
                a = c.get("statement_a", {})
                b = c.get("statement_b", {})
                report_lines.append(f"### Contradiction {i+1} [{c.get('severity', '?').upper()}] — {c.get('contradiction_type', '')}\n")
                report_lines.append(f"**Statement A** [{a.get('date', '?')}]: {a.get('statement', '')}")
                report_lines.append(f"- Source: {a.get('source_type', '')} — {a.get('source_subject', '')}\n")
                report_lines.append(f"**Statement B** [{b.get('date', '?')}]: {b.get('statement', '')}")
                report_lines.append(f"- Source: {b.get('source_type', '')} — {b.get('source_subject', '')}\n")
                report_lines.append(f"**Explanation:** {c.get('explanation', '')}\n")
                report_lines.append("---\n")

        report_md = "\n".join(report_lines)
        report_json = json.dumps(results, indent=2, default=str)

        col1, col2 = st.columns(2)
        with col1:
            st.download_button("Download Report (Markdown)", report_md,
                                file_name="contradiction_report.md", mime="text/markdown")
        with col2:
            st.download_button("Download Full Data (JSON)", report_json,
                                file_name="contradiction_analysis.json", mime="application/json")

    # Clear results button
    if st.button("Clear Results", key="clear_contra"):
        del st.session_state["contra_results"]
        st.rerun()
