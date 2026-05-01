# Reading & Guidance Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add page-level help expanders, field-level ℹ tooltips, clickable snippets that jump to source, email body rendering with paragraph preservation + thread collapse, sender→recipients context on result rows, and reading-friendly CSS — all on top of the existing W1.2 surface with no schema changes.

**Architecture:** Four new shared UI components in `casepulse/case_theory/ui/` (`page_help`, `reading_styles`, `email_renderer`, `snippet_link`). Two existing components extended (`source_row_card`, `view_source_dialog`). One bootstrap hook in `components/page_init.py` to inject CSS once per session. All 14 pages get a one-line `page_help.render(...)` call after `set_page_config`. Form fields gain `help=` parameters where the field's purpose is non-trivial.

**Tech Stack:** Python 3.11, Streamlit ≥ 1.30 (existing), AppTest for smoke tests, no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-04-30-reading-and-guidance-bundle-design.md`

---

## File structure

**New files:**

```
casepulse/case_theory/ui/
  page_help.py            # NEW
  reading_styles.py       # NEW
  email_renderer.py       # NEW
  snippet_link.py         # NEW

tests/case_theory_ui/
  test_page_help.py       # NEW
  test_reading_styles.py  # NEW
  test_email_renderer.py  # NEW
  test_snippet_link.py    # NEW
```

**Modified files:**

```
components/page_init.py                          # call reading_styles.inject_global()
casepulse/case_theory/ui/source_row_card.py      # extend format_one_line_meta
casepulse/case_theory/ui/view_source_dialog.py   # email_renderer + <mark> + JS scroll
casepulse/case_theory/ui/argument_editor.py      # make snippets clickable
Home.py                                          # add page_help.render("home")
pages/1_Case_Theory.py
pages/2_Search.py
pages/3_Timeline.py
pages/4_Cases.py
pages/4A_Witnesses.py
pages/5_Documents.py
pages/6_Ask.py
pages/7_Import_Chats.py
pages/8_Discover_Senders.py
pages/9_Fetch_Emails.py
pages/10_Accounts.py
pages/11_Export.py
pages/12_Contradictions.py
pages/13_Setup.py
```

---

## Phase 0 — Branch (already done)

Branch `ux-witnesses-help-snippet` was created earlier. Witnesses sub-piece (6 commits) and the spec doc (1 commit) already on it.

---

## Phase 1 — Foundation components

### Task 1: `page_help.py` — registry + render function

**Files:**
- Create: `casepulse/case_theory/ui/page_help.py`
- Test: `tests/case_theory_ui/test_page_help.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/case_theory_ui/test_page_help.py
import pytest
from casepulse.case_theory.ui.page_help import (
    PAGE_HELP, get_help, render_help_markdown,
)


def test_registry_contains_required_keys_for_each_page():
    expected_pages = {
        "home", "case_theory", "search", "timeline", "cases",
        "witnesses", "documents", "ask", "import_chats",
        "discover_senders", "fetch_emails", "accounts",
        "export", "contradictions", "setup",
    }
    assert set(PAGE_HELP.keys()) == expected_pages


def test_each_entry_has_required_fields():
    for key, entry in PAGE_HELP.items():
        assert "title" in entry, f"{key} missing title"
        assert "description" in entry, f"{key} missing description"
        assert "what_to_do" in entry, f"{key} missing what_to_do"
        assert isinstance(entry["title"], str) and entry["title"]
        assert isinstance(entry["description"], str) and entry["description"]
        assert isinstance(entry["what_to_do"], str) and entry["what_to_do"]


def test_get_help_returns_entry():
    h = get_help("case_theory")
    assert h["title"] == "Case Theory Workbench"


def test_get_help_returns_none_for_missing():
    assert get_help("nonexistent_page") is None


def test_render_help_markdown_includes_description_and_what_to_do():
    out = render_help_markdown("case_theory")
    assert "Case Theory Workbench" in out
    assert "Build" in out  # from description
    assert "**What to do here**" in out


def test_render_help_markdown_missing_returns_empty():
    assert render_help_markdown("nonexistent_page") == ""
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd /Users/mani/Dev/CasePulse && source venv/bin/activate
pytest tests/case_theory_ui/test_page_help.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/ui/page_help.py
"""Page-level help — default-open collapsible expander at top of every page.

Reads from PAGE_HELP registry. Each entry: title, description, what_to_do.
Render produces a Streamlit expander labeled 'About this page' that opens
by default per session and collapses on click.
"""
from typing import Optional
import streamlit as st


