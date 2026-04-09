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
st.markdown("Connect your Outlook, Hotmail, and Gmail accounts.")


from components.page_init import init_page
db, config = init_page()

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
                # Clean up token files
                token_dir = get_data_dir() / "tokens"
                safe = acc["email"].replace("@", "_at_").replace(".", "_")
                for f in token_dir.glob(f"*{safe}*"):
                    f.unlink()
                st.rerun()
    st.divider()

# ── Add Microsoft Account ──
st.markdown("### Add Microsoft Account (Outlook / Hotmail)")

with st.expander("Setup Guide — Microsoft App Registration", expanded=not any(
    a["provider"] == "microsoft" for a in accounts
)):
    from components.setup_guides import render_microsoft_guide
    render_microsoft_guide()

ms_client_id = st.text_input(
    "Microsoft Application (Client) ID",
    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    key="ms_client_id",
    help="From your Azure App Registration overview page",
)

ms_email_hint = st.text_input(
    "Email address (Outlook/Hotmail)",
    placeholder="you@outlook.com or you@hotmail.com",
    key="ms_email",
    help="The email address for this account",
)

if st.button("Connect Microsoft Account", disabled=not ms_client_id):
    if not ms_client_id or len(ms_client_id) < 10:
        st.error("Please enter a valid Client ID from your Azure App Registration.")
    else:
        with st.status("Authenticating with Microsoft...", expanded=True) as status:
            try:
                from casepulse.auth.microsoft import MicrosoftAuth
                auth = MicrosoftAuth(client_id=ms_client_id, account_email=ms_email_hint)

                st.write("Opening browser for sign-in...")
                st.write("A code will appear below — enter it in the browser window.")

                result = auth.authenticate_interactive(
                    callback=lambda msg: st.write(msg)
                )

                if "error" in result:
                    status.update(label="Authentication failed", state="error")
                    st.error(result["error"])
                else:
                    email = result["account_email"] or ms_email_hint
                    display_name = result.get("display_name", "")

                    # Save to database
                    db.add_account(
                        provider="microsoft",
                        email=email,
                        display_name=display_name,
                        client_id=ms_client_id,
                    )
                    config.add_microsoft_account(email, ms_client_id)

                    status.update(label=f"Connected: {email}", state="complete")
                    st.success(f"Successfully connected {email}!")
                    st.rerun()

            except Exception as e:
                status.update(label="Error", state="error")
                st.error(f"Authentication error: {str(e)}")

st.divider()

# ── Add Google Account ──
st.markdown("### Add Gmail Account")

with st.expander("Setup Guide — Google OAuth Credentials", expanded=not any(
    a["provider"] == "google" for a in accounts
)):
    from components.setup_guides import render_google_guide
    render_google_guide()

google_creds_file = st.file_uploader(
    "Upload Google OAuth credentials JSON",
    type=["json"],
    key="google_creds",
    help="Download this from Google Cloud Console > APIs & Services > Credentials",
)

google_email_hint = st.text_input(
    "Gmail address",
    placeholder="you@gmail.com",
    key="google_email",
    help="The Gmail address for this account",
)

if st.button("Connect Gmail Account", disabled=google_creds_file is None):
    if google_creds_file is None:
        st.error("Please upload your Google OAuth credentials JSON file.")
    else:
        with st.status("Authenticating with Google...", expanded=True) as status:
            try:
                # Save credentials file
                creds_dir = get_data_dir() / "tokens"
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
                    st.rerun()

            except Exception as e:
                status.update(label="Error", state="error")
                st.error(f"Authentication error: {str(e)}")
