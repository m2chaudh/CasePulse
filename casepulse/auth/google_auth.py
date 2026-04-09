"""Google OAuth authentication for Gmail accounts."""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from casepulse.config import get_data_dir

# Read-only access to Gmail
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

REDIRECT_PORT = 8401


class GoogleAuth:
    """Handles Google OAuth2 authentication for Gmail accounts."""

    def __init__(self, credentials_file: str, account_email: str = ""):
        self.credentials_file = credentials_file
        self.account_email = account_email
        self._token_dir = get_data_dir() / "tokens"
        self._token_dir.mkdir(parents=True, exist_ok=True)

    def _token_path(self) -> Path:
        safe_email = self.account_email.replace("@", "_at_").replace(".", "_")
        return self._token_dir / f"google_{safe_email}.json"

    def _load_credentials(self) -> Optional[Credentials]:
        """Load saved credentials from disk."""
        token_file = self._token_path()
        if not token_file.exists():
            return None
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        return creds

    def _save_credentials(self, creds: Credentials):
        """Save credentials to disk."""
        token_file = self._token_path()
        token_file.write_text(creds.to_json())

    def get_credentials(self) -> Optional[Credentials]:
        """Get valid credentials, refreshing if needed."""
        creds = self._load_credentials()
        if creds and creds.valid:
            return creds
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds)
                return creds
            except Exception:
                return None
        return None

    def authenticate_interactive(self, callback=None) -> dict:
        """Run interactive OAuth flow via browser.

        Args:
            callback: Optional function(status: str) for progress updates.

        Returns:
            dict with 'credentials', 'account_email' on success,
            or 'error' key on failure.
        """
        # Try cached credentials first
        creds = self.get_credentials()
        if creds:
            email = self._get_email_from_creds(creds)
            return {
                "credentials": creds,
                "account_email": email or self.account_email,
            }

        # Need fresh authentication
        if not Path(self.credentials_file).exists():
            return {
                "error": f"Credentials file not found: {self.credentials_file}\n"
                         "Download it from Google Cloud Console > APIs & Services > Credentials"
            }

        if callback:
            callback("Opening browser for Google sign-in...")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                scopes=SCOPES,
            )
            # Run local server to handle redirect
            creds = flow.run_local_server(
                port=REDIRECT_PORT,
                prompt="consent",
                authorization_prompt_message="",
            )

            # Get the user's email
            email = self._get_email_from_creds(creds)
            self.account_email = email or self.account_email
            self._save_credentials(creds)

            if callback:
                callback(f"Authenticated as {self.account_email}")

            return {
                "credentials": creds,
                "account_email": self.account_email,
            }

        except Exception as e:
            return {"error": f"Google authentication failed: {str(e)}"}

    def _get_email_from_creds(self, creds: Credentials) -> str:
        """Get user email from Gmail API using credentials."""
        try:
            from googleapiclient.discovery import build
            service = build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            return profile.get("emailAddress", "")
        except Exception:
            return ""

    def is_authenticated(self) -> bool:
        """Check if we have valid cached credentials."""
        creds = self.get_credentials()
        return creds is not None and creds.valid

    def logout(self):
        """Remove cached tokens."""
        token_file = self._token_path()
        if token_file.exists():
            token_file.unlink()

    def get_service(self):
        """Get an authenticated Gmail API service object."""
        creds = self.get_credentials()
        if not creds:
            return None
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=creds)
