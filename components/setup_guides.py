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
- In the left menu, go to **"APIs & Services"** > **"Library"**
  (or search "Gmail API" in the top search bar)
- Click **"Gmail API"** in the results
- Click **"Enable"**

**Step 4:** Configure OAuth consent screen:
- In the left menu, go to **"APIs & Services"** > **"OAuth consent screen"**
- You should see an **Overview** page — click **"Get Started"**
- **App name:** `CasePulse`
- **User support email:** Select your email from the dropdown
- Click **"Next"**
- **Scopes:** Click **"Add or Remove Scopes"**, search for `Gmail API`,
  check **`https://www.googleapis.com/auth/gmail.readonly`**, click **"Update"**, then **"Next"**
- **Audience / User type:** Select **"External"** and click **"Next"**
  (If you don't see this step, it may default to External — that's fine)
- **Contact information:** Enter your email address
- Click **"Create"** or **"Save"**
- After creation, go to the **"Audience"** section in the left menu (under OAuth consent screen)
- Under **"Test users"**, click **"Add Users"**, enter your Gmail address, and save

**Step 5:** Create OAuth credentials:
- In the left menu, go to **"APIs & Services"** > **"Credentials"**
- Click **"Create Credentials"** at the top > **"OAuth client ID"**
- **Application type:** Select **"Desktop app"**
- **Name:** `CasePulse`
- Click **"Create"**

**Step 6:** On the popup that appears, click **"Download JSON"**.
(If you missed it, find the credential in the list and click the download icon on the right)

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