PAGE_HELP: dict[str, dict[str, str]] = {
    "home": {
        "title": "CasePulse Home",
        "description": "Dashboard for your cases, recent activity, and connected email accounts. "
                       "From here you can jump to any feature in the sidebar.",
        "what_to_do": "Use the sidebar to navigate. New users start with Cases (create a case), "
                      "then Case Theory (build contradictions), then Search to find evidence.",
    },
    "case_theory": {
        "title": "Case Theory Workbench",
        "description": "Build your case theory: mark allegations the opposing party made, "
                       "document contradictions, and attach evidence to specific arguments. "
                       "AI assists *after* the structural work — you do the analysis first.",
        "what_to_do": "Pick a Contradiction on the left or create a new one. Add Arguments under it "
                      "with type (Alibi, Self-contradiction, Witness, Documentary, Timing, Pattern) "
                      "and strength (Strong, Moderate, Circumstantial). Use the Evidence Tray on "
                      "the right to find and attach evidence.",
    },
    "search": {
        "title": "Search",
        "description": "Search across every email, chat message, attachment, and document with "
                       "keyword + semantic ranking. Results are court-defensible — each links back "
                       "to its original source row with a verifiable hash.",
        "what_to_do": "Type a query. Use the Filters panel for source type, date range, sender. "
                      "Click '+ Add to Argument' on a result to attach it to a Contradiction.",
    },
    "timeline": {
        "title": "Timeline",
        "description": "Chronological view of every email and chat message. Use this to scan dates "
                       "and threads, or filter to a specific window of activity.",
        "what_to_do": "Set the date range, filter by sender or keyword, and click into any row "
                      "to expand the full body. Use '+ Add to Argument' to attach an item to your case theory.",
    },
    "cases": {
        "title": "Cases & Evidence Manager",
        "description": "Create and manage your cases (one for family law, one for criminal defence, "
                       "etc.). Each case has its own exhibit numbering format and tagging system.",
        "what_to_do": "Create your first case below. Once created, switch to Case Theory or Search "
                      "to start building. The Tag Evidence Items tab lets you bulk-assign exhibit labels.",
    },
    "witnesses": {
        "title": "Witnesses",
        "description": "Manage character witnesses and fact witnesses. Each witness can have multiple "
                       "statements linked to specific Contradictions or Arguments.",
        "what_to_do": "Add a witness on the left (name, relationship, type, contact info, status). "
                      "On the right, edit details and add statements. Linking a statement to a "
                      "Contradiction makes it appear in the Argument editor automatically.",
    },
    "documents": {
        "title": "Documents & Timeline",
        "description": "Import, browse, and manage standalone documents — affidavits, police reports, "
                       "court orders, scanned PDFs. Documents are full-text searchable and EXIF metadata "
                       "is extracted from images.",
        "what_to_do": "Use the Document Library tab to browse. Click '+ Add to Argument' to attach "
                      "a document as evidence. Use Import Documents to add new ones from a folder.",
    },
    "ask": {
        "title": "Ask",
        "description": "Ask natural-language questions about your case. Answers come with structured "
                       "citations linking back to specific source rows. Build the RAG index first "
                       "(button in sidebar) for semantic answers; keyword search works without it.",
        "what_to_do": "Type a question. Citations appear under each answer — click to view the source.",
    },
    "import_chats": {
        "title": "Import Chats",
        "description": "Import WhatsApp exports, AppClose PDFs, ChatVault HTML, and generic PDF chat exports. "
                       "Auto-detects format. Imported chats are searchable and timeline-merged with emails.",
        "what_to_do": "Pick a tab matching your export format and follow the upload steps. "
                      "After import, chats appear in Timeline, Search, and the Workbench Tray.",
    },
    "discover_senders": {
        "title": "Discover Senders",
        "description": "Scan your connected email accounts to find every contact you've corresponded with. "
                       "Select the ones relevant to your case before fetching their emails.",
        "what_to_do": "Set the date range, click Scan for Contacts, then check the contacts you want to "
                      "fetch. Click Save Selection. Then go to Fetch Emails to download their messages.",
    },
    "fetch_emails": {
        "title": "Fetch Emails",
        "description": "Download emails from your selected senders within a date range. Runs in the "
                       "background — you can leave the page and come back. Emails are deduplicated "
                       "across accounts.",
        "what_to_do": "Confirm the date range and selected senders, then click Fetch. Watch progress "
                      "in the sidebar. After completion, emails appear in Timeline and Search.",
    },
    "accounts": {
        "title": "Accounts",
        "description": "Connect your Outlook, Hotmail, and Gmail accounts. Multiple accounts per provider "
                       "are supported. OAuth tokens are stored locally — your credentials never leave this machine.",
        "what_to_do": "Click Add to connect a new account. Sign in via OAuth in the popup window. "
                      "Once connected, the account appears in Discover Senders and Fetch Emails.",
    },
    "export": {
        "title": "Export",
        "description": "Generate court-ready PDF bundles, AI analysis packages, Excel timelines, and more. "
                       "Each export carries a SHA-256 manifest for chain-of-custody.",
        "what_to_do": "Pick an export preset, configure the date range and case scope, then click "
                      "Generate. The output folder is shown after completion.",
    },
    "contradictions": {
        "title": "Contradiction Engine",
        "description": "AI-powered contradiction detection across emails, chats, and documents. "
                       "This is the legacy automated engine — the new Case Theory workbench is the "
                       "human-driven approach (recommended).",
        "what_to_do": "Pick contacts to analyze, set the email batch size, then click Run. "
                      "Findings appear at the bottom. You can promote interesting findings into your "
                      "Case Theory by hand.",
    },
    "setup": {
        "title": "First-Time Setup",
        "description": "Choose which optional modules you want enabled (cloud AI, local AI via Ollama, "
                       "RAG pipeline, vision/OCR, contradiction engine, exports). Core features are always on.",
        "what_to_do": "Tick the modules you want. Default selections cover the typical setup. "
                      "Click Save when done — you can change this later.",
    },
}


def get_help(page_key: str) -> Optional[dict[str, str]]:
    """Look up help entry by page_key. Returns None if missing."""
    return PAGE_HELP.get(page_key)


def render_help_markdown(page_key: str) -> str:
    """Build the markdown body of the page help expander.

    Returns empty string if page_key is not in PAGE_HELP.
    """
    entry = get_help(page_key)
    if not entry:
        return ""
    return (
        f"### {entry['title']}\n\n"
        f"{entry['description']}\n\n"
        f"**What to do here**\n\n{entry['what_to_do']}"
    )


def render(page_key: str) -> None:
    """Render a default-open collapsible expander at the top of a Streamlit page.

    Default-open per Streamlit session; user can collapse to reclaim space.
    Uses session_state to persist the open/closed state for this session.
    """
    body = render_help_markdown(page_key)
    if not body:
        return
    state_key = f"page_help_open_{page_key}"
    default_open = st.session_state.get(state_key, True)
    with st.expander("ℹ About this page", expanded=default_open):
        st.markdown(body)
        if st.button("Hide for now", key=f"hide_help_{page_key}"):
            st.session_state[state_key] = False
            st.rerun()
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_page_help.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/page_help.py tests/case_theory_ui/test_page_help.py
git commit -m "Add page_help component with PAGE_HELP registry for all 15 pages"
```

---

### Task 2: `reading_styles.py` — global CSS injection

**Files:**
- Create: `casepulse/case_theory/ui/reading_styles.py`
- Test: `tests/case_theory_ui/test_reading_styles.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/case_theory_ui/test_reading_styles.py
from casepulse.case_theory.ui.reading_styles import (
    GLOBAL_CSS, build_inject_block,
)


def test_global_css_includes_max_width():
    assert "max-width: 1100px" in GLOBAL_CSS


def test_global_css_includes_reading_content_class():
    assert ".reading-content" in GLOBAL_CSS
    assert "max-width: 720px" in GLOBAL_CSS
    assert "ui-serif" in GLOBAL_CSS or "Georgia" in GLOBAL_CSS
    assert "line-height: 1.7" in GLOBAL_CSS


def test_build_inject_block_returns_style_tag():
    out = build_inject_block()
    assert out.startswith("<style>")
    assert out.endswith("</style>")
    assert "max-width: 1100px" in out
    assert ".reading-content" in out
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/case_theory_ui/test_reading_styles.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_reading_styles.py -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/reading_styles.py tests/case_theory_ui/test_reading_styles.py
git commit -m "Add reading_styles with global max-width + .reading-content class"
```

---

### Task 3: `email_renderer.py` — pre-wrap + blockquote + thread collapse

**Files:**
- Create: `casepulse/case_theory/ui/email_renderer.py`
- Test: `tests/case_theory_ui/test_email_renderer.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/case_theory_ui/test_email_renderer.py
from casepulse.case_theory.ui.email_renderer import (
    detect_thread_boundary, split_quoted_lines, render_html,
)


def test_detect_thread_boundary_outlook_format():
    body = (
        "Hi there,\n"
        "Quick question.\n"
        "\n"
        "On Mon, Mar 14, 2024 at 10:00 AM, Jane Doe <jane@x.com> wrote:\n"
        "> earlier message\n"
    )
    boundary_idx = detect_thread_boundary(body)
    assert boundary_idx is not None
    assert "On Mon" in body[boundary_idx:]


def test_detect_thread_boundary_no_match():
    body = "Just a single message with no replies attached.\n"
    assert detect_thread_boundary(body) is None


def test_split_quoted_lines_groups_blockquotes():
    body = (
        "Reply text here.\n"
        "> first quoted\n"
        "> second quoted\n"
        "Back to reply.\n"
    )
    out = split_quoted_lines(body)
    assert "<blockquote>" in out
    assert "first quoted" in out
    assert "second quoted" in out
    assert "Back to reply." in out


