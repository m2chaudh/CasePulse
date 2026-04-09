"""Setup guide content for Microsoft and Google app registration."""
from __future__ import annotations


MICROSOFT_SETUP_GUIDE = """
### Microsoft App Registration (One-Time Setup)

This takes about 2 minutes. You need to create an "app registration" so CasePulse can
access your Outlook/Hotmail emails securely via OAuth.

**Step 1:** Open the Azure App Registration portal:

https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade

Sign in with your Microsoft account if prompted.

**Step 2:** Click **"New registration"** at the top.

**Step 3:** Fill in:
- **Name:** `CasePulse`
- **Supported account types:** Select **"Personal Microsoft accounts only"**
  (This is for Hotmail/Outlook.com accounts)
- **Redirect URI:** Select **"Public client/native (mobile & desktop)"** and enter:
  `http://localhost`

**Step 4:** Click **"Register"**

**Step 5:** On the overview page, copy the **"Application (client) ID"** — this is what you paste below.

**Step 6:** In the left menu, click **"Authentication"**:
- Under "Advanced settings", toggle **"Allow public client flows"** to **Yes**
- Click **Save**

**Step 7:** In the left menu, click **"API permissions"**:
- Click **"Add a permission"** > **"Microsoft Graph"** > **"Delegated permissions"**
- Search and add: `Mail.Read`, `User.Read`
- Click **"Add permissions"**

Done! Paste your Client ID below.
"""


GOOGLE_SETUP_GUIDE = """
### Google OAuth Setup (One-Time Setup)

This takes about 3 minutes. You need OAuth credentials so CasePulse can
access your Gmail securely.

**Step 1:** Open Google Cloud Console:

https://console.cloud.google.com/

Sign in with your Google account.

**Step 2:** Create a new project:
- Click the project dropdown at the top > **"New Project"**
- Name: `CasePulse`
- Click **"Create"**
- Select the new project from the dropdown

**Step 3:** Enable Gmail API:
- Go to **"APIs & Services"** > **"Library"** in the left menu
- Search for **"Gmail API"**
- Click on it and click **"Enable"**

**Step 4:** Configure OAuth consent screen:
- Go to **"APIs & Services"** > **"OAuth consent screen"**
- Select **"External"** (unless you have a Workspace account)
- Click **"Create"**
- Fill in App name: `CasePulse`, your email for support, and developer contact
- Click **"Save and Continue"** through all steps
- Under **"Test users"**, add your Gmail address
- Click **"Save and Continue"**

**Step 5:** Create OAuth credentials:
- Go to **"APIs & Services"** > **"Credentials"**
- Click **"Create Credentials"** > **"OAuth client ID"**
- Application type: **"Desktop app"**
- Name: `CasePulse`
- Click **"Create"**

**Step 6:** Click **"Download JSON"** on the popup that appears.

**Step 7:** Save the downloaded JSON file and upload it below.
"""


def render_microsoft_guide():
    """Render the Microsoft setup guide in Streamlit."""
    import streamlit as st
    st.markdown(MICROSOFT_SETUP_GUIDE)


def render_google_guide():
    """Render the Google setup guide in Streamlit."""
    import streamlit as st
    st.markdown(GOOGLE_SETUP_GUIDE)
