"""Theme palettes + picker UI for CasePulse.

Six curated themes, each with a distinct *vibe* — not just a different
background tint. Each palette carries: background trio, text, muted text,
rule, primary + secondary accent, status colors, font stack, corner radius.

The active theme is persisted in `app_settings` under the key `theme.active`.
The reading-styles CSS is rebuilt against the active palette on every page
render via `casepulse.case_theory.ui.reading_styles.inject_global()`, so
switching is instantaneous (one `st.rerun()`).
"""
from __future__ import annotations
import streamlit as st


THEMES = {
    # ---------- LIGHT ----------
    "solarized_light": {
        "name": "Solarized Light",
        "kind": "light",
        "vibe": "1970s typewriter paper",
        "blurb": "Warm cream paper, slow blue. Designed for hours of reading.",
        "bg":        "#fdf6e3",
        "bg2":       "#eee8d5",
        "bg3":       "#f5efd5",
        "text":      "#586e75",
        "muted":     "#93a1a1",
        "rule":      "#d3cbb7",
        "primary":   "#268bd2",   # warm blue
        "secondary": "#cb4b16",   # orange — links/hover
        "yellow":    "#fbedc4",
        "ok":        "#859900",
        "warn":      "#b58900",
        "err":       "#dc322f",
        "font":      "ui-sans-serif, -apple-system, 'Source Sans 3', system-ui, sans-serif",
        "radius":    "4px",
    },
    "paper": {
        "name": "Paper",
        "kind": "light",
        "vibe": "academic publication",
        "blurb": "Parchment off-white, deep ink, serif body. Like reading a brief.",
        "bg":        "#faf8f1",
        "bg2":       "#f1ede0",
        "bg3":       "#ebe6d4",
        "text":      "#2d2a26",
        "muted":     "#7a7368",
        "rule":      "#cdc7b8",
        "primary":   "#1e4d72",   # oxford blue
        "secondary": "#8c1d18",   # claret
        "yellow":    "#f5e9b8",
        "ok":        "#3d6b3a",
        "warn":      "#9e6e2a",
        "err":       "#a83232",
        "font":      "'Charter', 'Iowan Old Style', 'Georgia', ui-serif, serif",
        "radius":    "0px",
    },
    "github_light": {
        "name": "GitHub Light",
        "kind": "light",
        "vibe": "clean tech tool",
        "blurb": "Crisp white, vivid blue. Familiar, professional.",
        "bg":        "#ffffff",
        "bg2":       "#f6f8fa",
        "bg3":       "#eaeef2",
        "text":      "#1f2328",
        "muted":     "#656d76",
        "rule":      "#d0d7de",
        "primary":   "#0969da",
        "secondary": "#cf222e",
        "yellow":    "#fff8c5",
        "ok":        "#1a7f37",
        "warn":      "#9a6700",
        "err":       "#cf222e",
        "font":      "-apple-system, 'Segoe UI', 'Helvetica Neue', system-ui, sans-serif",
        "radius":    "6px",
    },
    # ---------- DARK ----------
    "solarized_dark": {
        "name": "Solarized Dark",
        "kind": "dark",
        "vibe": "amber terminal at night",
        "blurb": "Warm dark teal, slow blue. Same colorimetry as Solarized Light.",
        "bg":        "#002b36",
        "bg2":       "#073642",
        "bg3":       "#0a4451",
        "text":      "#93a1a1",
        "muted":     "#586e75",
        "rule":      "#0a4451",
        "primary":   "#268bd2",
        "secondary": "#cb4b16",
        "yellow":    "#3a3a1c",
        "ok":        "#859900",
        "warn":      "#b58900",
        "err":       "#dc322f",
        "font":      "ui-sans-serif, -apple-system, 'Source Sans 3', system-ui, sans-serif",
        "radius":    "4px",
    },
    "nord": {
        "name": "Nord",
        "kind": "dark",
        "vibe": "scandinavian minimalist",
        "blurb": "Cool arctic slate, ice blue. Calm and modern.",
        "bg":        "#2e3440",
        "bg2":       "#3b4252",
        "bg3":       "#434c5e",
        "text":      "#eceff4",
        "muted":     "#81a1c1",
        "rule":      "#4c566a",
        "primary":   "#88c0d0",
        "secondary": "#5e81ac",
        "yellow":    "#3b3a25",
        "ok":        "#a3be8c",
        "warn":      "#ebcb8b",
        "err":       "#bf616a",
        "font":      "ui-sans-serif, -apple-system, 'Inter', system-ui, sans-serif",
        "radius":    "4px",
    },
    "dracula": {
        "name": "Dracula",
        "kind": "dark",
        "vibe": "cyberpunk neon",
        "blurb": "Deep purple, hot pink. Bold contrast for late-night work.",
        "bg":        "#282a36",
        "bg2":       "#21222c",
        "bg3":       "#44475a",
        "text":      "#f8f8f2",
        "muted":     "#bdbdbd",
        "rule":      "#44475a",
        "primary":   "#bd93f9",   # purple
        "secondary": "#ff79c6",   # hot pink
        "yellow":    "#f1fa8c",
        "ok":        "#50fa7b",
        "warn":      "#ffb86c",
        "err":       "#ff5555",
        "font":      "ui-sans-serif, -apple-system, 'Inter', 'Fira Sans', system-ui, sans-serif",
        "radius":    "6px",
    },
}


DEFAULT_THEME = "solarized_light"


def get_active_theme_id(db) -> str:
    """Read the active theme id from app_settings; default if unset."""
    try:
        with db._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = 'theme.active'"
            ).fetchone()
        if row and row["value"] in THEMES:
            return row["value"]
    except Exception:
        pass
    return DEFAULT_THEME


def get_active_theme(db) -> dict:
    """Return the active theme palette dict."""
    return THEMES[get_active_theme_id(db)]


def set_active_theme(db, theme_id: str) -> None:
    if theme_id not in THEMES:
        raise ValueError(f"unknown theme: {theme_id}")
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO app_settings (key, value) VALUES ('theme.active', ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (theme_id,),
        )


def _swatch_html(theme: dict) -> str:
    """Five-color swatch HTML for a theme. Used in the picker preview."""
    swatches = [theme["bg"], theme["bg2"], theme["text"], theme["primary"], theme["secondary"]]
    cells = "".join(
        f"<span style='display:inline-block;width:18px;height:18px;border-radius:3px;"
        f"background:{c};margin-right:2px;border:1px solid rgba(0,0,0,0.1);'></span>"
        for c in swatches
    )
    return f"<div style='display:inline-block'>{cells}</div>"


def render_theme_picker(db, *, location: str = "main") -> None:
    """Render the theme picker. `location` may be 'main' or 'sidebar'.

    Shows all themes side-by-side with name, vibe, blurb, and a five-color
    swatch (bg / bg2 / text / primary / secondary). Click a theme to apply.
    """
    target = st.sidebar if location == "sidebar" else st
    current_id = get_active_theme_id(db)

    target.markdown("### Theme")
    target.caption("Click a theme to apply. The whole app re-renders immediately.")

    for tid, theme in THEMES.items():
        is_active = tid == current_id
        marker = "●" if is_active else "○"
        cols = target.columns([1, 5])
        with cols[0]:
            st.markdown(_swatch_html(theme), unsafe_allow_html=True)
        with cols[1]:
            label = f"{marker} **{theme['name']}** · {theme['kind']}"
            if st.button(label, key=f"theme_btn_{tid}",
                          disabled=is_active, use_container_width=True):
                set_active_theme(db, tid)
                st.rerun()
            st.caption(f"_{theme['vibe']}_ — {theme['blurb']}")
