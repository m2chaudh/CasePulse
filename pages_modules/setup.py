"""First-run setup wizard — module selection."""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="CasePulse - Setup", page_icon="CP", layout="wide")

from casepulse.setup_wizard import (
    MODULES, is_setup_complete, load_installed_modules,
    save_installed_modules, get_default_selections,
)
from casepulse.case_theory.ui import page_help
from casepulse.storage.database import Database
from casepulse.ui.workflow_help import (
    compute_workflow_state, render_workflow_help, WorkflowState,
)
from casepulse.ui.themes import render_theme_picker

# If setup is already done, show settings view
setup_done = is_setup_complete()

# Render workflow help at the top of the page
_db = Database()
with _db._get_conn() as _conn:
    _row = _conn.execute("SELECT id FROM cases ORDER BY id LIMIT 1").fetchone()
if _row:
    _wstate = compute_workflow_state(_db, case_id=_row["id"])
    render_workflow_help(
        _wstate,
        default_open=not (_wstate.has_email or _wstate.has_document),
    )
else:
    render_workflow_help(WorkflowState(), default_open=True)

# Theme picker — also exposed in the sidebar (🎨 Theme expander) for
# every page; this Setup-page version is more prominent.
st.markdown("---")
st.markdown("### 🎨 Appearance — Theme")
render_theme_picker(_db)
st.markdown("---")

if setup_done:
    st.markdown("## Module Settings")
    st.markdown("Enable or disable optional modules. Changes take effect on next restart.")
else:
    st.markdown("## Welcome to CasePulse")
    st.markdown("Select the modules you want to enable. You can change this later in Setup.")
    st.info("Core features (Accounts, Email Fetch, Timeline, Import Chats, Cases, Export) are always included.")

page_help.render("setup")

current = load_installed_modules() if setup_done else get_default_selections()

st.divider()

selections = {}
total_size = 200  # Core size in MB

for key, mod in MODULES.items():
    col1, col2, col3 = st.columns([0.5, 3, 1])
    with col1:
        enabled = st.checkbox(
            mod["name"],
            value=current.get(key, mod["default"]),
            key=f"mod_{key}",
            label_visibility="collapsed",
        )
        selections[key] = enabled
    with col2:
        st.markdown(f"**{mod['name']}**")
        st.caption(mod["description"])
    with col3:
        st.caption(f"~{mod['size']}")

    if enabled:
        size_str = mod["size"].split()[0]
        try:
            total_size += int(size_str)
        except ValueError:
            pass

st.divider()
st.markdown(f"**Estimated install size:** ~{total_size} MB")

if setup_done:
    if st.button("Save Changes", type="primary"):
        save_installed_modules(selections)
        st.success("Module settings saved. Restart CasePulse for changes to take effect.")
else:
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Get Started", type="primary"):
            save_installed_modules(selections)
            st.balloons()
            st.success("Setup complete! Navigate to **Accounts** to connect your email.")
            st.rerun()
    with col2:
        st.caption("You can change these settings anytime from the Setup page.")


# ── ChatVault Exports ─────────────────────────────────────────────────────
st.divider()
st.markdown("## ChatVault Exports")
st.caption(
    "Register a folder produced by ChatVault (`chatvault appclose <pdf>` "
    "or the WhatsApp pipeline). CasePulse symlinks it under `static/` "
    "so Streamlit serves it, then indexes the `msg-N` anchors against "
    "your `chat_messages` rows. The day-drawer chat clusters get "
    "**View in ChatVault →** buttons that jump to the right message."
)

from casepulse.chatvault_integration import (
    get_scan_parent, set_scan_parent, scan_for_exports,
    list_exports, register_export, remove_export, url_for,
)
from casepulse.scripts.index_chatvault_export import index_export

_cv_db = _db

# Parent folder
_current_parent = get_scan_parent(_cv_db)
new_parent = st.text_input(
    "Parent folder to scan for exports",
    value=_current_parent,
    placeholder="/Users/you/Documents/ChatVault-output/",
    key="cv_scan_parent",
    help="A folder containing one subfolder per ChatVault export. Each "
         "subfolder must contain an `index.html`.",
)
col_save, col_refresh = st.columns([1, 4])
with col_save:
    if st.button("Save parent", key="cv_save_parent"):
        set_scan_parent(_cv_db, new_parent)
        st.rerun()

# Existing exports
_exports = list_exports(_cv_db)
if _exports:
    st.markdown("### Registered exports")
    for exp in _exports:
        with st.container(border=True):
            cols = st.columns([3, 2, 1, 1, 1])
            with cols[0]:
                st.markdown(f"**{exp['name']}**")
                st.caption(
                    f"{exp['platform']} · {exp['chat_name'] or '(no chat name)'}"
                )
                st.caption(f"`{exp['source_dir']}`")
            with cols[1]:
                last = exp["last_indexed_at"] or "never"
                st.caption(
                    f"Indexed: **{last}**"
                    + (f" · {exp['message_count']} msgs"
                       if exp["message_count"] else "")
                )
            with cols[2]:
                if st.button("Re-index", key=f"cv_reidx_{exp['id']}"):
                    stats = index_export(_cv_db, exp["id"])
                    if "error" in stats:
                        st.error(stats["error"])
                    else:
                        st.success(
                            f"{stats['matched']} matched · "
                            f"{stats['unmatched_cv']} CV unmatched · "
                            f"{stats['unmatched_cm']} CM unmatched"
                        )
                        st.rerun()
            with cols[3]:
                st.markdown(
                    f"[Open ↗]({url_for(exp['name'])})",
                    help="Open the export in a new browser tab.",
                )
            with cols[4]:
                if st.button("Remove", key=f"cv_rm_{exp['id']}"):
                    remove_export(_cv_db, exp["id"])
                    st.rerun()
else:
    st.info("No ChatVault exports registered yet.")

# Scan + register
if new_parent:
    _candidates = scan_for_exports(new_parent)
    _registered_paths = {e["source_dir"] for e in _exports}
    _unregistered = [
        c for c in _candidates if c["path"] not in _registered_paths
    ]
    if _unregistered:
        st.markdown("### Available to register")
        for c in _unregistered:
            with st.container(border=True):
                cols = st.columns([3, 2, 1])
                with cols[0]:
                    st.markdown(f"**{c['name']}**")
                    st.caption(
                        f"{c['platform'] or 'unknown'} · "
                        f"{c['chat_name'] or '(no chat name)'}"
                    )
                    st.caption(f"`{c['path']}`")
                with cols[1]:
                    reg_name = st.text_input(
                        "Register as",
                        value=(
                            f"{c['chat_name']} ({c['platform']})"
                            if c['chat_name'] and c['platform']
                            else c['name']
                        ),
                        key=f"cv_regname_{c['name']}",
                        label_visibility="collapsed",
                    )
                with cols[2]:
                    if st.button("Register",
                                  key=f"cv_reg_{c['name']}",
                                  type="primary"):
                        try:
                            new_id = register_export(
                                _cv_db, reg_name, c["path"],
                            )
                            stats = index_export(_cv_db, new_id)
                            st.success(
                                f"Registered + indexed: "
                                f"{stats['matched']} matches"
                            )
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
    elif _candidates:
        st.caption(
            f"All {len(_candidates)} candidate folder(s) under that "
            f"parent are already registered."
        )
    else:
        st.caption(
            "No candidate folders found (need a subfolder containing "
            "`index.html`)."
        )
