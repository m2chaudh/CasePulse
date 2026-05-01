"""Documents & Timeline Events — import documents, OCR, extract dates, manual timeline."""
import streamlit as st
import sys
import json
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Documents", page_icon="CP", layout="wide")

st.markdown("## Documents & Timeline")
st.markdown("Import documents, extract text, build timeline events.")

from components.page_init import init_page
db, config = init_page()

# Active case for "+ Add to Argument" (sidebar picker)
_all_cases = db.get_cases() if hasattr(db, "get_cases") else []
_active_case_id = st.session_state.get("active_case_id")
if not _active_case_id and _all_cases:
    _active_case_id = _all_cases[0]["id"]
if _all_cases:
    _case_opts = {f"{c['name']} ({c.get('case_type','case')})": c["id"]
                  for c in _all_cases}
    with st.sidebar:
        st.markdown("### Active Case")
        _sel_lbl = st.selectbox("Case", list(_case_opts.keys()),
                                 key="docs_active_case")
        _active_case_id = _case_opts[_sel_lbl]


def _has_photo_metadata(db, doc_id: int) -> bool:
    cur = db._get_conn().cursor()
    cur.execute(
        "SELECT id FROM photo_metadata WHERE source_table = ? AND source_row_id = ?",
        ("documents", doc_id),
    )
    return cur.fetchone() is not None


def _photo_metadata_for(db, source_table: str, source_row_id: int):
    """Return photo_metadata dict for a document, or None."""
    cur = db._get_conn().cursor()
    cur.execute(
        "SELECT id, taken_at, camera_make, camera_model, lens, "
        "software, gps_lat, gps_lon, orientation, exif_present "
        "FROM photo_metadata WHERE source_table = ? AND source_row_id = ?",
        (source_table, source_row_id),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "taken_at": row[1], "camera_make": row[2],
        "camera_model": row[3], "lens": row[4], "software": row[5],
        "gps_lat": row[6], "gps_lon": row[7],
        "orientation": row[8], "exif_present": bool(row[9]),
    }


tab_import, tab_docs, tab_timeline, tab_add = st.tabs([
    "Import Documents", "Document Library", "Timeline Events", "Add Event"
])

