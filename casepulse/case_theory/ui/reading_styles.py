# casepulse/case_theory/ui/reading_styles.py
"""Comprehensive theme-aware CSS injection.

Reads the active theme palette from `app_settings` (via casepulse.ui.themes)
and emits a stylesheet that overrides Streamlit's BaseWeb internals so dark
themes are fully readable and every theme actually changes the visible UI.

CSS variables are set on `:root` so deeply-nested widgets inherit them.
"""
import streamlit as st


def _build_css(t: dict) -> str:
    return f"""
:root {{
  --cp-bg:        {t["bg"]};
  --cp-bg2:       {t["bg2"]};
  --cp-bg3:       {t["bg3"]};
  --cp-text:      {t["text"]};
  --cp-muted:     {t["muted"]};
  --cp-rule:      {t["rule"]};
  --cp-primary:   {t["primary"]};
  --cp-secondary: {t["secondary"]};
  --cp-yellow:    {t["yellow"]};
  --cp-ok:        {t["ok"]};
  --cp-warn:      {t["warn"]};
  --cp-err:       {t["err"]};
  --cp-font:      {t["font"]};
  --cp-radius:    {t["radius"]};
}}

/* ===== App shell ===== */
html, body, .stApp,
[data-testid="stApp"],
[data-testid="stAppViewContainer"] {{
  background: var(--cp-bg) !important;
  color: var(--cp-text) !important;
  font-family: var(--cp-font);
}}

.main, .main .block-container {{
  background: var(--cp-bg);
  color: var(--cp-text);
  max-width: 1100px;
  font-family: var(--cp-font);
}}

header[data-testid="stHeader"], [data-testid="stHeader"] {{
  background: var(--cp-bg) !important;
  border-bottom: 1px solid var(--cp-rule);
}}
[data-testid="stToolbar"] {{ background: transparent; }}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
[data-testid="stSidebar"] > div:first-child {{
  background: var(--cp-bg2) !important;
  border-right: 1px solid var(--cp-rule);
}}

section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] a {{
  color: var(--cp-text) !important;
}}

section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {{
  color: var(--cp-muted) !important;
}}

section[data-testid="stSidebar"] [aria-current="page"],
section[data-testid="stSidebar"] a[aria-current="page"] {{
  background: var(--cp-bg3) !important;
  color: var(--cp-primary) !important;
  border-radius: var(--cp-radius);
}}

/* ===== Typography ===== */
h1, h2, h3, h4, h5, h6 {{
  color: var(--cp-text) !important;
  font-family: var(--cp-font);
  font-weight: 600;
}}

p, li,
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] * {{
  color: var(--cp-text);
  font-family: var(--cp-font);
}}

.stCaption,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] * {{
  color: var(--cp-muted) !important;
}}

hr, [data-testid="stDivider"] hr {{
  border-color: var(--cp-rule) !important;
  background: var(--cp-rule) !important;
}}

a, a:link, a:visited {{ color: var(--cp-primary) !important; }}
a:hover {{ color: var(--cp-secondary) !important; }}

/* ===== Buttons ===== */
.stButton > button,
[data-testid="stButton"] > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"] {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border: 1px solid var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
  font-family: var(--cp-font);
}}

.stButton > button:hover,
[data-testid="baseButton-secondary"]:hover {{
  background: var(--cp-bg3) !important;
  border-color: var(--cp-primary) !important;
  color: var(--cp-primary) !important;
}}

.stButton > button[kind="primary"],
[data-testid="baseButton-primary"] {{
  background: var(--cp-primary) !important;
  color: #ffffff !important;
  border-color: var(--cp-primary) !important;
}}

.stButton > button[kind="primary"]:hover,
[data-testid="baseButton-primary"]:hover {{
  background: var(--cp-secondary) !important;
  border-color: var(--cp-secondary) !important;
  color: #ffffff !important;
}}

.stButton > button:disabled {{
  opacity: 0.6;
  cursor: default;
}}

/* ===== Selectbox / Multiselect ===== */
[data-baseweb="select"] {{ font-family: var(--cp-font); }}

[data-baseweb="select"] > div,
[data-baseweb="select"] [role="combobox"] {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border-color: var(--cp-rule) !important;
}}

[data-baseweb="select"] input,
[data-baseweb="select"] [data-baseweb="tag"] {{
  color: var(--cp-text) !important;
  background: transparent !important;
}}

[data-baseweb="popover"],
[data-baseweb="popover"] > div,
[data-baseweb="menu"] {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border: 1px solid var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
}}

[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] ul {{
  background: var(--cp-bg2) !important;
}}

[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] [role="option"],
[data-baseweb="popover"] li {{
  color: var(--cp-text) !important;
  background: transparent !important;
}}

[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="popover"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] [role="option"]:hover {{
  background: var(--cp-bg3) !important;
  color: var(--cp-primary) !important;
}}

/* ===== Inputs ===== */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTimeInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border-color: var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
  font-family: var(--cp-font);
}}

[data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder,
[data-baseweb="input"] input::placeholder {{
  color: var(--cp-muted) !important;
  opacity: 1;
}}

/* ===== Radio + Checkbox ===== */
[data-testid="stRadio"] *,
[data-testid="stCheckbox"] *,
[data-testid="stRadio"] label span,
[data-testid="stCheckbox"] label span {{
  color: var(--cp-text) !important;
}}

/* ===== Expander ===== */
[data-testid="stExpander"],
details[data-testid="stExpander"] {{
  background: var(--cp-bg2) !important;
  border: 1px solid var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
}}

[data-testid="stExpander"] summary,
[data-testid="stExpander"] [role="button"],
[data-testid="stExpander"] *,
details[data-testid="stExpander"] summary span {{
  color: var(--cp-text) !important;
  font-family: var(--cp-font);
}}

/* ===== Tabs ===== */
[data-baseweb="tab-list"] {{
  background: transparent !important;
  border-bottom: 1px solid var(--cp-rule) !important;
}}

[data-baseweb="tab"] {{
  color: var(--cp-muted) !important;
  background: transparent !important;
  font-family: var(--cp-font);
}}

[data-baseweb="tab"][aria-selected="true"] {{
  color: var(--cp-primary) !important;
  border-bottom: 2px solid var(--cp-primary) !important;
}}

/* ===== Tags / pills / badges ===== */
[data-baseweb="tag"], [data-baseweb="badge"] {{
  background: var(--cp-bg3) !important;
  color: var(--cp-text) !important;
  border-color: var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
}}

/* ===== Metric tiles ===== */
[data-testid="stMetric"] {{
  background: var(--cp-bg2) !important;
  border: 1px solid var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
  padding: 14px 16px;
}}

[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{
  color: var(--cp-muted) !important;
}}

[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  color: var(--cp-primary) !important;
}}

[data-testid="stMetricDelta"], [data-testid="stMetricDelta"] * {{
  color: var(--cp-text) !important;
}}

/* ===== Alerts ===== */
[data-testid="stAlert"] {{
  border-radius: var(--cp-radius) !important;
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border: 1px solid var(--cp-rule);
}}

[data-testid="stAlert"] * {{ color: var(--cp-text) !important; }}

[data-testid="stNotification"] {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
}}

/* ===== Code blocks ===== */
pre, code,
[data-testid="stCodeBlock"],
[data-testid="stCodeBlock"] pre,
[data-testid="stCodeBlock"] code {{
  background: var(--cp-bg2) !important;
  color: var(--cp-text) !important;
  border: 1px solid var(--cp-rule);
  border-radius: var(--cp-radius);
  font-family: ui-monospace, "SF Mono", "Menlo", "Consolas", monospace;
}}

/* ===== DataFrame / table ===== */
[data-testid="stDataFrame"] table {{
  background: var(--cp-bg2);
  color: var(--cp-text);
}}

[data-testid="stDataFrame"] th {{
  background: var(--cp-bg3) !important;
  color: var(--cp-text) !important;
}}

/* ===== Slider ===== */
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
  background: var(--cp-primary) !important;
}}

/* ===== File uploader ===== */
[data-testid="stFileUploader"] section,
[data-testid="stFileUploadDropzone"] {{
  background: var(--cp-bg2) !important;
  border: 1px dashed var(--cp-rule) !important;
  color: var(--cp-text) !important;
  border-radius: var(--cp-radius) !important;
}}

/* ===== Forms (Add Entry etc.) ===== */
[data-testid="stForm"] {{
  background: var(--cp-bg2) !important;
  border: 1px solid var(--cp-rule) !important;
  border-radius: var(--cp-radius) !important;
}}

/* ===== Reading content (long-form text surfaces) ===== */
.reading-content {{
  max-width: 720px;
  margin: 0 auto;
  font-family: ui-serif, Georgia, "Charter", "Times New Roman", serif;
  line-height: 1.7;
  font-size: 1.05em;
  color: var(--cp-text);
}}
.reading-content p {{ margin: 1em 0; }}
.reading-content blockquote {{
  border-left: 3px solid var(--cp-primary);
  padding: 6px 14px;
  margin: 1em 0;
  background: var(--cp-bg3);
  color: var(--cp-text);
  font-style: italic;
  border-radius: 0 var(--cp-radius) var(--cp-radius) 0;
}}
.reading-content mark, .reading-content mark#cited-highlight {{
  background: var(--cp-yellow);
  padding: 1px 3px;
  border-radius: 2px;
  color: var(--cp-text);
}}
.reading-content pre, .reading-content code {{
  background: var(--cp-bg2);
  border: 1px solid var(--cp-rule);
  color: var(--cp-text);
  border-radius: var(--cp-radius);
}}

/* ===== Dashboard helpers ===== */
.main-header {{
  font-size: 2.2rem;
  font-weight: 700;
  margin-bottom: 0;
  color: var(--cp-text);
  font-family: var(--cp-font);
}}
.sub-header {{
  font-size: 1rem;
  color: var(--cp-muted);
  margin-top: -10px;
  margin-bottom: 30px;
}}
.stat-card {{
  background: var(--cp-bg2);
  border-radius: var(--cp-radius);
  padding: 18px;
  text-align: center;
  border: 1px solid var(--cp-rule);
}}
.stat-number {{
  font-size: 1.9rem;
  font-weight: 700;
  color: var(--cp-primary);
}}
.stat-label {{
  font-size: 0.85rem;
  color: var(--cp-text);
  margin-top: 4px;
}}
.status-ok   {{ color: var(--cp-ok); }}
.status-warn {{ color: var(--cp-warn); }}
.status-err  {{ color: var(--cp-err); }}
"""


def inject_global() -> None:
    """Inject theme-aware CSS once per Streamlit page render."""
    from casepulse.ui.themes import get_active_theme, THEMES, DEFAULT_THEME

    db = st.session_state.get("db")
    theme = get_active_theme(db) if db is not None else THEMES[DEFAULT_THEME]
    st.markdown(f"<style>{_build_css(theme)}</style>", unsafe_allow_html=True)


def build_inject_block() -> str:
    """Return the <style>...</style> string for the active theme."""
    from casepulse.ui.themes import get_active_theme, THEMES, DEFAULT_THEME

    db = st.session_state.get("db") if hasattr(st, "session_state") else None
    theme = get_active_theme(db) if db is not None else THEMES[DEFAULT_THEME]
    return f"<style>{_build_css(theme)}</style>"


def _default_css() -> str:
    """Return the CSS rendered against the default theme. Used by tests."""
    from casepulse.ui.themes import THEMES, DEFAULT_THEME
    return _build_css(THEMES[DEFAULT_THEME])


# Backward-compat module-level constant for tests that import GLOBAL_CSS.
GLOBAL_CSS = _default_css()
