"""Theme palettes + picker UI for CasePulse.

Each theme is a flat dict of named colors. The active theme is persisted
per-user in `app_settings` under the key `theme.active`. The reading-styles
CSS is rebuilt against the active palette on every page render, so switching
themes is instantaneous (one `st.rerun()`).

`.streamlit/config.toml` sets `base = "light"` so Streamlit's chrome opens
sensibly. Dark themes from this file override with CSS — most widgets follow
correctly via inheritance; a few system pieces (scrollbars, native menus) may
fall back to the light base. Switching between light and dark groups shows
the active theme cleanly in the body, header, and sidebar.
"""
from __future__ import annotations
import streamlit as st


THEMES = {
    # ----- Lights -----
    "solarized_light": {
        "name": "Solarized Light",
        "kind": "light",
        "blurb": "Warm cream — Ethan Schoonover's reading-optimised palette.",
        "bg":       "#fdf6e3",
        "bg2":      "#eee8d5",
        "text":     "#586e75",
        "muted":    "#93a1a1",
        "rule":     "#d3cbb7",
        "primary":  "#268bd2",
        "yellow":   "#fbedc4",
        "quote_bg": "#f5efd5",
        "ok":       "#859900",
        "warn":     "#b58900",
        "err":      "#dc322f",
    },
    "catppuccin_latte": {
        "name": "Catppuccin Latte",
        "kind": "light",
        "blurb": "Cool lavender-tinted soft white. Modern, popular in 2024+.",
        "bg":       "#eff1f5",
        "bg2":      "#e6e9ef",
        "text":     "#4c4f69",
        "muted":    "#6c6f85",
        "rule":     "#bcc0cc",
        "primary":  "#1e66f5",
        "yellow":   "#fff4cf",
        "quote_bg": "#dce0e8",
        "ok":       "#40a02b",
        "warn":     "#df8e1d",
        "err":      "#d20f39",
    },
    "github_light": {
        "name": "GitHub Light",
        "kind": "light",
        "blurb": "Crisp white, blue accent. Familiar, professional.",
        "bg":       "#ffffff",
        "bg2":      "#f6f8fa",
        "text":     "#1f2328",
        "muted":    "#656d76",
        "rule":     "#d0d7de",
        "primary":  "#0969da",
        "yellow":   "#fff8c5",
        "quote_bg": "#f6f8fa",
        "ok":       "#1a7f37",
        "warn":     "#9a6700",
        "err":      "#cf222e",
    },
    "paper": {
        "name": "Paper",
        "kind": "light",
        "blurb": "Tufte-style off-white, deep ink. Like reading on stationery.",
        "bg":       "#fafaf7",
        "bg2":      "#f1eee5",
        "text":     "#2d2a26",
        "muted":    "#7a7368",
        "rule":     "#d6d2c7",
        "primary":  "#1e6091",
        "yellow":   "#f5e9b8",
        "quote_bg": "#f1eee5",
        "ok":       "#3d6b3a",
        "warn":     "#9e6e2a",
        "err":      "#a83232",
    },
    "atom_one_light": {
        "name": "Atom One Light",
        "kind": "light",
        "blurb": "Editor classic — neutral whites, gentle blue accent.",
        "bg":       "#fafafa",
        "bg2":      "#eaeaeb",
        "text":     "#383a42",
        "muted":    "#a0a1a7",
        "rule":     "#d0d0d3",
        "primary":  "#4078f2",
        "yellow":   "#f7e8a3",
        "quote_bg": "#eaeaeb",
        "ok":       "#50a14f",
        "warn":     "#c18401",
        "err":      "#e45649",
    },
    # ----- Darks -----
    "solarized_dark": {
        "name": "Solarized Dark",
        "kind": "dark",
        "blurb": "Warm dark — same palette as Solarized Light, low strain.",
        "bg":       "#002b36",
        "bg2":      "#073642",
        "text":     "#93a1a1",
        "muted":    "#586e75",
        "rule":     "#0a4451",
        "primary":  "#268bd2",
        "yellow":   "#3a3a1c",
        "quote_bg": "#073642",
        "ok":       "#859900",
        "warn":     "#b58900",
        "err":      "#dc322f",
    },
    "nord": {
        "name": "Nord",
        "kind": "dark",
        "blurb": "Cool arctic blue-gray. Calm and modern.",
        "bg":       "#2e3440",
        "bg2":      "#3b4252",
        "text":     "#d8dee9",
        "muted":    "#81a1c1",
        "rule":     "#434c5e",
        "primary":  "#88c0d0",
        "yellow":   "#3b3a25",
        "quote_bg": "#3b4252",
        "ok":       "#a3be8c",
        "warn":     "#ebcb8b",
        "err":      "#bf616a",
    },
    "catppuccin_mocha": {
        "name": "Catppuccin Mocha",
        "kind": "dark",
        "blurb": "Rich dark with mauve accents. Trendy in 2024+.",
        "bg":       "#1e1e2e",
        "bg2":      "#181825",
        "text":     "#cdd6f4",
        "muted":    "#a6adc8",
        "rule":     "#313244",
        "primary":  "#89b4fa",
        "yellow":   "#3a3624",
        "quote_bg": "#181825",
        "ok":       "#a6e3a1",
        "warn":     "#f9e2af",
        "err":      "#f38ba8",
    },
    "github_dark": {
        "name": "GitHub Dark",
        "kind": "dark",
        "blurb": "Clean charcoal — GitHub's official dark.",
        "bg":       "#0d1117",
        "bg2":      "#161b22",
        "text":     "#e6edf3",
        "muted":    "#7d8590",
        "rule":     "#30363d",
        "primary":  "#2f81f7",
        "yellow":   "#3a2c00",
        "quote_bg": "#161b22",
        "ok":       "#3fb950",
        "warn":     "#d29922",
        "err":      "#f85149",
    },
    "atom_one_dark": {
        "name": "Atom One Dark",
        "kind": "dark",
        "blurb": "Editor classic dark — neutral, well-calibrated.",
        "bg":       "#282c34",
        "bg2":      "#21252b",
        "text":     "#abb2bf",
        "muted":    "#5c6370",
        "rule":     "#3e4451",
        "primary":  "#61afef",
        "yellow":   "#3a3625",
        "quote_bg": "#21252b",
        "ok":       "#98c379",
        "warn":     "#e5c07b",
        "err":      "#e06c75",
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


def render_theme_picker(db, *, location: str = "main") -> None:
    """Render the theme picker. `location` may be 'main' or 'sidebar'."""
    target = st.sidebar if location == "sidebar" else st
    current_id = get_active_theme_id(db)
    options = list(THEMES.keys())
    labels = {tid: f"{THEMES[tid]['name']} · {THEMES[tid]['kind']}" for tid in options}
    target.markdown("### Theme")
    target.caption("Pick a palette. The whole app re-renders immediately.")
    chosen = target.selectbox(
        "Active theme",
        options,
        index=options.index(current_id),
        format_func=lambda k: labels[k],
        key="theme_picker",
        label_visibility="collapsed",
    )
    target.caption(THEMES[chosen]["blurb"])
    if chosen != current_id:
        set_active_theme(db, chosen)
        st.rerun()