# ══════════════════════════════════════════════════════
# TAB 1: Import Documents
# ══════════════════════════════════════════════════════
with tab_import:
    st.markdown("### Import from Directory")
    st.markdown("Point to a folder with PDFs, Word docs, images, emails. Duplicates are auto-detected by file hash.")

    import_dir = st.text_input(
        "Document folder path",
        placeholder="/Users/mani/Personal/Legal Documents",
        key="doc_import_dir",
    )

    col1, col2 = st.columns(2)
    with col1:
        copy_files = st.checkbox("Copy files into CasePulse data folder", value=True,
                                  help="If unchecked, files stay in their original location (referenced by path)")
    with col2:
        pass

    if st.button("Import Documents", type="primary", disabled=not import_dir):
        if not Path(import_dir).exists():
            st.error(f"Directory not found: {import_dir}")
        else:
            with st.status("Importing documents...", expanded=True) as status:
                from casepulse.export.document_import import import_directory
                result = import_directory(
                    import_dir, db, copy_files=copy_files,
                    progress_cb=lambda msg: st.write(msg),
                )

                if "error" in result:
                    status.update(label="Import failed", state="error")
                    st.error(result["error"])
                else:
                    status.update(
                        label=f"Imported {result['imported']}, {result['duplicates']} duplicates, {result['errors']} errors",
                        state="complete",
                    )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Imported", result["imported"])
            with col2:
                st.metric("Duplicates", result["duplicates"])
            with col3:
                st.metric("Errors", result["errors"])

            if result.get("files"):
                with st.expander(f"Details ({len(result['files'])} files)"):
                    for f in result["files"]:
                        icon = "+" if f["status"] == "imported" else "=" if f["status"] == "duplicate" else "x"
                        extra = ""
                        if f["status"] == "duplicate":
                            extra = f" (same as {f.get('duplicate_of', '?')})"
                        elif f["status"] == "error":
                            extra = f" ({f.get('error', '?')})"
                        st.caption(f"[{icon}] {f['filename']}{extra}")

    st.divider()

    # File upload
    st.markdown("### Upload Files")
    uploaded = st.file_uploader(
        "Drop files here",
        type=["pdf", "docx", "doc", "txt", "csv", "jpg", "jpeg", "png", "gif", "eml", "html"],
        accept_multiple_files=True,
        key="doc_upload",
    )

    if uploaded and st.button("Process Uploaded Files"):
        import hashlib
        from casepulse.attachments.extractor import extract_text
        from casepulse.config import get_data_dir

        dest_dir = get_data_dir() / "documents"
        dest_dir.mkdir(exist_ok=True)

        imported = 0
        dupes = 0
        for uf in uploaded:
            raw = uf.read()
            content_hash = hashlib.sha256(raw).hexdigest()

            existing = db.get_document_by_hash(content_hash)
            if existing:
                st.caption(f"= {uf.name} (duplicate of {existing['filename']})")
                dupes += 1
                continue

            dest_path = dest_dir / uf.name
            dest_path.write_bytes(raw)

            ext = Path(uf.name).suffix.lower()
            content_type = uf.type or ""
            extracted = ""
            ocr_status = "pending"
            if ext in (".pdf", ".docx", ".doc", ".txt", ".csv", ".eml", ".html"):
                extracted = extract_text(str(dest_path), content_type)
                ocr_status = "done" if extracted else "no_text"
            elif ext in (".jpg", ".jpeg", ".png", ".gif"):
                ocr_status = "needs_ocr"

            db.insert_document(
                filename=uf.name, file_path=str(dest_path),
                content_type=content_type, size_bytes=len(raw),
                content_hash=content_hash, extracted_text=extracted,
                ocr_status=ocr_status,
            )
            st.caption(f"+ {uf.name} ({'text extracted' if extracted else ocr_status})")
            imported += 1

        st.success(f"Processed: {imported} imported, {dupes} duplicates")

    st.divider()

    # Import timeline HTML JSON
    st.markdown("### Import Timeline JSON")
    st.markdown("Export JSON from your `timeline.html` and paste or upload it here.")

    timeline_json_file = st.file_uploader("Upload timeline JSON export", type=["json"], key="timeline_json_upload")
    timeline_json_text = st.text_area("Or paste JSON here", placeholder='{"events": [...], "evidence": [...]}',
                                       key="timeline_json_paste", height=100)

    cases = db.get_cases()
    timeline_case_id = None
    if cases:
        case_options = {0: "No case"} | {c["id"]: c["name"] for c in cases}
        timeline_case_id = st.selectbox("Assign to case", list(case_options.keys()),
                                         format_func=lambda x: case_options[x], key="tl_import_case")
        if timeline_case_id == 0:
            timeline_case_id = None

    if st.button("Import Timeline Events", disabled=not (timeline_json_file or timeline_json_text)):
        json_content = ""
        if timeline_json_file:
            json_content = timeline_json_file.read().decode("utf-8")
        elif timeline_json_text:
            json_content = timeline_json_text

        from casepulse.export.document_import import parse_timeline_html_json
        events = parse_timeline_html_json(json_content)

        if not events:
            st.error("No events found in the JSON. Make sure it has an 'events' array.")
        else:
            imported = 0
            for ev in events:
                if ev.get("date"):
                    db.add_timeline_event(
                        date=ev["date"], time=ev.get("time", ""),
                        approx=ev.get("approx", "exact"),
                        category=ev.get("category", "context"),
                        description=ev.get("description", ""),
                        source_type=ev.get("source_type", "timeline_html"),
                        source_file=ev.get("source_file", ""),
                        refs=ev.get("refs", ""),
                        strength=ev.get("strength", "unassessed"),
                        contradicts=ev.get("contradicts", ""),
                        notes=ev.get("notes", ""),
                        case_id=timeline_case_id,
                    )
                    imported += 1
            db.log_action("timeline_import", f"Imported {imported} events from timeline JSON")
            st.success(f"Imported **{imported}** timeline events!")

