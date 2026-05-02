# casepulse/case_theory/ui/reading_styles.py
"""Global CSS injection for reading-friendly typography.

Two scopes:
1. Global moderate max-width — pages stop stretching to 1440px+ on wide screens
2. Tight `.reading-content` class — for long-form text surfaces (View source dialog,
   Argument editor reasoning, document body, brief preview)

Colors harmonise with the Solarized Light Streamlit theme set in
`.streamlit/config.toml`. The Solarized palette was designed scientifically
for low-strain reading; the constants below reuse its named hex values.
"""
import streamlit as st


# Solarized Light palette — kept named so swapping the theme
# (e.g. to Solarized Dark) only requires changing this block.
SOL_BG       = "#fdf6e3"   # base3  — main background
SOL_BG2      = "#eee8d5"   # base2  — secondary surface
SOL_TEXT     = "#586e75"   # base01 — body text
SOL_TEXT_MUT = "#93a1a1"   # base1  — muted / metadata
SOL_RULE     = "#d3cbb7"   # blend  — subtle dividers / borders
SOL_BLUE     = "#268bd2"   # blue   — links, primary actions
SOL_YELLOW   = "#fbedc4"   # yellow tint — soft highlight (mark)
SOL_QUOTE_BG = "#f5efd5"   # very light cream — blockquote panel


GLOBAL_CSS = f"""
/* Moderate global max-width — let pages breathe instead of stretching to 1440px */
.main .block-container {{
  max-width: 1100px;
}}

/* Tight reading column for long-form text */
.reading-content {{
  max-width: 720px;
  margin: 0 auto;
  font-family: ui-serif, Georgia, "Charter", "Times New Roman", serif;
  line-height: 1.7;
  font-size: 1.05em;
  color: {SOL_TEXT};
}}

.reading-content p {{
  margin: 1em 0;
}}

.reading-content blockquote {{
  border-left: 3px solid {SOL_BLUE};
  padding: 6px 14px;
  margin: 1em 0;
  background: {SOL_QUOTE_BG};
  color: {SOL_TEXT};
  font-style: italic;
  border-radius: 0 4px 4px 0;
}}

.reading-content mark,
.reading-content mark#cited-highlight {{
  background: {SOL_YELLOW};
  padding: 1px 3px;
  border-radius: 2px;
  color: {SOL_TEXT};
}}

.reading-content pre {{
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: ui-monospace, "SF Mono", "Menlo", "Consolas", monospace;
  line-height: 1.6;
  font-size: 0.95em;
  background: {SOL_BG2};
  padding: 10px 14px;
  border-radius: 4px;
  border: 1px solid {SOL_RULE};
}}

.reading-content code {{
  font-family: ui-monospace, "SF Mono", "Menlo", monospace;
  background: {SOL_BG2};
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.93em;
  color: {SOL_TEXT};
}}

/* Soften Streamlit chrome for a desktop-app feel */
header[data-testid="stHeader"] {{
  background: transparent;
}}

/* Sidebar — secondary cream so it reads as a panel, not a slab */
section[data-testid="stSidebar"] {{
  background: {SOL_BG2};
  border-right: 1px solid {SOL_RULE};
}}

/* Dividers — softer than Streamlit's default slate */
hr, [data-testid="stDivider"] hr {{
  border-color: {SOL_RULE} !important;
}}

/* Tighten Streamlit's heavy-bold default headings on cream */
h1, h2, h3 {{
  color: {SOL_TEXT};
  font-weight: 600;
}}

/* Captions — slightly muted */
.stCaption, [data-testid="stCaptionContainer"] {{
  color: {SOL_TEXT_MUT} !important;
}}

/* Buttons — match Solarized blue accent and softer corners */
.stButton > button {{
  border-radius: 4px;
}}
"""


def build_inject_block() -> str:
    """Return the <style>...</style> string to inject into a Streamlit page."""
    return f"<style>{GLOBAL_CSS}</style>"


def inject_global() -> None:
    """Inject the reading-friendly CSS once per Streamlit page render.

    Idempotent — Streamlit re-renders on every interaction; running this every
    time is fine because the resulting <style> block is just appended to the DOM
    and overwrites any prior version cleanly.
    """
    st.markdown(build_inject_block(), unsafe_allow_html=True)
