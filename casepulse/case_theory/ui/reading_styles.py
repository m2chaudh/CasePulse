# casepulse/case_theory/ui/reading_styles.py
"""Global CSS injection for reading-friendly typography.

Two scopes:
1. Global moderate max-width — pages stop stretching to 1440px+ on wide screens
2. Tight `.reading-content` class — for long-form text surfaces (View source dialog,
   Argument editor reasoning, document body, brief preview)
"""
import streamlit as st


GLOBAL_CSS = """
/* Moderate global max-width — let pages breathe instead of stretching to 1440px */
.main .block-container {
  max-width: 1100px;
}

/* Tight reading column for long-form text */
.reading-content {
  max-width: 720px;
  margin: 0 auto;
  font-family: ui-serif, Georgia, "Times New Roman", serif;
  line-height: 1.7;
  font-size: 1.05em;
}

.reading-content p {
  margin: 1em 0;
}

.reading-content blockquote {
  border-left: 3px solid #94a3b8;
  padding-left: 14px;
  margin-left: 0;
  color: #475569;
  font-style: italic;
}

.reading-content mark,
.reading-content mark#cited-highlight {
  background: #fef3c7;
  padding: 1px 3px;
  border-radius: 2px;
}

.reading-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: ui-serif, Georgia, "Times New Roman", serif;
  line-height: 1.7;
  font-size: 1em;
}

/* Soften Streamlit chrome for desktop-app feel */
header[data-testid="stHeader"] {
  background: transparent;
}
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