# ══════════════════════════════════════════════════════
# TAB 2: Document Library
# ══════════════════════════════════════════════════════
with tab_docs:
    st.markdown("### Document Library")

    docs = db.get_documents()

    if not docs:
        st.info("No documents imported yet. Use the Import tab.")
    else:
        # Stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Documents", len(docs))
        with col2:
            st.metric("Text Extracted", sum(1 for d in docs if d["ocr_status"] == "done"))
        with col3:
            st.metric("Needs OCR", sum(1 for d in docs if d["ocr_status"] == "needs_ocr"))
        with col4:
            st.metric("No Text", sum(1 for d in docs if d["ocr_status"] == "no_text"))

        # OCR batch processing
        needs_ocr = [d for d in docs if d["ocr_status"] == "needs_ocr"]
        if needs_ocr:
            st.markdown(f"**{len(needs_ocr)} images need OCR** (vision model describes the image)")
            if st.button("Run OCR with AI Vision", type="primary"):
                from casepulse.llm.ollama_provider import OllamaProvider
                vision = OllamaProvider(model="llava:7b")

                progress = st.progress(0, text="Starting OCR...")
                for i, doc in enumerate(needs_ocr):
                    progress.progress(i / len(needs_ocr),
                                      text=f"OCR {i + 1}/{len(needs_ocr)}: {doc['filename']}")
                    try:
                        description = vision.describe_image(doc["file_path"])
                        db.update_document(doc["id"], extracted_text=description, ocr_status="done")
                    except Exception as e:
                        db.update_document(doc["id"], ocr_status="ocr_failed",
                                           extracted_text=f"[OCR Error: {str(e)}]")

                progress.progress(1.0, text=f"Done! {len(needs_ocr)} images processed.")
                st.rerun()

        # Document list
        search = st.text_input("Search documents", placeholder="Search by filename or content...", key="doc_search")

        filtered_docs = docs
        if search:
            search_lower = search.lower()
            filtered_docs = [d for d in docs if search_lower in d["filename"].lower()
                             or search_lower in (d.get("extracted_text") or "").lower()]

        for doc in filtered_docs:
            with st.expander(f"{doc['filename']} ({doc['ocr_status']}) — {doc['size_bytes'] // 1024} KB"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"Path: {doc['file_path']}")
                    st.caption(f"Type: {doc['content_type']} | Hash: {doc['content_hash'][:16]}...")

                    # Show extracted text
                    if doc.get("extracted_text"):
                        st.text_area("Extracted text", doc["extracted_text"][:3000],
                                     height=150, disabled=True, key=f"doctext_{doc['id']}",
                                     label_visibility="collapsed")

                    # Date extraction
                    if doc.get("extracted_text"):
                        from casepulse.export.document_import import extract_dates_from_text
                        dates = extract_dates_from_text(doc["extracted_text"])
                        if dates:
                            st.markdown(f"**Dates found ({len(dates)}):**")
                            for d in dates[:10]:
                                st.caption(f"  {d['date']} — {d['context'][:100]}")

                with col2:
                    # Manual timeline date
                    tl_date = st.date_input("Timeline date", value=None,
                                             key=f"doc_tl_date_{doc['id']}")
                    if tl_date:
                        db.update_document(doc["id"], timeline_date=str(tl_date))

                    # + Add to Argument button
                    if st.button("+ Add to Argument", key=f"docs_ata_{doc['id']}"):
                        if _active_case_id:
                            from casepulse.case_theory.ui.add_to_argument import show as _show_ata
                            _show_ata(
                                db,
                                source_table="documents",
                                source_row_id=doc["id"],
                                case_id=_active_case_id,
                            )
                        else:
                            st.info("No active case — create one in the Cases page first.")

                    if st.button("Delete", key=f"del_doc_{doc['id']}"):
                        db.delete_document(doc["id"])
                        st.rerun()

                # Photo metadata attestation form (Task 4.2)
                pm = _photo_metadata_for(db, "documents", doc["id"])
                if pm:
                    with st.expander("Photo metadata"):
                        from casepulse.case_theory.ui import attestation_form
                        attestation_form.render(
                            db,
                            photo_metadata_id=pm["id"],
                            photo_metadata=pm,
                        )