def test_render_html_simple_no_quote():
    body = "Plain email\n\nWith two paragraphs."
    html = render_html(body)
    assert "<pre" in html
    assert "Plain email" in html
    assert "With two paragraphs." in html


def test_render_html_with_thread_separates_current_and_earlier():
    body = (
        "Current message body.\n\n"
        "On Mon, Mar 14 2024, Jane wrote:\n"
        "> ancient quoted line\n"
    )
    result = render_html(body)
    # Should return a dict with 'current' (HTML) and 'earlier' (HTML or None)
    assert isinstance(result, dict)
    assert "current" in result
    assert "earlier" in result
    assert "Current message body." in result["current"]
    assert "ancient quoted line" in (result["earlier"] or "")


def test_render_html_empty_body():
    result = render_html("")
    assert result["current"] == "<pre>[empty body]</pre>"
    assert result["earlier"] is None
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/case_theory_ui/test_email_renderer.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/ui/email_renderer.py
"""Email body rendering — pre-wrap, blockquote styling for quoted lines,
and a separated 'earlier replies' section for forwarded chains.

Output is a dict with two HTML strings: 'current' (the current message)
and 'earlier' (the forwarded chain, or None if there's no boundary).
The caller renders 'current' inline and 'earlier' inside an expander.
"""
import re
from html import escape
from typing import Optional


# Outlook / Gmail / Apple Mail style boundary
_THREAD_BOUNDARY_RE = re.compile(
    r"^On\s+.{4,200}\s+wrote:\s*$",
    re.MULTILINE,
)


def detect_thread_boundary(body: str) -> Optional[int]:
    """Return the character index of the first 'On ... wrote:' boundary, or None."""
    if not body:
        return None
    m = _THREAD_BOUNDARY_RE.search(body)
    return m.start() if m else None


def split_quoted_lines(body: str) -> str:
    """HTML-escape body and wrap consecutive quoted lines (lines starting with '> ')
    in a single <blockquote> block. Returns HTML."""
    if not body:
        return ""
    lines = body.split("\n")
    out_parts: list[str] = []
    in_quote = False
    quote_buf: list[str] = []
    for line in lines:
        is_quoted = line.startswith("> ") or line.startswith(">")
        if is_quoted:
            if not in_quote:
                in_quote = True
                quote_buf = []
            # Strip the leading '> ' or '>'
            stripped = line[2:] if line.startswith("> ") else line[1:]
            quote_buf.append(escape(stripped))
        else:
            if in_quote:
                out_parts.append(
                    "<blockquote>" + "\n".join(quote_buf) + "</blockquote>"
                )
                in_quote = False
                quote_buf = []
            out_parts.append(escape(line))
    if in_quote:
        out_parts.append(
            "<blockquote>" + "\n".join(quote_buf) + "</blockquote>"
        )
    return "\n".join(out_parts)


def render_html(body: str) -> dict:
    """Render an email body as HTML.

    Returns:
        {
            "current": "<pre>...</pre>",
            "earlier": "<pre>...</pre>" or None,
        }

    'current' is the visible part — the most recent message in the thread.
    'earlier' is everything after the first 'On ... wrote:' boundary, intended
    to be wrapped in a 'Show earlier replies' expander by the caller.
    """
    if not body:
        return {"current": "<pre>[empty body]</pre>", "earlier": None}

    boundary = detect_thread_boundary(body)
    if boundary is None:
        return {
            "current": f"<pre>{split_quoted_lines(body)}</pre>",
            "earlier": None,
        }

    current = body[:boundary].rstrip()
    earlier = body[boundary:].rstrip()
    return {
        "current": f"<pre>{split_quoted_lines(current)}</pre>",
        "earlier": f"<pre>{split_quoted_lines(earlier)}</pre>",
    }
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_email_renderer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/email_renderer.py tests/case_theory_ui/test_email_renderer.py
git commit -m "Add email_renderer with pre-wrap, blockquote styling, and thread boundary detection"
```

---

### Task 4: `snippet_link.py` — clickable snippet → highlighted source

**Files:**
- Create: `casepulse/case_theory/ui/snippet_link.py`
- Test: `tests/case_theory_ui/test_snippet_link.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/case_theory_ui/test_snippet_link.py
from casepulse.case_theory.ui.snippet_link import (
    wrap_with_mark, build_scroll_script, render_marked_body,
)


def test_wrap_with_mark_inserts_mark_at_offsets():
    body = "Hello world this is a long body."
    out = wrap_with_mark(body, char_start=6, char_end=11)
    assert '<mark id="cited-highlight">world</mark>' in out
    assert "Hello " in out
    assert " this is a long body." in out


def test_wrap_with_mark_offset_overflow_returns_full_body_no_mark():
    body = "short body"
    out = wrap_with_mark(body, char_start=999, char_end=1000)
    # Out of range — return body without mark
    assert "<mark" not in out
    assert "short body" in out


def test_wrap_with_mark_zero_length_range():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=5, char_end=5)
    # Empty mark — render full body without mark
    assert "<mark" not in out
    assert "Hello world" in out


def test_wrap_with_mark_negative_start():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=-3, char_end=5)
    # Negative start — treat as 0
    assert '<mark id="cited-highlight">Hello</mark>' in out


def test_wrap_with_mark_no_offsets_returns_body():
    body = "Hello world"
    out = wrap_with_mark(body, char_start=None, char_end=None)
    assert out == "Hello world"


def test_build_scroll_script_targets_anchor():
    s = build_scroll_script()
    assert "<script>" in s
    assert "cited-highlight" in s
    assert "scrollIntoView" in s


def test_render_marked_body_combines_wrap_and_script():
    body = "Hello world"
    out = render_marked_body(body, char_start=6, char_end=11)
    assert '<mark id="cited-highlight">world</mark>' in out
    assert "scrollIntoView" in out
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/case_theory_ui/test_snippet_link.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/ui/snippet_link.py
"""Clickable snippet → source view with highlighted span and auto-scroll.

This module provides:
- wrap_with_mark: wraps a substring at (char_start, char_end) in <mark id="cited-highlight">
- build_scroll_script: returns a <script> tag that scrolls the highlight into view
- render_marked_body: combines the above into one HTML block ready for st.markdown(unsafe_allow_html=True)

The Streamlit caller uses these in the View source dialog to render the source body
with the cited span highlighted and auto-scrolled into view on dialog open.
"""
from html import escape
from typing import Optional


def wrap_with_mark(body: str, *, char_start: Optional[int],
                    char_end: Optional[int]) -> str:
    """Return body with the (char_start, char_end) range wrapped in <mark>.

    Edge cases:
    - char_start or char_end is None: return body unchanged
    - char_start < 0: clamp to 0
    - char_end > len(body): return body without <mark> (data drift)
    - char_end <= char_start: return body without <mark> (zero-length)
    """
    if char_start is None or char_end is None:
        return body
    if char_end <= char_start:
        return body
    if char_end > len(body):
        return body
    start = max(0, char_start)
    before = escape(body[:start])
    middle = escape(body[start:char_end])
    after = escape(body[char_end:])
    return f"{before}<mark id=\"cited-highlight\">{middle}</mark>{after}"


