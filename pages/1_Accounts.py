"""Accounts page — Connect and manage email accounts."""
import streamlit as st
import sys
import json
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from casepulse.config import get_data_dir

st.set_page_config(page_title="CasePulse - Accounts", page_icon="CP", layout="wide")

st.markdown("## Accounts")
st.markdown("Connect your Outlook, Hotmail, and Gmail accounts. You can add multiple accounts of each type.")


from components.page_init import init_page
db, config = init_page()

# Track how many accounts have been added (used to reset email input key)
if "ms_add_counter" not in st.session_state:
    st.session_state.ms_add_counter = 0
if "google_add_counter" not in st.session_state:
    st.session_state.google_add_counter = 0

# ── Show connected accounts ──
accounts = db.get_accounts()
if accounts:
    st.markdown("### Connected Accounts")
    for acc in accounts:
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            provider_label = "Microsoft" if acc["provider"] == "microsoft" else "Google"
            st.markdown(f"**{provider_label}** — {acc['email']}")
        with col2:
            synced = acc.get("last_synced", "Never")
            st.caption(f"Last synced: {synced or 'Never'}")
        with col3:
            if st.button("Remove", key=f"remove_{acc['id']}"):
                db.delete_account(acc["id"])
                config.remove_account(acc["provider"], acc["email"])
                token_dir = get_data_dir() / "tokens"
                safe = acc["email"].replace("@", "_at_").replace(".", "_")
                for f in token_dir.glob(f"*{safe}*"):
                    f.unlink()
                st.rerun()
    st.divider()

ms_accounts = [a for a in accounts if a["provider"] == "microsoft"]
google_accounts = [a for a in accounts if a["provider"] == "google"]

# ── Resolve persisted Microsoft Client ID ──
# Check if we already have a client_id from a previously connected account
saved_ms_client_id = ""
if ms_accounts:
    saved_ms_client_id = ms_accounts[0].get("client_id", "")

# ── Add Microsoft Account ──
st.markdown("### Add Microsoft Account (Outlook / Hotmail)")
if ms_accounts:
    st.caption(f"{len(ms_accounts)} Microsoft account(s) connected. You can add more below.")

with st.expander("Setup Guide — Microsoft App Registration", expanded=not ms_accounts):
    from components.setup_guides import render_microsoft_guide
    render_microsoft_guide()

# Pre-fill client ID from previously connected account
ms_key = st.session_state.ms_add_counter
ms_client_id = st.text_input(
    "Microsoft Application (Client) ID",
    value=saved_ms_client_id,
    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    key=f"ms_client_id_{ms_key}",
    help="From your Azure App Registration overview page. Reused automatically from your first account.",
)
ms_email_hint = st.text_input(
    "Email address (Outlook/Hotmail)",
    placeholder="you@outlook.com or you@hotmail.com",
    key=f"ms_email_{ms_key}",
    help="The specific email account to connect",
)

if st.button("Connect Microsoft Account", disabled=not ms_client_id, key=f"ms_connect_{ms_key}"):
    if len(ms_client_id) < 10:
        st.error("Please enter a valid Client ID from your Azure App Registration.")
    else:
        with st.status("Authenticating with Microsoft...", expanded=True) as status:
            try:
                from casepulse.auth.microsoft import MicrosoftAuth
                auth = MicrosoftAuth(client_id=ms_client_id, account_email=ms_email_hint)

                st.write("Opening browser for sign-in...")
                if ms_email_hint:
                    st.warning(
                        f"**Important:** When the browser opens, make sure you sign in with "
                        f"**{ms_email_hint}**, not a different Microsoft account. "
                        f"If your browser auto-signs in with the wrong account, "
                        f"click your profile icon in the browser and choose "
                        f"'Sign in with a different account'."
                    )

                result = auth.authenticate_interactive(
                    callback=lambda msg: st.write(msg)
                )

                if "error" in result:
                    status.update(label="Authentication failed", state="error")
                    st.error(result["error"])
                    st.info("To try again, just click 'Connect Microsoft Account' again.")
                else:
                    email = result["account_email"] or ms_email_hint

                    # Check if we authenticated with the right account
                    if ms_email_hint and email.lower() != ms_email_hint.lower():
                        status.update(label="Wrong account", state="error")
                        st.error(
                            f"You signed in with **{email}** but you entered "
                            f"**{ms_email_hint}**. The wrong account was authenticated.\n\n"
                            f"Please try again and make sure to sign in with "
                            f"**{ms_email_hint}** in the browser."
                        )
                    else:
                        display_name = result.get("display_name", "")
                        db.add_account(
                            provider="microsoft",
                            email=email,
                            display_name=display_name,
                            client_id=ms_client_id,
                        )
                        config.add_microsoft_account(email, ms_client_id)

                        status.update(label=f"Connected: {email}", state="complete")
                        st.success(f"Successfully connected {email}!")
                        st.session_state.ms_add_counter += 1
                        st.rerun()

            except Exception as e:
                status.update(label="Error", state="error")
                st.error(f"Authentication error: {str(e)}")
                st.info("To try again, just click 'Connect Microsoft Account' again.")

