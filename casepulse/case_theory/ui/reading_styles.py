# casepulse/case_theory/ui/reading_styles.py
"""Global CSS injection for reading-friendly typography.

Reads the active theme palette from `app_settings` (via `casepulse.ui.themes`)
on every render, so switching themes via the picker re-renders the whole app
in the new palette instantly.
"""
import streamlit as st


def _build_css(theme: dict) -> str:
    """Build the CSS string against a theme palette dict."""
    return f"""
/* Body — match the active theme so Streamlit's white default doesn't peek through */
html, body, [data-testid="stApp"] {{
  background: {theme["bg"]} !important;
  color: {theme["text"]};
}}

/* Moderate page width — readable on wide screens */
.main .block-container {{
  max-width: 1100px;
  background: {theme["bg"]};
}}

/* Tight reading column for long-form text */
.reading-content {{
  max-width: 720px;
  margin: 0 auto;
  font-family: ui-serif, Georgia, "Charter", "Times New Roman", serif;
  line-height: 1.7;
  font-size: 1.05em;
  color: {theme["text"]};
}}

.reading-content p {{
  margin: 1em 0;
}}

.reading-content blockquote {{
  border-left: 3px solid {theme["primary"]};
  padding: 6px 14px;
  margin: 1em 0;
  background: {theme["quote_bg"]};
  color: {theme["text"]};
  font-style: italic;
  border-radius: 0 4px 4px 0;
}}

.reading-content mark,
.reading-content mark#cited-highlight {{
  background: {theme["yellow"]};
  padding: 1px 3px;
  border-radius: 2px;
  color: {theme["text"]};
}}

.reading-content pre {{
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: ui-monospace, "SF Mono", "Menlo", "Consolas", monospace;
  line-height: 1.6;
  font-size: 0.95em;
  background: {theme["bg2"]};
  padding: 10px 14px;
  border-radius: 4px;
  border: 1px solid {theme["rule"]};
}}

.reading-content code {{
  font-family: ui-monospace, "SF Mono", "Menlo", monospace;
  background: {theme["bg2"]};
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.93em;
  color: {theme["text"]};
}}

/* Soften Streamlit chrome */
header[data-testid="stHeader"] {{
  background: transparent;
}}

/* Sidebar — secondary background as a panel */
section[data-testid="stSidebar"] {{
  background: {theme["bg2"]};
  border-right: 1px solid {theme["rule"]};
}}
section[data-testid="stSidebar"] * {{
  color: {theme["text"]};
}}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
  color: {theme["muted"]} !important;
}}

/* Dividers */
hr, [data-testid="stDivider"] hr {{
  border-color: {theme["rule"]} !important;
}}

/* Headings — inherit theme text color, slightly reduced weight */
h1, h2, h3, h4, h5, h6 {{
  color: {theme["text"]};
  font-weight: 600;
}}

/* Captions */
.stCaption, [data-testid="stCaptionContainer"] {{
  color: {theme["muted"]} !important;
}}

/* Buttons — softer corners */
.stButton > button {{
  border-radius: 4px;
}}

/* Metric tiles harmonise */
[data-testid="stMetric"] {{
  background: {theme["bg2"]};
  border-radius: 8px;
  padding: 14px 16px;
  border: 1px solid {theme["rule"]};
}}
[data-testid="stMetricLabel"] {{
  color: {theme["muted"]} !important;
}}
[data-testid="stMetricValue"] {{
  color: {theme["primary"]} !important;
}}

/* Dashboard helpers — defined once globally so dashboard.py can drop its inline <style> */
.main-header {{
  font-size: 2.2rem;
  font-weight: 700;
  margin-bottom: 0;
  color: {theme["text"]};
}}
.sub-header {{
  font-size: 1rem;
  color: {theme["muted"]};
  margin-top: -10px;
  margin-bottom: 30px;
}}
.stat-card {{
  background: {theme["bg2"]};
  border-radius: 8px;
  padding: 18px;
  text-align: center;
  border: 1px solid {theme["rule"]};
}}
.stat-number {{
  font-size: 1.9rem;
  font-weight: 700;
  color: {theme["primary"]};
}}
.stat-label {{
  font-size: 0.85rem;
  color: {theme["text"]};
  margin-top: 4px;
}}
.status-ok   {{ color: {theme["ok"]}; }}
.status-warn {{ color: {theme["warn"]}; }}
.status-err  {{ color: {theme["err"]}; }}
"""


def inject_global() -> None:
    """Inject the reading-friendly CSS once per Streamlit page render.

    Reads the active theme from `app_settings` via the database in
    `st.session_state.db` if available, otherwise falls back to the default
    theme.
    """
    from casepulse.ui.themes import get_active_theme, THEMES, DEFAULT_THEME

    db = st.session_state.get("db")
    theme = get_active_theme(db) if db is not None else THEMES[DEFAULT_THEME]
    st.markdown(f"<style>{_build_css(theme)}</style>", unsafe_allow_html=True)


def build_inject_block() -> str:
    """Legacy helper — returns the <style>...</style> string for the active theme."""
    from casepulse.ui.themes import get_active_theme, THEMES, DEFAULT_THEME

    db = st.session_state.get("db") if hasattr(st, "session_state") else None
    theme = get_active_theme(db) if db is not None else THEMES[DEFAULT_THEME]
    return f"<style>{_build_css(theme)}</style>"


def _default_css() -> str:
    """Return the CSS rendered against the default theme.
    Module-level convenience used by tests and by callers that want a
    deterministic snapshot independent of any user setting."""
    from casepulse.ui.themes import THEMES, DEFAULT_THEME
    return _build_css(THEMES[DEFAULT_THEME])


# Backward-compatible module-level constant — represents the default theme's
# CSS. Tests and external callers that import GLOBAL_CSS keep working; live
# rendering goes through `inject_global()` which reads the user's active theme.
GLOBAL_CSS = _default_css()