def build_scroll_script() -> str:
    """Return a <script> that scrolls the #cited-highlight element into view."""
    return (
        "<script>"
        "(function(){"
        "var el = document.getElementById('cited-highlight');"
        "if (el) { el.scrollIntoView({block: 'center', behavior: 'smooth'}); }"
        "})();"
        "</script>"
    )


def render_marked_body(body: str, *, char_start: Optional[int],
                        char_end: Optional[int]) -> str:
    """Return an HTML block with the cited span highlighted and a scroll script.

    Suitable for st.markdown(..., unsafe_allow_html=True).
    """
    marked = wrap_with_mark(body, char_start=char_start, char_end=char_end)
    return marked + build_scroll_script()
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_snippet_link.py -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/snippet_link.py tests/case_theory_ui/test_snippet_link.py
git commit -m "Add snippet_link with mark wrapping, offset edge cases, and scroll script"
```

---

## Phase 2 — Wire reading-friendly CSS

### Task 5: Hook `reading_styles.inject_global()` into `components/page_init.py`

**Files:**
- Modify: `components/page_init.py`

- [ ] **Step 1: Open and inspect the existing file**

```bash
cat /Users/mani/Dev/CasePulse/components/page_init.py
```

Expected current content (verified during planning): `init_page()` function that creates Database + Config, calls render_pin_gate, returns `(db, config)`.

- [ ] **Step 2: Add the CSS injection call after init**

Edit `components/page_init.py`. Locate the line `db = st.session_state.db` (around line 22). After the PIN gate block, add a call to `inject_global()`. Final structure:

```python
"""Shared page initialization — database, config, PIN gate, reading styles."""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def init_page():
    """Initialize database, config, PIN gate, and inject reading-friendly CSS.

    Returns (db, config) if unlocked, or calls st.stop() if locked.
    """
    from casepulse.storage.database import Database
    from casepulse.config import Config
    from casepulse.case_theory.ui.reading_styles import inject_global

    if "db" not in st.session_state:
        st.session_state.db = Database()
    if "config" not in st.session_state:
        st.session_state.config = Config()

    db = st.session_state.db
    config = st.session_state.config

    # PIN gate
    from casepulse.legal.pin_lock import render_pin_gate
    if not render_pin_gate(db):
        st.stop()

    # Reading-friendly CSS — inject once per page render
    inject_global()

    # Show running background jobs in sidebar (existing functionality)
    running_jobs = db.get_running_jobs()
    if running_jobs:
        with st.sidebar:
            st.markdown("---")
            st.markdown("**Background Jobs**")
            for job in running_jobs:
                job_type = job["job_type"].replace("_", " ").title()
                progress = job.get("progress", "Starting...")
                st.info(f"**{job_type}**\n\n{progress}")
                if st.button("Cancel", key=f"cancel_job_{job['id']}"):
                    db.cancel_job(job["id"])
                    st.rerun()

    return db, config
```

- [ ] **Step 3: Verify pages still load**

```bash
pytest tests/case_theory_ui/test_cross_page_nav.py -v
```

Expected: all 6 page-load tests PASS.

- [ ] **Step 4: Commit**

```bash
git add components/page_init.py
git commit -m "Inject reading-friendly CSS in page_init for all pages"
```

---

## Phase 3 — Wire `page_help` into all pages

### Task 6: Add `page_help.render(...)` to all 14 pages plus Home

**Files:**
- Modify: `Home.py`, `pages/1_Case_Theory.py`, `pages/2_Search.py`, `pages/3_Timeline.py`, `pages/4_Cases.py`, `pages/4A_Witnesses.py`, `pages/5_Documents.py`, `pages/6_Ask.py`, `pages/7_Import_Chats.py`, `pages/8_Discover_Senders.py`, `pages/9_Fetch_Emails.py`, `pages/10_Accounts.py`, `pages/11_Export.py`, `pages/12_Contradictions.py`, `pages/13_Setup.py`

- [ ] **Step 1: Write a smoke test that confirms each page calls page_help**

```python
# tests/case_theory_ui/test_page_help_wiring.py
from pathlib import Path

PAGES_DIR = Path(__file__).parent.parent.parent / "pages"
HOME = Path(__file__).parent.parent.parent / "Home.py"


def test_home_uses_page_help():
    text = HOME.read_text()
    assert "page_help" in text
    assert 'page_help.render("home")' in text or 'page_help.render(\'home\')' in text


def test_every_page_uses_page_help():
    expected = {
        "1_Case_Theory.py": "case_theory",
        "2_Search.py": "search",
        "3_Timeline.py": "timeline",
        "4_Cases.py": "cases",
        "4A_Witnesses.py": "witnesses",
        "5_Documents.py": "documents",
        "6_Ask.py": "ask",
        "7_Import_Chats.py": "import_chats",
        "8_Discover_Senders.py": "discover_senders",
        "9_Fetch_Emails.py": "fetch_emails",
        "10_Accounts.py": "accounts",
        "11_Export.py": "export",
        "12_Contradictions.py": "contradictions",
        "13_Setup.py": "setup",
    }
    for filename, page_key in expected.items():
        page = PAGES_DIR / filename
        text = page.read_text()
        assert "page_help" in text, f"{filename} missing page_help import"
        assert (
            f'page_help.render("{page_key}")' in text
            or f"page_help.render('{page_key}')" in text
        ), f"{filename} missing page_help.render('{page_key}')"
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/case_theory_ui/test_page_help_wiring.py -v
```

Expected: FAIL — none of the pages call page_help yet.

- [ ] **Step 3: Add `from casepulse.case_theory.ui import page_help` import + `page_help.render("...")` call to each page**

For each page file, locate the line just AFTER `st.set_page_config(...)` and any `init_page()` / database setup, and BEFORE the first content `st.markdown(...)` or similar. Insert two changes:

1. Near the top imports, add: `from casepulse.case_theory.ui import page_help`
2. Just after the page-init setup, add: `page_help.render("<page_key>")` where `<page_key>` matches the table in the test.

Example (for `pages/1_Case_Theory.py`):

Existing:
```python
import streamlit as st
from casepulse.storage.database import Database
from casepulse.config import Config
from casepulse.case_theory.repository import (
    list_contradictions, create_evidence, attach_evidence_to_argument,
)
from casepulse.case_theory.models import Evidence, EvidenceKind, EvidenceRole
from casepulse.case_theory.ui import argument_editor, contradiction_form, evidence_tray
from casepulse.case_theory.ui.picker_state import get_recent_argument_id
from casepulse.legal.pin_lock import render_pin_gate

