"""Export page — Generate court-ready PDFs, Excel timelines, and exhibit bundles."""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import date, datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Export", page_icon="CP", layout="wide")

st.markdown("## Export")
st.markdown("Generate court-ready documents, timelines, and exhibit bundles.")

from components.page_init import init_page
db, config = init_page()

stats = db.get_stats()
cases = db.get_cases()

# ── Export Presets ──
st.markdown("### What do you need?")

preset = st.selectbox(
    "Export type",
    [
        "AI Analysis Package (for Claude/Gemini)",
        "For My Lawyer (PDF + Notes)",
        "Timeline — Full Detail (PDF)",
        "Timeline — Court Ready (PDF, trimmed bodies)",
        "Timeline — Summary/Index (PDF)",
        "Timeline (Excel)",
        "Timeline (CSV)",
        "Chat Timeline (HTML with images)",
        "Exhibit Bundle (PDF)",
        "Full Data (JSON)",
        "Full Data (Markdown)",
    ],
    key="export_preset",
)

st.markdown("### Configure")

col1, col2 = st.columns(2)
with col1:
    export_start = st.date_input("From", value=date.fromisoformat(config.date_start), key="exp_start")
with col2:
    export_end = st.date_input("To", value=date.fromisoformat(config.date_end), key="exp_end")

# Case selection (for exhibit references and evidence tags)
selected_case_id = None
selected_case = None
if cases:
    case_options = {0: "No case (export all)"} | {c["id"]: f"{c['name']} ({c['case_type'].title()})" for c in cases}
    selected_case_id = st.selectbox(
        "Case",
        list(case_options.keys()),
        format_func=lambda x: case_options[x],
        key="exp_case",
        help="Select a case to include exhibit labels, tags, and annotations in the export",
    )
    if selected_case_id:
        selected_case = db.get_case(selected_case_id)

# Options based on preset
include_notes = False
include_chats = True

if "AI Analysis" in preset:
    st.info(
        "**AI Analysis Package** generates a folder with everything Claude/Gemini needs:\n"
        "- **MEGA_FILE.md** — single file with all emails + chats + documents (upload to Claude.ai)\n"
        "- **Individual files** — one per email, monthly chats, documents\n"
        "- **INSTRUCTIONS.md** — tells the AI how to analyze your case\n"
        "- **Attachments** — copies of all email attachments"
    )
    ai_output_dir = st.text_input(
        "Output folder",
        value=str(Path.home() / "Desktop" / "CasePulse_AI_Package"),
        key="ai_output_dir",
    )

if "Exhibit" in preset:
    if not cases:
        st.warning("Create a case and tag evidence first (Cases page) before exporting an exhibit bundle.")
        st.stop()
    if not selected_case_id:
        st.warning("Select a case to export its exhibit bundle.")
        st.stop()

col1, col2 = st.columns(2)
with col1:
    include_chats = st.checkbox("Include chat messages", value=True, key="exp_chats")
with col2:
    include_notes = st.checkbox("Include annotations/notes", value="Lawyer" in preset or "Full" in preset or "AI" in preset,
                                 key="exp_notes")

st.divider()