st.divider()

# ── Resolve persisted Google credentials ──
# Check if we already have a credentials file from a previously connected account
saved_google_creds_path = ""
if google_accounts:
    # Reuse the credentials file from the first Google account
    first_google = google_accounts[0]
    candidate = first_google.get("token_file", "")
    if candidate and Path(candidate).exists():
        saved_google_creds_path = candidate

# Also check for any google_creds_*.json file in the tokens directory
if not saved_google_creds_path:
    token_dir = get_data_dir() / "tokens"
    creds_files = list(token_dir.glob("google_creds_*.json"))
    if creds_files:
        saved_google_creds_path = str(creds_files[0])

# ── Add Google Account ──
st.markdown("### Add Gmail Account")
if google_accounts:
    st.caption(f"{len(google_accounts)} Gmail account(s) connected. You can add more below.")

with st.expander("Setup Guide — Google OAuth Credentials", expanded=not google_accounts):
    from components.setup_guides import render_google_guide
    render_google_guide()

google_key = st.session_state.google_add_counter

if saved_google_creds_path:
    st.success(f"Google OAuth credentials on file: `{Path(saved_google_creds_path).name}`")
    use_saved = st.checkbox("Use saved credentials", value=True, key=f"use_saved_google_{google_key}")

    if not use_saved:
        google_creds_file = st.file_uploader(
            "Upload new Google OAuth credentials JSON",
            type=["json"],
            key=f"google_creds_{google_key}",
        )
    else:
        google_creds_file = None  # Will use saved path
else:
    use_saved = False
    google_creds_file = st.file_uploader(
        "Upload Google OAuth credentials JSON",
        type=["json"],
        key=f"google_creds_{google_key}",
        help="Download this from Google Cloud Console > APIs & Services > Credentials.",
    )

google_email_hint = st.text_input(
    "Gmail address",
    placeholder="you@gmail.com",
    key=f"google_email_{google_key}",
    help="The specific Gmail account to connect",
)

can_connect_google = (use_saved and saved_google_creds_path) or (google_creds_file is not None)

if st.button("Connect Gmail Account", disabled=not can_connect_google, key=f"google_connect_{google_key}"):
    with st.status("Authenticating with Google...", expanded=True) as status:
        try:
            creds_dir = get_data_dir() / "tokens"

            if use_saved and saved_google_creds_path:
                # Reuse existing credentials file
                creds_path = Path(saved_google_creds_path)
                st.write(f"Using saved credentials: {creds_path.name}")
            else:
                # Save newly uploaded credentials file
                safe_email = google_email_hint.replace("@", "_at_").replace(".", "_") if google_email_hint else "default"
                creds_path = creds_dir / f"google_creds_{safe_email}.json"
                creds_content = google_creds_file.read()
                creds_path.write_bytes(creds_content)

            from casepulse.auth.google_auth import GoogleAuth
            auth = GoogleAuth(
                credentials_file=str(creds_path),
                account_email=google_email_hint,
            )

            st.write("Opening browser for Google sign-in...")
            if google_email_hint:
                st.info(f"Sign in with **{google_email_hint}** in the browser window.")

            result = auth.authenticate_interactive(
                callback=lambda msg: st.write(msg)
            )

            if "error" in result:
                status.update(label="Authentication failed", state="error")
                st.error(result["error"])
            else:
                email = result["account_email"] or google_email_hint
                db.add_account(
                    provider="google",
                    email=email,
                    display_name="",
                    token_file=str(creds_path),
                )
                config.add_google_account(email, str(creds_path))

                status.update(label=f"Connected: {email}", state="complete")
                st.success(f"Successfully connected {email}!")
                st.session_state.google_add_counter += 1
                st.rerun()

        except Exception as e:
            status.update(label="Error", state="error")
            st.error(f"Authentication error: {str(e)}")
