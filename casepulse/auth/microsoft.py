"""Microsoft OAuth authentication using MSAL for Outlook/Hotmail accounts."""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Optional

import msal

from casepulse.config import get_data_dir

# Permissions needed to read mail
SCOPES = ["Mail.Read", "Mail.ReadBasic", "User.Read"]

# Authority for personal Microsoft accounts (Hotmail, Outlook.com)
AUTHORITY = "https://login.microsoftonline.com/consumers"


class MicrosoftAuth:
    """Handles Microsoft OAuth2 authentication for personal accounts.

    Each account gets its own separate token cache file to avoid
    cross-account token confusion.
    """

    def __init__(self, client_id: str, account_email: str = ""):
        self.client_id = client_id
        self.account_email = account_email
        self._token_dir = get_data_dir() / "tokens"
        self._token_dir.mkdir(parents=True, exist_ok=True)
        self._cache = msal.SerializableTokenCache()
        self._load_cache()
        self._app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=AUTHORITY,
            token_cache=self._cache,
        )

    def _cache_path(self) -> Path:
        safe_email = self.account_email.replace("@", "_at_").replace(".", "_")
        return self._token_dir / f"ms_{safe_email}.json"

    def _load_cache(self):
        cache_file = self._cache_path()
        if cache_file.exists():
            self._cache.deserialize(cache_file.read_text())

    def _save_cache(self):
        if self._cache.has_state_changed:
            self._cache_path().write_text(self._cache.serialize())

    def _find_matching_account(self):
        """Find the MSAL cached account matching self.account_email."""
        accounts = self._app.get_accounts()
        if not accounts:
            return None
        if self.account_email:
            for acc in accounts:
                username = acc.get("username", "").lower()
                if username == self.account_email.lower():
                    return acc
        # Only return first account if we have exactly one (no ambiguity)
        if len(accounts) == 1:
            return accounts[0]
        return None

    def get_token_silent(self) -> Optional[str]:
        """Try to get a token silently from cache for THIS specific account."""
        account = self._find_matching_account()
        if not account:
            return None
        result = self._app.acquire_token_silent(SCOPES, account=account)
        if result and "access_token" in result:
            self._save_cache()
            return result["access_token"]
        return None

    def authenticate_interactive(self, callback=None) -> dict:
        """Run interactive OAuth flow via browser.

        Always uses device code flow for new accounts. Only uses silent
        auth if we find a cached token matching this exact email.

        Args:
            callback: Optional function(status: str) for progress updates.

        Returns:
            dict with 'access_token', 'account_email', 'display_name' on success,
            or 'error' key on failure.
        """
        # Try silent only if we have a specific email to match
        if self.account_email:
            token = self.get_token_silent()
            if token:
                account = self._find_matching_account()
                if account:
                    return {
                        "access_token": token,
                        "account_email": account.get("username", self.account_email),
                        "display_name": account.get("name", ""),
                    }

        # Device code flow — always prompts user to sign in
        if callback:
            callback("Initiating device code flow...")

        flow = self._app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            return {"error": f"Could not initiate auth flow: {flow.get('error_description', 'Unknown error')}"}

        # Open browser for user
        auth_uri = flow.get("verification_uri", "https://microsoft.com/devicelogin")
        webbrowser.open(auth_uri)

        if callback:
            callback(f"Enter code: {flow['user_code']}")

        # Wait for user to complete auth (blocks until done or timeout)
        result = self._app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            # Find the account that was just authenticated
            accounts = self._app.get_accounts()
            email = ""
            display_name = ""

            if accounts:
                # Find the newly added account (might not be accounts[0])
                # The token result contains id_token_claims with the email
                claims = result.get("id_token_claims", {})
                preferred = claims.get("preferred_username", "")

                if preferred:
                    email = preferred
                    for acc in accounts:
                        if acc.get("username", "").lower() == preferred.lower():
                            display_name = acc.get("name", "")
                            break
                else:
                    # Fallback: use the last account added
                    email = accounts[-1].get("username", "")
                    display_name = accounts[-1].get("name", "")

            self.account_email = email or self.account_email
            self._save_cache()

            return {
                "access_token": result["access_token"],
                "account_email": email,
                "display_name": display_name,
            }

        return {"error": result.get("error_description", "Authentication failed")}

    def get_access_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if needed."""
        return self.get_token_silent()

    def is_authenticated(self) -> bool:
        """Check if we have a valid cached token."""
        return self.get_token_silent() is not None

    def logout(self):
        """Remove cached tokens."""
        cache_file = self._cache_path()
        if cache_file.exists():
            cache_file.unlink()
        self._cache = msal.SerializableTokenCache()
        self._app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=AUTHORITY,
            token_cache=self._cache,
        )

    def get_user_info(self, access_token: str) -> dict:
        """Get user profile info from Microsoft Graph."""
        import requests
        resp = requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            return {
                "email": data.get("mail") or data.get("userPrincipalName", ""),
                "display_name": data.get("displayName", ""),
            }
        return {}