# ══════════════════════════════════════════════════════
# TAB 3: Timeline Events
# ══════════════════════════════════════════════════════
with tab_timeline:
    st.markdown("### Timeline Events")
    st.markdown("All events from emails, chats, documents, and manual entries — merged chronologically.")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        tl_start = st.date_input("From", value=date.fromisoformat(config.date_start), key="tl_ev_start")
    with col2:
        tl_end = st.date_input("To", value=date.fromisoformat(config.date_end), key="tl_ev_end")
    with col3:
        tl_cat = st.selectbox("Category", [
            "All", "relationship", "communication", "incident", "legal",
            "financial", "children", "contradiction", "context", "cas", "police",
        ], key="tl_ev_cat")

    cat_filter = None if tl_cat == "All" else tl_cat

    # Get case for filtering
    case_id_filter = None
    if cases:
        case_opts = {0: "All cases"} | {c["id"]: c["name"] for c in cases}
        case_id_filter = st.selectbox("Case", list(case_opts.keys()),
                                       format_func=lambda x: case_opts[x], key="tl_ev_case_filter")
        if case_id_filter == 0:
            case_id_filter = None

    events = db.get_timeline_events(
        case_id=case_id_filter, category=cat_filter,
        date_start=str(tl_start), date_end=str(tl_end),
    )

    st.markdown(f"**{len(events)} events**")

    if events:
        current_date = ""
        for ev in events:
            ev_date = ev.get("date", "")
            if ev_date != current_date:
                current_date = ev_date
                st.markdown(f"#### {current_date}")

            time_str = ev.get("time", "")
            approx = f" (~{ev['approx']})" if ev.get("approx") and ev["approx"] != "exact" else ""
            category = ev.get("category", "")
            strength = ev.get("strength", "")
            desc = ev.get("description", "")
            refs = ev.get("refs", "")
            notes = ev.get("notes", "")
            contradicts = ev.get("contradicts", "")
            source = ev.get("source_type", "")

            with st.expander(f"{time_str or '—'}{approx} | `{category}` | {desc[:80]}"):
                st.markdown(f"**{desc}**")
                if contradicts:
                    st.error(f"Contradicts: {contradicts}")
                if refs:
                    st.caption(f"References: {refs}")
                if notes:
                    st.caption(f"Notes: {notes}")
                st.caption(f"Strength: {strength} | Source: {source} | ID: {ev['id']}")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Delete", key=f"del_ev_{ev['id']}"):
                        db.delete_timeline_event(ev["id"])
                        st.rerun()
    else:
        st.info("No timeline events yet. Import from timeline JSON, or add events manually.")

# ══════════════════════════════════════════════════════
# TAB 4: Add Manual Event
# ══════════════════════════════════════════════════════
with tab_add:
    st.markdown("### Add Timeline Event Manually")
    st.markdown("For events that aren't in any email or document — verbal conversations, in-person incidents, court appearances.")

    with st.form("add_event_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ev_date = st.date_input("Date", key="ev_add_date")
        with col2:
            ev_time = st.text_input("Time (optional)", placeholder="14:30", key="ev_add_time")
        with col3:
            ev_approx = st.selectbox("Date precision", ["exact", "approximate", "estimated"],
                                      key="ev_add_approx")

        ev_category = st.selectbox("Category", [
            "relationship", "communication", "incident", "legal",
            "financial", "children", "contradiction", "context",
            "cas", "police", "court", "travel",
        ], key="ev_add_cat")

        ev_desc = st.text_area("Description", placeholder="What happened?", key="ev_add_desc")

        col1, col2 = st.columns(2)
        with col1:
            ev_strength = st.selectbox("Evidence strength",
                                        ["unassessed", "strong", "moderate", "weak"],
                                        key="ev_add_strength")
        with col2:
            ev_contradicts = st.text_input("Contradicts (optional)",
                                            placeholder="e.g., Para 12 of respondent's affidavit",
                                            key="ev_add_contradicts")

        ev_refs = st.text_input("References (optional)",
                                 placeholder="e.g., Exhibit A, Police Report #123",
                                 key="ev_add_refs")
        ev_notes = st.text_area("Notes (optional)", key="ev_add_notes", height=80)

        # Case assignment
        ev_case_id = None
        if cases:
            case_opts = {0: "No case"} | {c["id"]: c["name"] for c in cases}
            ev_case_id = st.selectbox("Assign to case", list(case_opts.keys()),
                                       format_func=lambda x: case_opts[x], key="ev_add_case")
            if ev_case_id == 0:
                ev_case_id = None

        submitted = st.form_submit_button("Add Event", type="primary")

    if submitted and ev_desc:
        db.add_timeline_event(
            date=str(ev_date), time=ev_time, approx=ev_approx,
            category=ev_category, description=ev_desc,
            source_type="manual", refs=ev_refs,
            strength=ev_strength, contradicts=ev_contradicts,
            notes=ev_notes, case_id=ev_case_id,
        )
        db.log_action("timeline_event_added", f"Manual event: {ev_desc[:50]}")
        st.success("Event added to timeline!")