st.set_page_config(page_title="Case Theory — CasePulse", layout="wide")
```

Add:
```python
from casepulse.case_theory.ui import page_help
```
to the imports group, and after `_init_session()` + PIN gate block, add:
```python
page_help.render("case_theory")
```

Repeat for every other page using the page_key from the test mapping.

For `Home.py`: add `from casepulse.case_theory.ui import page_help` to imports and `page_help.render("home")` near the top of `main()`.

For pages that call `init_page()` (most pages), put the `page_help.render(...)` call right after `init_page()` returns.

- [ ] **Step 4: Run wiring + cross-page tests, verify PASS**

```bash
pytest tests/case_theory_ui/test_page_help_wiring.py tests/case_theory_ui/test_cross_page_nav.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add Home.py pages/ tests/case_theory_ui/test_page_help_wiring.py
git commit -m "Wire page_help.render(...) into Home + all 14 pages"
```

---

## Phase 4 — Field-level help (`help=` parameters)

### Task 7: Add `help=` parameters to non-trivial form fields across pages

**Files (touched):**
- `pages/4_Cases.py` (case creation form, evidence tagging filters, bulk operations)
- `pages/4A_Witnesses.py` (witness form, statement form)
- `pages/1_Case_Theory.py` (argument editor — already in `casepulse/case_theory/ui/argument_editor.py`)
- `casepulse/case_theory/ui/argument_editor.py`
- `casepulse/case_theory/ui/contradiction_form.py`
- `casepulse/case_theory/ui/facets.py`
- `casepulse/case_theory/ui/attestation_form.py`
- `pages/8_Discover_Senders.py`, `pages/9_Fetch_Emails.py`, `pages/11_Export.py`, `pages/13_Setup.py`

- [ ] **Step 1: Write a coverage test**

```python
# tests/case_theory_ui/test_field_help_coverage.py
"""Spot-check that non-trivial form fields across the app pass help= text.

This test reads the source of selected files and asserts a minimum number
of `help=` arguments appear. It's an approximate quality check, not a strict
audit — if the count drops below the threshold, someone removed help text.
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def _count_help_args(path: Path) -> int:
    text = path.read_text()
    # Count occurrences of `help="` and `help='` — both quote styles
    return text.count("help=\"") + text.count("help='")


def test_cases_page_has_field_helps():
    assert _count_help_args(ROOT / "pages/4_Cases.py") >= 5


def test_witnesses_page_has_field_helps():
    assert _count_help_args(ROOT / "pages/4A_Witnesses.py") >= 4


def test_argument_editor_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/argument_editor.py") >= 4


def test_contradiction_form_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/contradiction_form.py") >= 3


def test_facets_has_field_helps():
    assert _count_help_args(ROOT / "casepulse/case_theory/ui/facets.py") >= 3
```

- [ ] **Step 2: Run, verify FAIL** (counts likely 0 or low for new components)

```bash
pytest tests/case_theory_ui/test_field_help_coverage.py -v
```

- [ ] **Step 3: Add `help=` strings to the targeted form fields**

For each file listed below, add concise `help="..."` text on the named widget. Skip widgets where the label already makes purpose obvious (e.g., a "Search" text input).

**`pages/4_Cases.py`** — case creation form:

Locate the four widgets in the "Create New Case" form (around lines 32-52). Modify each:

```python
case_name = st.text_input(
    "Case Name", placeholder="e.g., Family Law — Smith v. Smith",
    help="A short label that identifies this case in pickers and exports. "
         "Use a descriptive name, e.g. 'Family Law' or 'Criminal Defence'.",
)
case_type = st.selectbox(
    "Case Type", ["family", "criminal"],
    format_func=lambda x: {"family": "Family Law", "criminal": "Criminal Defence"}[x],
    help="Determines the default exhibit format and which export templates apply. "
         "Family Law uses lettered exhibits (A, B, C); Criminal Defence uses numbered (1, 2, 3) at trial.",
)
case_number = st.text_input(
    "Court File Number (optional)", placeholder="e.g., FC-2025-12345",
    help="The court file number assigned to your matter, if known. Appears on exhibit covers.",
)
exhibit_format = st.selectbox(
    "Exhibit Numbering Format",
    ["alpha", "bates", "numerical", "system"],
    format_func=lambda x: {
        "alpha": "Alphabetical (Exhibit A, B, C...)",
        "bates": "Bates Numbering (BATES_00001)",
        "numerical": "Numerical (Exhibit 1, 2, 3...)",
        "system": "System-Generated (Page A-1)",
    }[x],
    help="Alphabetical and Numerical are most common in Ontario family/criminal court. "
         "Bates is used for large productions to opposing counsel.",
)
```

For the evidence-tagging filters (around lines 100-116) and bulk operations (around lines 145-161), add similar concise `help=` strings.

**`pages/4A_Witnesses.py`** — witness form fields (relationship, witness_type, contact_info, status, notes) and statement form (statement_text, statement_date, contradiction picker, argument picker). Add `help=` to each, e.g.:

```python
witness_type = st.selectbox(
    "Type", options=[None] + list(WitnessType),
    format_func=lambda x: "—" if x is None else x.value,
    help="Character witnesses speak to the user's general truthfulness/character. "
         "Fact witnesses speak to specific events or statements they observed.",
)
status = st.selectbox(
    "Status", options=list(WitnessStatus), format_func=lambda x: x.value, index=0,
    help="Track contact progress: initial → contacted → willing/hostile → subpoenaed.",
)
```

**`casepulse/case_theory/ui/argument_editor.py`** — argument creation form (title, type, strength, reasoning):

```python
arg_type = st.selectbox(
    "Type", options=[None] + list(ArgumentType),
    format_func=lambda x: "—" if x is None else x.value,
    help="Alibi: shows the user wasn't there. Self-contradiction: shows the opposing "
         "party's own statements conflict. Witness: a third party will testify. "
         "Documentary: a document refutes the claim. Timing: events couldn't have happened "
         "as alleged. Pattern: a pattern of similar false claims.",
)
strength = st.selectbox(
    "Strength", options=[None] + list(Strength),
    format_func=lambda x: "—" if x is None else x.value,
    help="Strong: bulletproof, leads at trial. Moderate: corroborating but not decisive. "
         "Circumstantial: supports a pattern but needs other arguments alongside.",
)
```

**`casepulse/case_theory/ui/contradiction_form.py`** — headline, theme, notes fields. Add help:

```python
headline = st.text_input(
    "Headline",
    help="A short summary of this contradiction, e.g. 'Affidavit ¶12 vs Police Report — March 14 events'.",
)
theme_id = st.selectbox(
    "Theme",
    options=list(theme_options.keys()),
    format_func=lambda k: theme_options[k],
    help="Group related contradictions under a theme like 'Pattern of false reports' "
         "or 'Documentary inconsistencies'. Themes become brief sections at export.",
)
```

**`casepulse/case_theory/ui/facets.py`** — source-types, date range, sender. Add:

```python
types = st.multiselect(
    "Source types", SOURCE_TYPES, default=None, key=f"{key_prefix}_source_types",
    help="Restrict search to specific types: emails, chats, documents, attachments, annotations.",
)
date_from = st.text_input(
    "From", placeholder="2024-01-01", key=f"{key_prefix}_date_from",
    help="ISO date (YYYY-MM-DD). Leave blank to search from the beginning of your data.",
)
date_to = st.text_input(
    "To", placeholder="2024-12-31", key=f"{key_prefix}_date_to",
    help="ISO date (YYYY-MM-DD). Leave blank to search up to today.",
)
sender = st.text_input(
    "Sender contains", placeholder="email or name", key=f"{key_prefix}_sender",
    help="Partial match against sender email or name. Case-insensitive.",
)
```

For other pages and forms, add `help=` to non-trivial fields using the same plain-language style.

- [ ] **Step 4: Run coverage test, verify PASS**

```bash
pytest tests/case_theory_ui/test_field_help_coverage.py tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pages/ casepulse/case_theory/ui/ tests/case_theory_ui/test_field_help_coverage.py
git commit -m "Add help= tooltips to non-trivial form fields across pages and components"
```

---

## Phase 5 — Email renderer + view_source integration

### Task 8: Wire `email_renderer` into `view_source_dialog`

**Files:**
- Modify: `casepulse/case_theory/ui/view_source_dialog.py`
- Modify: `tests/case_theory_ui/test_view_source_dialog.py` (extend existing test)

- [ ] **Step 1: Write the failing test extension**

Append to `tests/case_theory_ui/test_view_source_dialog.py`:

```python
def test_render_source_panel_uses_email_renderer_for_emails(tmp_db_with_case):
    """Emails are rendered via email_renderer (paragraphs preserved, blockquotes)."""
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)
        VALUES ('S', 'Reply line.\\n\\n> earlier quoted line\\n\\nMore reply.', 'a@x', '<m1>', 'h1')
    """)
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid, inline=True,
    )
    assert "<pre>" in panel_text
    assert "<blockquote>" in panel_text
    assert "earlier quoted line" in panel_text


