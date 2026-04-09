"""Import Chats page — Import WhatsApp, ChatVault, PDF chat exports."""
import streamlit as st
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Import Chats", page_icon="CP", layout="wide")

st.markdown("## Import Chats")
st.markdown("Import WhatsApp exports, ChatVault HTML, PDF chat exports, and more.")


from components.page_init import init_page
db, config = init_page()

# ── Import Methods ──
tab1, tab2, tab3, tab4 = st.tabs([
    "Bulk Directory Import",
    "WhatsApp File",
    "PDF Chat Export",
    "ChatVault HTML",
])

# ── Tab 1: Bulk Directory Import ──
with tab1:
    st.markdown("### Import All Chats from a Directory")
    st.markdown("""
    Point to a folder containing WhatsApp exports. It will auto-detect:
    - **Subdirectories** with `.txt` + media files (raw WhatsApp exports)
    - **`.zip` files** (compressed WhatsApp exports)
    - **`.txt` files** (WhatsApp chat exports)
    - **ChatVault `index.html`** files
    - **PDF chat exports**
    """)

    bulk_dir = st.text_input(
        "Directory path",
        placeholder="/Users/mani/Personal/WhatsApp/WhatsApp Content RAW",
        key="bulk_dir",
        help="Full path to the folder containing chat exports",
    )

    if st.button("Import All from Directory", type="primary", disabled=not bulk_dir):
        if not Path(bulk_dir).exists():
            st.error(f"Directory not found: {bulk_dir}")
        elif not Path(bulk_dir).is_dir():
            st.error(f"Not a directory: {bulk_dir}")
        else:
            with st.status("Importing chats...", expanded=True) as status:
                from casepulse.chat_engine.importer import import_bulk_directory

                result = import_bulk_directory(
                    bulk_dir, db,
                    progress_cb=lambda msg: st.write(msg),
                )

                if result["errors"]:
                    for err in result["errors"]:
                        st.warning(err)

                status.update(
                    label=f"Imported {result['total_imports']} chats, {result['total_messages']} messages",
                    state="complete",
                )

            st.markdown("### Import Results")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Chats Imported", result["total_imports"])
            with col2:
                st.metric("Total Messages", f"{result['total_messages']:,}")
            with col3:
                st.metric("Media Files", result["total_media"])

            if result["imports"]:
                st.markdown("**Imported chats:**")
                for imp in result["imports"]:
                    st.markdown(f"- **{imp['chat_name']}** — {imp['messages']:,} messages")

# ── Tab 2: WhatsApp File ──
with tab2:
    st.markdown("### Import WhatsApp Chat Export")
    st.markdown("Upload a `.txt` or `.zip` file exported from WhatsApp.")

    wa_file = st.file_uploader(
        "WhatsApp export file",
        type=["txt", "zip"],
        key="wa_upload",
    )

    if wa_file and st.button("Import WhatsApp Chat"):
        # Save uploaded file
        tmp_dir = Path("/tmp/casepulse_uploads")
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / wa_file.name
        tmp_path.write_bytes(wa_file.read())

        with st.status("Importing...", expanded=True) as status:
            from casepulse.chat_engine.importer import import_whatsapp_txt, import_whatsapp_zip

            if wa_file.name.endswith(".zip"):
                result = import_whatsapp_zip(str(tmp_path), db,
                                             progress_cb=lambda msg: st.write(msg))
            else:
                result = import_whatsapp_txt(str(tmp_path), db,
                                             progress_cb=lambda msg: st.write(msg))

            if "error" in result:
                status.update(label="Import failed", state="error")
                st.error(result["error"])
            else:
                status.update(
                    label=f"Imported {result['count']} messages from {result['chat_name']}",
                    state="complete",
                )
                st.success(f"Imported **{result['count']}** messages from **{result['chat_name']}**")