# ── Generate Export ──
if st.button("Generate Export", type="primary"):
    from casepulse.export.manifest import generate_export_id, generate_manifest, compute_checksum

    export_id = generate_export_id()
    case_name = selected_case["name"] if selected_case else ""
    case_number = selected_case.get("case_number", "") if selected_case else ""

    with st.status(f"Generating {preset}...", expanded=True) as status:
        try:
            if "AI Analysis" in preset:
                st.write("Building AI Analysis Package...")
                from casepulse.export.ai_package import build_ai_package

                my_emails = [a["email"] for a in db.get_accounts()]
                result = build_ai_package(
                    db, output_dir=ai_output_dir,
                    case_name=case_name,
                    my_emails=my_emails,
                    date_start=str(export_start), date_end=str(export_end),
                    include_chats=include_chats,
                    include_documents=True,
                    progress_cb=lambda msg: st.write(msg),
                )

                status.update(label=f"AI Package ready — {result['estimated_tokens']:,} tokens", state="complete")

                st.success(f"Package exported to: `{ai_output_dir}`")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Emails", f"{result['total_emails']:,}")
                with col2:
                    st.metric("Chat Messages", f"{result['total_chats']:,}")
                with col3:
                    st.metric("Est. Tokens", f"{result['estimated_tokens']:,}")

                st.markdown(f"""
### How to use this package:

**Claude.ai (recommended — your 1M context):**
1. Go to claude.ai
2. Start a new conversation
3. Upload `{ai_output_dir}/MEGA_FILE.md`
4. Upload `{ai_output_dir}/INSTRUCTIONS.md`
5. Ask: "Analyze this case data. Start with a summary of key findings."

**Claude Desktop:**
1. Same as above — drag and drop the files

**Claude Code:**
1. Open a new Claude Code session
2. Tell it: "Read all files in {ai_output_dir} and analyze my case"
                """)

                # Log export
                db.log_export(export_id, "ai_package", case_id=selected_case_id,
                              case_name=case_name, fmt="markdown",
                              items_count=result["total_emails"] + result["total_chats"],
                              manifest=json.dumps(result, default=str))
                db.log_action("export", f"AI Analysis Package: {result['estimated_tokens']:,} tokens")

                # Don't continue to the download button flow
                st.stop()

            elif "Lawyer" in preset:
                st.write("Building lawyer package (Timeline + Emails + Notes)...")
                from casepulse.export.pdf_builder import build_timeline_pdf
                from casepulse.export.timeline_export import build_timeline_excel

                # Timeline PDF
                pdf_data = build_timeline_pdf(
                    db, case_name=case_name, case_number=case_number,
                    date_start=str(export_start), date_end=str(export_end),
                    case_id=selected_case_id,
                )

                # Timeline Excel with notes
                excel_data = build_timeline_excel(
                    db, case_name=case_name,
                    date_start=str(export_start), date_end=str(export_end),
                    case_id=selected_case_id,
                )

                items = db.get_unified_timeline(str(export_start), str(export_end), limit=50000)
                items_count = len(items)

                status.update(label=f"Lawyer package ready — {items_count} items", state="complete")

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "Download Timeline (PDF)",
                        data=pdf_data,
                        file_name=f"CasePulse_Lawyer_Timeline_{export_start}_{export_end}.pdf",
                        mime="application/pdf",
                    )
                with col2:
                    st.download_button(
                        "Download Timeline (Excel with Notes)",
                        data=excel_data,
                        file_name=f"CasePulse_Lawyer_Timeline_{export_start}_{export_end}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                # Log
                db.log_export(export_id, "for_lawyer", case_id=selected_case_id,
                              case_name=case_name, fmt="pdf+excel", items_count=items_count)
                db.log_action("export", f"Lawyer package: {items_count} items")
                st.stop()

            elif "Timeline" in preset and "PDF" in preset:
                from casepulse.export.pdf_builder import build_timeline_pdf
                import shutil

                if "Full" in preset:
                    st.write("Building full detail timeline PDF (every email with full body + attachments)...")
                    detail = "full"
                    label = "Full_Detail"
                    body_cap = 0  # No cap
                elif "Court" in preset:
                    st.write("Building court-ready timeline PDF (trimmed bodies, ~500-800 pages)...")
                    detail = "full"
                    label = "Court_Ready"
                    body_cap = 800  # Cap bodies at 800 chars — keeps key content, cuts signatures/chains
                else:
                    st.write("Building summary/index timeline PDF (compact table)...")
                    detail = "summary"
                    label = "Summary_Index"
                    body_cap = 0

                data = build_timeline_pdf(
                    db, case_name=case_name, case_number=case_number,
                    date_start=str(export_start), date_end=str(export_end),
                    case_id=selected_case_id,
                    detail_level=detail,
                    attachments_folder="attachments",
                    body_cap=body_cap,
                )
                filename = f"CasePulse_Timeline_{label}_{export_start}_{export_end}.pdf"
                mime = "application/pdf"
                fmt = "pdf"
                items = db.get_unified_timeline(str(export_start), str(export_end), limit=50000)
                items_count = len(items)

                # For full detail, also save to Desktop with attachments folder
                if detail == "full":
                    from pathlib import Path as _P
                    out_dir = _P.home() / "Desktop" / f"CasePulse_Timeline_{label}"
                    out_dir.mkdir(exist_ok=True)
                    att_dir = out_dir / "attachments"
                    att_dir.mkdir(exist_ok=True)

                    # Save PDF
                    (out_dir / filename).write_bytes(data)

                    # Copy all attachments
                    from casepulse.config import get_data_dir
                    src_att = get_data_dir() / "attachments"
                    att_copied = 0
                    if src_att.exists():
                        for folder in src_att.iterdir():
                            if folder.is_dir():
                                for f in folder.iterdir():
                                    if f.is_file():
                                        dst = att_dir / f.name
                                        if not dst.exists():
                                            try:
                                                shutil.copy2(str(f), str(dst))
                                                att_copied += 1
                                            except Exception:
                                                pass

                    st.write(f"Saved to Desktop: `{out_dir}`")
                    st.write(f"PDF + {att_copied} attachment files. Attachments are hyperlinked in the PDF.")

            elif preset == "Timeline (Excel)":
                st.write("Building Excel timeline...")
                from casepulse.export.timeline_export import build_timeline_excel
                data = build_timeline_excel(
                    db, case_name=case_name,
                    date_start=str(export_start), date_end=str(export_end),
                    case_id=selected_case_id,
                )
                filename = f"CasePulse_Timeline_{export_start}_{export_end}.xlsx"
                mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                fmt = "excel"
                items = db.get_unified_timeline(str(export_start), str(export_end), limit=50000)
                items_count = len(items)

            elif preset == "Timeline (CSV)":
                st.write("Building CSV timeline...")
                from casepulse.export.timeline_export import build_timeline_csv
                csv_text = build_timeline_csv(
                    db, date_start=str(export_start), date_end=str(export_end),
                    case_id=selected_case_id,
                )
                data = csv_text.encode("utf-8")
                filename = f"CasePulse_Timeline_{export_start}_{export_end}.csv"
                mime = "text/csv"
                fmt = "csv"
                items = db.get_unified_timeline(str(export_start), str(export_end), limit=50000)
                items_count = len(items)

            elif "Chat Timeline" in preset:
                st.write("Building chat timeline HTML with inline images...")
                from casepulse.export.chat_timeline_html import build_chat_timeline_html
                from pathlib import Path as _P

                chat_out = str(_P.home() / "Desktop" / "CasePulse_Chat_Timeline")
                result = build_chat_timeline_html(
                    db, output_dir=chat_out,
                    case_name=case_name,
                    date_start=str(export_start), date_end=str(export_end),
                    include_images=True,
                    progress_cb=lambda msg: st.write(msg),
                )

                status.update(label=f"Chat timeline ready — {result['total_messages']:,} messages", state="complete")

                st.success(f"Saved to: `{chat_out}`")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Messages", f"{result['total_messages']:,}")
                with col2:
                    st.metric("Images", f"{result['total_images']:,}")
                with col3:
                    st.metric("Conversations", result['total_chats'])

                st.markdown(f"""
Open `{chat_out}/chat_timeline.html` in your browser to view.
Print with **Cmd+P** — images included, navigation bar hidden.

**For court:** Print to PDF from the browser (Cmd+P → Save as PDF).
This produces a standard PDF that any court accepts.
                """)

                db.log_export(export_id, "chat_timeline_html", case_id=selected_case_id,
                              case_name=case_name, fmt="html",
                              items_count=result["total_messages"])
                db.log_action("export", f"Chat timeline HTML: {result['total_messages']:,} messages")
                st.stop()

            elif preset == "Exhibit Bundle (PDF)":
                st.write("Building exhibit bundle...")
                from casepulse.export.pdf_builder import build_exhibit_bundle_pdf
                exhibit_prefix = selected_case.get("exhibit_prefix", "") if selected_case else ""
                data = build_exhibit_bundle_pdf(
                    db, case_id=selected_case_id,
                    case_name=case_name, case_number=case_number,
                    exhibit_prefix=exhibit_prefix,
                    include_notes=include_notes,
                )
                filename = f"CasePulse_Exhibits_{case_name.replace(' ', '_')}.pdf"
                mime = "application/pdf"
                fmt = "pdf"
                tags = db.get_evidence_tags_for_case(selected_case_id)
                items_count = len(tags)

            elif preset == "Full Data (JSON)":
                st.write("Building JSON export...")
                emails = db.get_emails(
                    date_start=str(export_start), date_end=str(export_end), limit=50000,
                )
                chats = db.get_chat_messages(
                    date_start=str(export_start), date_end=str(export_end), limit=50000,
                ) if include_chats else []

                export_data = {
                    "metadata": {
                        "export_id": export_id,
                        "generated": datetime.now().isoformat(),
                        "case": case_name,
                        "date_range": [str(export_start), str(export_end)],
                    },
                    "emails": [],
                    "chat_messages": [],
                }
                for e in emails:
                    entry = dict(e)
                    entry["attachments"] = db.get_attachments_for_email(e["id"])
                    if include_notes and selected_case_id:
                        entry["annotations"] = db.get_annotations("email", e["id"], selected_case_id)
                        tag = db.get_evidence_tag("email", e["id"], selected_case_id)
                        entry["evidence_tag"] = tag
                    export_data["emails"].append(entry)

                for m in chats:
                    entry = dict(m)
                    if include_notes and selected_case_id:
                        entry["annotations"] = db.get_annotations("chat", m["id"], selected_case_id)
                    export_data["chat_messages"].append(entry)

                data = json.dumps(export_data, indent=2, default=str).encode("utf-8")
                filename = f"CasePulse_FullExport_{export_start}_{export_end}.json"
                mime = "application/json"
                fmt = "json"
                items_count = len(emails) + len(chats)

            elif preset == "Full Data (Markdown)":
                st.write("Building Markdown export...")
                items = db.get_unified_timeline(str(export_start), str(export_end), limit=50000)

                md = [f"# CasePulse Export — {case_name or 'All Data'}\n"]
                md.append(f"**Date Range:** {export_start} to {export_end}")
                md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                md.append(f"**Items:** {len(items)}\n")
                md.append("---\n")

                current_dt = ""
                for item in items:
                    ts = str(item.get("timestamp", ""))
                    if ts[:10] != current_dt:
                        current_dt = ts[:10]
                        md.append(f"\n## {current_dt}\n")

                    sender = item.get("sender", "")
                    subject = item.get("subject", "")
                    body = item.get("body_preview", "")
                    item_type = item.get("type", "email")
                    direction = item.get("direction", "")
                    fwd = " [FORWARDED]" if item.get("is_forwarded") else ""

                    md.append(f"### {ts[11:16]} — {sender} ({item_type}, {direction}){fwd}")
                    if subject:
                        md.append(f"**Subject:** {subject}\n")
                    if body:
                        md.append(f"> {body[:500]}\n")

                data = "\n".join(md).encode("utf-8")
                filename = f"CasePulse_Export_{export_start}_{export_end}.md"
                mime = "text/markdown"
                fmt = "markdown"
                items_count = len(items)

            # Generate manifest
            manifest = generate_manifest(
                export_id=export_id,
                case_name=case_name,
                case_number=case_number,
                export_type=preset,
                filters={
                    "date_start": str(export_start),
                    "date_end": str(export_end),
                    "case_id": selected_case_id,
                    "include_chats": include_chats,
                    "include_notes": include_notes,
                },
                items_count=items_count,
                pages_total=len(data) // 3000 if fmt == "pdf" else 0,  # rough estimate
                attachments_count=0,
                privilege_excluded=0,
            )

            # Log the export
            db.log_export(
                export_id=export_id,
                export_type=preset,
                case_id=selected_case_id,
                case_name=case_name,
                fmt=fmt,
                items_count=items_count,
                filters=json.dumps(manifest["filters_applied"]),
                manifest=json.dumps(manifest),
            )
            db.log_action("export", f"Generated {preset} with {items_count} items (ID: {export_id})")

            status.update(label=f"Export ready — {items_count} items", state="complete")

            # Download button
            st.download_button(
                f"Download {filename}",
                data=data,
                file_name=filename,
                mime=mime,
            )

            # Show manifest
            with st.expander("Export Manifest"):
                st.json(manifest)

        except Exception as e:
            status.update(label="Export failed", state="error")
            st.error(f"Export error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

st.divider()

# ── Export History ──
st.markdown("### Export History")
exports = db.get_export_log(limit=20)
if exports:
    for exp in exports:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            st.markdown(f"**{exp['export_type']}** — {exp.get('case_name') or 'All data'}")
        with col2:
            st.caption(f"{exp['items_count']} items | {exp['format']} | {exp['created_at'][:16]}")
        with col3:
            st.caption(f"ID: {exp['export_id']}")
else:
    st.caption("No exports yet.")