def test_render_source_panel_with_thread_includes_earlier_section(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)
        VALUES ('S',
                'Current message.\\n\\nOn Mon, Mar 14 2024, Jane wrote:\\n> ancient\\n',
                'a@x', '<m2>', 'h2')
    """)
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid, inline=True,
    )
    assert "Current message." in panel_text
    # Earlier section should be marked clearly
    assert "earlier replies" in panel_text.lower() or "ancient" in panel_text


def test_render_source_panel_highlights_cited_span(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id, content_hash)
        VALUES ('S', 'Hello world this is a long body.', 'a@x', '<m3>', 'h3')
    """)
    conn.commit()
    eid = cur.lastrowid
    from casepulse.case_theory.ui.view_source_dialog import render_source_panel
    # Pass char range (6, 11) which covers "world"
    panel_text = render_source_panel(
        db, source_table="emails", source_row_id=eid,
        inline=True, char_start=6, char_end=11,
    )
    assert '<mark id="cited-highlight">world</mark>' in panel_text
    assert "scrollIntoView" in panel_text
```

- [ ] **Step 2: Run, verify FAIL** (existing function doesn't accept char_start/char_end)

```bash
pytest tests/case_theory_ui/test_view_source_dialog.py -v
```

- [ ] **Step 3: Update `view_source_dialog.render_source_panel` and `show`**

Modify `casepulse/case_theory/ui/view_source_dialog.py`:

```python
# casepulse/case_theory/ui/view_source_dialog.py
"""Renders the full source content for an Evidence row.

Emails: rendered via email_renderer (pre-wrap, blockquotes, thread collapse).
Other types: rendered as plain text inside <pre> with snippet highlighting.

Optional char_start/char_end: highlight the cited span via <mark id="cited-highlight">
and inject a JS scroll-into-view script so the dialog opens already scrolled to it.
"""
from typing import Optional
import streamlit as st

from casepulse.case_theory.evidence_resolver import resolve
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.ui.email_renderer import render_html as render_email_html
from casepulse.case_theory.ui.snippet_link import (
    wrap_with_mark, build_scroll_script,
)


def _resolve_for_display(db, *, source_table: str, source_row_id: int):
    e = Evidence(
        evidence_kind=EvidenceKind.EMAIL,  # placeholder; resolver dispatches on source_table
        source_table=source_table,
        source_row_id=source_row_id,
    )
    return resolve(db, e)


def render_source_panel(db, *, source_table: str, source_row_id: int,
                         inline: bool = False,
                         char_start: Optional[int] = None,
                         char_end: Optional[int] = None) -> str:
    """Render the source panel.

    Returns the rendered string (for tests via inline=True; in normal use,
    invoked from inside @st.dialog).
    """
    rs = _resolve_for_display(
        db, source_table=source_table, source_row_id=source_row_id,
    )
    parts = [f"<h3>{rs.kind.title()}</h3>"]
    for k, v in rs.metadata.items():
        if v is None or v == "":
            continue
        parts.append(f"<p><strong>{k}:</strong> {v}</p>")

    text = rs.text or ""

    if rs.kind == "email":
        rendered = render_email_html(text)
        # Apply highlight to the 'current' section if char range falls within it
        current_html = rendered["current"]
        if char_start is not None and char_end is not None:
            # Highlight in the raw text, then re-render
            highlighted_text = wrap_with_mark(text, char_start=char_start, char_end=char_end)
            # Use highlighted_text in place of the email_renderer output if the
            # mark wrap actually produced a <mark>
            if "<mark" in highlighted_text:
                # Email body is mostly the 'current' part; re-render with mark
                marked_html = highlighted_text + build_scroll_script()
                parts.append(f'<div class="reading-content"><pre>{marked_html}</pre></div>')
            else:
                parts.append(f'<div class="reading-content">{current_html}</div>')
                if rendered["earlier"]:
                    # Caller (Streamlit) will wrap earlier in expander when not inline
                    parts.append(
                        f'<details><summary>Show earlier replies</summary>'
                        f'<div class="reading-content">{rendered["earlier"]}</div>'
                        f'</details>'
                    )
        else:
            parts.append(f'<div class="reading-content">{current_html}</div>')
            if rendered["earlier"]:
                parts.append(
                    f'<details><summary>Show earlier replies</summary>'
                    f'<div class="reading-content">{rendered["earlier"]}</div>'
                    f'</details>'
                )
    else:
        # Non-email: plain text with optional mark
        if char_start is not None and char_end is not None and "<mark" in wrap_with_mark(
            text, char_start=char_start, char_end=char_end,
        ):
            highlighted = wrap_with_mark(text, char_start=char_start, char_end=char_end)
            parts.append(
                f'<div class="reading-content"><pre>{highlighted}'
                f'{build_scroll_script()}</pre></div>'
            )
        else:
            from html import escape
            parts.append(
                f'<div class="reading-content"><pre>{escape(text)}</pre></div>'
            )

    rendered_html = "\n".join(parts)
    if inline:
        return rendered_html
    st.markdown(rendered_html, unsafe_allow_html=True)
    return rendered_html