# ── Tab 3: PDF Chat Export ──
with tab3:
    st.markdown("### Import Chat from PDF")
    st.markdown("Upload a PDF export from any chat app (iMessage, Messenger, etc.)")

    pdf_file = st.file_uploader(
        "PDF chat export",
        type=["pdf"],
        key="pdf_upload",
    )

    pdf_platform = st.selectbox(
        "Platform (auto-detect or specify)",
        ["auto", "imessage", "messenger", "telegram", "whatsapp", "generic"],
        key="pdf_platform",
    )

    if pdf_file and st.button("Import PDF Chat"):
        tmp_dir = Path("/tmp/casepulse_uploads")
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / pdf_file.name
        tmp_path.write_bytes(pdf_file.read())

        with st.status("Parsing PDF...", expanded=True) as status:
            from casepulse.chat_engine.importer import import_pdf_chat

            result = import_pdf_chat(str(tmp_path), db, platform=pdf_platform,
                                     progress_cb=lambda msg: st.write(msg))

            if "error" in result:
                status.update(label="Import failed", state="error")
                st.error(result["error"])
            else:
                label = f"Imported {result['count']} messages"
                if result.get("raw_fallback"):
                    label += " (raw text — could not parse individual messages)"
                status.update(label=label, state="complete")

# ── Tab 4: ChatVault HTML ──
with tab4:
    st.markdown("### Import ChatVault Export")
    st.markdown("Point to the ChatVault `index.html` file or upload it.")

    cv_path = st.text_input(
        "Path to ChatVault index.html",
        placeholder="/path/to/ChatVault-Export/Contact/index.html",
        key="cv_path",
    )

    if cv_path and st.button("Import ChatVault"):
        if not Path(cv_path).exists():
            st.error(f"File not found: {cv_path}")
        else:
            with st.status("Importing ChatVault...", expanded=True) as status:
                from casepulse.chat_engine.importer import import_chatvault_html

                result = import_chatvault_html(cv_path, db,
                                               progress_cb=lambda msg: st.write(msg))

                if "error" in result:
                    status.update(label="Import failed", state="error")
                    st.error(result["error"])
                else:
                    status.update(
                        label=f"Imported {result['count']} messages from {result['chat_name']}",
                        state="complete",
                    )

st.divider()

# ── Imported Chats Overview ──
st.markdown("### Imported Chats")

imports = db.get_chat_imports()
if imports:
    for imp in imports:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            participants = ""
            try:
                p = json.loads(imp.get("participants", "[]"))
                participants = f" ({', '.join(p[:3])}{'...' if len(p) > 3 else ''})"
            except (json.JSONDecodeError, TypeError):
                pass
            st.markdown(f"**{imp.get('chat_name', 'Unknown')}**{participants}")
        with col2:
            st.caption(
                f"{imp['message_count']:,} msgs | "
                f"{imp.get('platform', '?')} | "
                f"{imp.get('date_start', '?')[:10]} to {imp.get('date_end', '?')[:10]}"
            )
        with col3:
            st.caption(imp.get("source_type", ""))
        with col4:
            if st.button("Delete", key=f"del_imp_{imp['id']}"):
                db.delete_chat_import(imp["id"])
                st.rerun()
else:
    st.info("No chats imported yet. Use the tabs above to import.")

st.divider()

# ── Sender Mapping ──
st.markdown("### Map Chat Senders to Case Contacts")
st.markdown("Link chat senders (names/phone numbers) to email contacts or case categories.")

sender_maps = db.get_chat_sender_maps()
categories = [
    "benefits", "cas_worker", "court", "daycare", "disclosure",
    "docusign", "employer", "ex_spouse", "expenses", "family",
    "financial", "insurance", "me", "mediator", "moving",
    "my_lawyer", "opposing_lawyer", "police", "school",
    "therapist", "travel", "witness", "other",
]

if sender_maps:
    for sm in sender_maps:
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            st.markdown(f"**{sm['chat_sender']}** ({sm.get('platform', '')})")
        with col2:
            label = st.text_input(
                "Label",
                value=sm.get("display_label", ""),
                key=f"label_{sm['id']}",
                placeholder="e.g., My ex-wife",
                label_visibility="collapsed",
            )
            if label != (sm.get("display_label") or ""):
                db.upsert_chat_sender_map(
                    sm["chat_sender"], sm.get("platform", ""),
                    sm.get("mapped_email", ""), sm.get("mapped_category", "other"),
                    label,
                )
        with col3:
            cat = st.selectbox(
                "Category",
                categories,
                index=categories.index(sm.get("mapped_category", "other")),
                key=f"smap_cat_{sm['id']}",
                label_visibility="collapsed",
            )
            if cat != sm.get("mapped_category", "other"):
                db.upsert_chat_sender_map(
                    sm["chat_sender"], sm.get("platform", ""),
                    sm.get("mapped_email", ""), cat,
                    sm.get("display_label", ""),
                )
else:
    st.caption("No chat senders found yet. Import chats first.")