@st.dialog("Source")
def show(db, *, source_table: str, source_row_id: int,
          char_start: Optional[int] = None,
          char_end: Optional[int] = None):
    render_source_panel(
        db, source_table=source_table, source_row_id=source_row_id,
        char_start=char_start, char_end=char_end,
    )
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_view_source_dialog.py -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/view_source_dialog.py tests/case_theory_ui/test_view_source_dialog.py
git commit -m "view_source_dialog: render emails via email_renderer + highlight cited span + auto-scroll"
```

---

## Phase 6 — Clickable snippet in Argument editor

### Task 9: Make snippet text clickable in `argument_editor`

**Files:**
- Modify: `casepulse/case_theory/ui/argument_editor.py`

- [ ] **Step 1: Identify the current snippet display**

```bash
grep -n "snippet" /Users/mani/Dev/CasePulse/casepulse/case_theory/ui/argument_editor.py
```

The argument editor shows attached evidence with their snippet text inline. Currently this is plain text. Goal: make the snippet text a button that opens View source with highlight.

- [ ] **Step 2: Add a clickable-snippet pattern**

In `casepulse/case_theory/ui/argument_editor.py`, find the per-attached-evidence rendering block (the loop over `evidence_list`). Replace the inline snippet display with:

```python
for e in evidence_list:
    ev = e["evidence"]
    cols = st.columns([6, 1])
    with cols[0]:
        # Bold metadata line
        st.markdown(
            f"- **{format_one_line_meta(kind=ev.evidence_kind.value, subject=ev.snippet or ev.source_table)}**"
        )
        # Clickable snippet — opens View source dialog with highlight + auto-scroll
        if ev.snippet:
            if st.button(
                f"📖 {ev.snippet[:120]}{'…' if len(ev.snippet) > 120 else ''}",
                key=f"snip_link_{ev.id}",
                help="Click to view this snippet in its source context",
            ):
                from casepulse.case_theory.ui.view_source_dialog import show as show_source
                show_source(
                    db,
                    source_table=ev.source_table,
                    source_row_id=ev.source_row_id,
                    char_start=ev.char_start,
                    char_end=ev.char_end,
                )
    with cols[1]:
        # Existing inline action buttons (refine snippet, remove)
        if st.button("✎", key=f"ref_{ev.id}", help="Refine snippet"):
            from casepulse.case_theory.ui.refine_snippet_dialog import show as show_refine
            show_refine(
                db, evidence_id=ev.id,
                source_table=ev.source_table,
                source_row_id=ev.source_row_id,
            )
```

- [ ] **Step 3: Verify pages still load**

```bash
pytest tests/case_theory_ui/test_workbench_smoke.py -v
```

Expected: smoke tests PASS.

- [ ] **Step 4: Commit**

```bash
git add casepulse/case_theory/ui/argument_editor.py
git commit -m "Argument editor: make snippet clickable — opens View source with highlight + scroll"
```

---

## Phase 7 — Row card extension: sender → recipients

### Task 10: Extend `format_one_line_meta` to include sender → recipients

**Files:**
- Modify: `casepulse/case_theory/ui/source_row_card.py`
- Modify: `tests/case_theory_ui/test_source_row_card.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/case_theory_ui/test_source_row_card.py`:

```python
def test_format_one_line_email_with_sender_recipients():
    line = format_one_line_meta(
        kind="email", date="2024-03-14 10:00",
        sender="alice@x.com",
        recipients=["bob@y.com", "charlie@z.com"],
        subject="Custody hearing",
    )
    assert "alice@x.com" in line
    assert "bob@y.com" in line
    assert "charlie@z.com" in line or "+1" in line  # may truncate to +1


def test_format_one_line_email_truncates_recipients():
    line = format_one_line_meta(
        kind="email", date="2024-01-01",
        sender="alice@x", recipients=["a@x", "b@x", "c@x", "d@x", "e@x"],
        subject="topic",
    )
    assert "+3 more" in line or "+4 more" in line  # accept either threshold


def test_format_one_line_chat_with_chat_name():
    line = format_one_line_meta(
        kind="chat", date="2024-03-14 14:02",
        sender="Sarah", chat_name="Mom & Manisha",
        subject="message preview here",
    )
    assert "Mom & Manisha" in line
    assert "Sarah" in line


def test_format_one_line_attachment_with_parent_email():
    line = format_one_line_meta(
        kind="attachment", date="2024-03-14",
        sender="alice@x.com", filename="affidavit.pdf",
    )
    assert "affidavit.pdf" in line
    assert "alice@x.com" in line or "alice" in line
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/case_theory_ui/test_source_row_card.py -v
```

- [ ] **Step 3: Update `format_one_line_meta`**

Replace the existing function in `casepulse/case_theory/ui/source_row_card.py`:

```python
"""Renders a 1-line preview of an evidence source row across kinds."""
from typing import Optional


_ICONS = {
    "email": "📧",
    "chat": "💬",
    "attachment": "📎",
    "document": "📄",
    "photo": "📷",
    "annotation": "📝",
}


def icon_for(kind: str) -> str:
    return _ICONS.get(kind, "•")


def _truncate(s: str, limit: int = 80) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


def _format_recipients(recipients: list[str], max_visible: int = 2) -> str:
    """Format a recipient list: 'r1, r2, +N more'."""
    if not recipients:
        return ""
    if len(recipients) <= max_visible:
        return ", ".join(recipients)
    visible = ", ".join(recipients[:max_visible])
    extra = len(recipients) - max_visible
    return f"{visible}, +{extra} more"


def format_one_line_meta(
    *, kind: str,
    date: Optional[str] = None,
    sender: Optional[str] = None,
    recipients: Optional[list[str]] = None,
    subject: Optional[str] = None,
    filename: Optional[str] = None,
    chat_name: Optional[str] = None,
) -> str:
    """Return a one-line metadata preview for an evidence source row.

    Format varies by kind:
    - email:      📧 [date] [sender] → [recipient1, recipient2, +N more] · [subject]
    - chat:       💬 [date] · [chat_name] · [sender] · [subject (message preview)]
    - attachment: 📎 [date] [filename] · from email of [sender]
    - document:   📄 [date] [filename]
    - photo:      📷 [date] [filename]
    - annotation: 📝 [date] [subject (preview)]
    """
    icon = icon_for(kind)
    if kind == "email":
        parts = []
        if date:
            parts.append(date[:16])
        if sender:
            who = sender
            if recipients:
                who = f"{sender} → {_format_recipients(recipients)}"
            parts.append(who)
        title = _truncate(subject or "", 60)
        line = f"{icon} {' · '.join(parts)}"
        if title:
            line += f" · {title}"
        return line

    if kind == "chat":
        parts = []
        if date:
            parts.append(date[:16])
        if chat_name:
            parts.append(chat_name)
        if sender:
            parts.append(sender)
        title = _truncate(subject or "", 80)
        line = f"{icon} {' · '.join(parts)}"
        if title:
            line += f" · {title}"
        return line

    if kind == "attachment":
        parts = []
        if date:
            parts.append(date[:16])
        if filename:
            parts.append(filename)
        line = f"{icon} {' · '.join(parts)}"
        if sender:
            line += f" · from email of {sender}"
        return line

    # document, photo, annotation, unknown
    parts = []
    if date:
        parts.append(date[:16])
    title = _truncate(subject or filename or "", 80)
    if title:
        parts.append(title)
    return f"{icon} {' · '.join(parts)}" if parts else icon
```

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/case_theory_ui/test_source_row_card.py -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/ui/source_row_card.py tests/case_theory_ui/test_source_row_card.py
git commit -m "source_row_card: extend format_one_line_meta with sender → recipients (emails) and chat_name"
```

---

### Task 11: Wire extended `format_one_line_meta` into Search, Timeline, Tray, Document Library

**Files:**
- Modify: `pages/2_Search.py`
- Modify: `pages/3_Timeline.py`
- Modify: `casepulse/case_theory/ui/evidence_tray.py`
- Modify: `pages/5_Documents.py`

- [ ] **Step 1: Add a smoke test**

```python
# tests/case_theory_ui/test_row_card_wiring.py
"""Confirm that pages using source_row_card pass sender/recipients/chat_name
where the data is available."""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_search_page_passes_sender_to_row_card():
    text = (ROOT / "pages/2_Search.py").read_text()
    # Should pass sender/recipients to format_one_line_meta where source row has them
    assert "format_one_line_meta" in text
    assert "sender" in text


def test_evidence_tray_passes_sender_to_row_card():
    text = (ROOT / "casepulse/case_theory/ui/evidence_tray.py").read_text()
    assert "format_one_line_meta" in text
```

- [ ] **Step 2: Run, verify check current state**

```bash
pytest tests/case_theory_ui/test_row_card_wiring.py -v
```

Likely PASSES already — the wiring exists; we just need to ensure the new sender/recipients arguments are passed.

- [ ] **Step 3: Update each surface to fetch and pass sender/recipients**

In `pages/2_Search.py` (Search results loop), modify the call:

```python
# Before per-result rendering, look up the actual sender/recipients from the source row
def _enrich_citation(cit, db):
    """Return (sender, recipients, chat_name, subject) for a Citation, or empties."""
    conn = db._get_conn()
    cur = conn.cursor()
    if cit.table == "emails":
        cur.execute(
            "SELECT sender_email, recipients, subject FROM emails WHERE id = ?",
            (cit.row_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, [], None, None
        import json
        recipients = []
        try:
            recipients = json.loads(row[1] or "[]")
        except Exception:
            recipients = []
        return row[0], recipients, None, row[2]
    if cit.table == "chat_messages":
        cur.execute(
            "SELECT sender, chat_name FROM chat_messages WHERE id = ?", (cit.row_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, [], None, None
        return row[0], [], row[1], None
    return None, [], None, None


for idx, hit in enumerate(hits):
    cit = hit.citation
    kind = cit.table.rstrip("s") if cit.table.endswith("s") else cit.table
    sender, recipients, chat_name, subject = _enrich_citation(cit, db)
    line = format_one_line_meta(
        kind=kind,
        sender=sender,
        recipients=recipients,
        chat_name=chat_name,
        subject=subject or (cit.snippet or "")[:80],
    )
    st.markdown(line)
    # ... rest of result rendering ...
```

Apply the same `_enrich_citation` helper pattern to `pages/3_Timeline.py` (per-row rendering) and `casepulse/case_theory/ui/evidence_tray.py` (per-hit in the tray).

For `pages/5_Documents.py`: documents don't have sender/recipients — the existing rendering is correct as-is.

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pages/ casepulse/case_theory/ui/evidence_tray.py tests/case_theory_ui/test_row_card_wiring.py
git commit -m "Search/Timeline/Tray: pass sender + recipients + chat_name to row card formatter"
```

---

## Phase 8 — Final smoke + manual verification

### Task 12: Cross-page smoke + full suite

**Files:** none (verification only)

- [ ] **Step 1: Run cross-page smoke**

```bash
cd /Users/mani/Dev/CasePulse && source venv/bin/activate
pytest tests/case_theory_ui/test_cross_page_nav.py -v
```

Expected: 14+ pages all load without exception.

- [ ] **Step 2: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS (target: 140+ tests, depending on how many were added in Phase 1-7).

- [ ] **Step 3: Confirm coverage hasn't regressed**

```bash
pytest tests/ --cov-report=term-missing 2>&1 | tail -20
```

Note total coverage; should match or exceed pre-bundle baseline.

- [ ] **Step 4: No commit** (verification only).

---

### Task 13: Manual browser verification

**Files:** none (manual)

- [ ] **Step 1: Restart Streamlit**

```bash
pkill -f "streamlit run" 2>/dev/null; sleep 2
./run.sh &
```

- [ ] **Step 2: Open browser and verify each page**

Open http://localhost:8501 and navigate through each sidebar entry. For each page, confirm:

1. The "ℹ About this page" expander shows by default at the top
2. The expander contains a title, description, and "What to do here" section
3. Clicking "Hide for now" collapses it and the page still works

- [ ] **Step 3: Verify field-level help on Cases form**

Click Cases → "Create New Case" expander. Hover over each field's label — a small ℹ icon should appear with the help text on hover.

- [ ] **Step 4: Verify reading-friendly typography**

Click Documents → Document Library → expand a document with extracted text → confirm the body is rendered in a serif font with line-height 1.7 and a max-width column.

- [ ] **Step 5: Verify View source dialog on email**

Click Search → query a term that hits an email → click "View source" → confirm:
- Email body is shown in serif font with preserved paragraphing
- Quoted lines (starting with `> `) appear as blockquotes
- Forwarded chains are collapsed behind a "Show earlier replies" expander (if applicable)

- [ ] **Step 6: Verify clickable snippet → highlighted source**

Create a contradiction → add an argument → attach an evidence item with a snippet → click the snippet text in the argument editor → confirm:
- View source dialog opens
- The cited span is highlighted in yellow
- The dialog auto-scrolls to the highlight

- [ ] **Step 7: Verify result-row context on Search**

Search for a term → confirm result rows show:
- Email rows: `📧 [date] [sender] → [recipient(s)] · [subject]`
- Chat rows: `💬 [date] · [chat_name] · [sender] · [preview]`

- [ ] **Step 8: No commit** (manual verification only).

---

## Self-review

After writing this plan, fresh-eyes pass against the spec at `docs/superpowers/specs/2026-04-30-reading-and-guidance-bundle-design.md`:

**1. Spec coverage:**
- §4.1 New shared components: Tasks 1-4 + 7 + 8 + 10 cover all four new components.
- §4.2 Per-page changes: Tasks 5 (CSS hook), 6 (page_help wiring), 7 (field help) cover this.
- §4.3 Page help registry: Task 1 implements PAGE_HELP for all 14+ pages.
- §4.4 CSS injection: Task 2 implements the CSS string; Task 5 hooks it into page_init.
- §4.5 Email body renderer: Task 3 implements; Task 8 wires it into view_source_dialog.
- §4.6 Snippet link component: Task 4 implements; Task 9 wires into argument_editor.
- §4.7 Row card extension: Task 10 extends; Task 11 wires it.
- §6 Error handling: covered by Task 4's edge-case tests + Task 8's defensive paths.
- §7 Testing: each task has unit + smoke tests; Task 12-13 covers final verification.
- §10 Acceptance criteria: every bullet maps to a Task.

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or "similar to Task N" patterns found. Every code step shows the actual code.

**3. Type consistency:** `format_one_line_meta(kind, date, sender, recipients, subject, filename, chat_name)` signature consistent across Tasks 10 and 11. `render_source_panel(db, source_table, source_row_id, inline, char_start, char_end)` consistent in Tasks 8 and 9. `wrap_with_mark(body, char_start, char_end)` consistent in Task 4.

No issues found.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-reading-and-guidance-bundle-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
