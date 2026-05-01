# Design — Reading & Guidance Bundle

| Field | Value |
|---|---|
| Date | 2026-04-30 |
| Status | Draft — pending user review |
| Scope | UI/UX polish bundle — top-of-page help, field-level help tooltips, clickable snippet → source navigation, email body formatting, result-row context, reading-friendly typography |
| Out of scope | Schema changes, new entities, new pages, AI mode work, court export pipeline, framework migration |
| Pre-requisites | W1.1 (foundation) and W1.2 (UI) on main; Witnesses sub-piece already shipped on the `ux-witnesses-help-snippet` branch (6 commits) |

## 1. Goal

Make CasePulse easier to use and easier to read on long-form text without changing the underlying architecture. Specifically:

1. Every page surfaces a plain-language explanation of what it is for and what to do here.
2. Every form field has an inline ℹ tooltip explaining its purpose.
3. The cited snippet under an Argument is clickable — clicking opens the source view dialog highlighting and auto-scrolling to the cited span, so the user can see surrounding context in one click.
4. Email bodies render with original paragraphing preserved, quoted lines styled as blockquotes, and forwarded chains collapsed behind an expander.
5. Result rows on the Search page, Timeline, Evidence Tray, and Document Library show *who* the communication is between (sender → recipients) plus the subject or snippet — in one compact line.
6. Long-form reading surfaces (View source dialog, Argument editor reasoning text, document body previews, brief preview) get a tighter reading-column width with a serif body font and generous line-height. Pages overall get a moderate global max-width so they breathe.

The bundle does not introduce new entities, schema, dependencies, or pages. It is purely UI/CSS layered on top of the existing W1.2 surface.

## 2. Non-goals

- Migrating off Streamlit (Tauri rebuild is deferred to after Plan 1.3 + Wave 2)
- True drag-to-highlight text selection for snippet refinement (Streamlit limitation; deferred to a later custom-component effort)
- New schema, new pages, new export formats
- The Case Binder feature (will be a separate spec next)
- Plan 1.3 court export pipeline (separate spec)
- Wave 2 AI modes (separate plan)

## 3. Users and workflow

Single user. Streamlit app on local desktop. PIN-locked. The reading & guidance improvements primarily benefit:

- The user himself when reading long affidavits, police reports, and forwarded email chains in View source
- The user when scanning Search results, Timeline, and Document Library
- A future second reader (lawyer, paralegal) opening the app for the first time and needing to know what each page does

No data flow changes. All improvements are at the render layer.

## 4. Architecture

### 4.1 New shared components

All in `casepulse/case_theory/ui/`:

```
casepulse/case_theory/ui/
  page_help.py            # NEW — default-open collapsible expander
  reading_styles.py       # NEW — injects global CSS for reading-friendly layout
  email_renderer.py       # NEW — pre-wrap + blockquote + thread collapse
  snippet_link.py         # NEW — clickable snippet → opens source dialog with highlight + auto-scroll
  source_row_card.py      # MODIFIED — extended format_one_line_meta to include sender → recipients
  view_source_dialog.py   # MODIFIED — uses email_renderer for emails; renders <mark> highlight + JS auto-scroll
```

### 4.2 Per-page changes

Every page (14 pages today) gets:
- A `page_help.render(page_key)` call as the first content after `st.set_page_config(...)`. The expander is open by default (per Streamlit session) and collapsible.
- A `reading_styles.inject_global()` call in the page-init helper (`components/page_init.py`) so the moderate-global max-width applies once per session.
- All `st.text_input`, `st.selectbox`, `st.text_area`, `st.checkbox`, `st.date_input`, `st.multiselect`, etc. gain a `help="..."` parameter where useful (skip trivial cases like search boxes whose label already names the purpose).

Reading-content pages (View source dialog, Argument editor reasoning, document body section, future brief preview) wrap their long-text element in a `<div class="reading-content">...</div>` block via `st.markdown(unsafe_allow_html=True)` so the tighter reading-column max-width and serif font apply.

### 4.3 Page help content registry

A single `PAGE_HELP` dict in `casepulse/case_theory/ui/page_help.py` maps page-keys to their help content:

```python
PAGE_HELP = {
    "case_theory": {
        "title": "Case Theory Workbench",
        "description": "Build your case structure: mark allegations the other party has made, "
                       "document the contradictions, and attach evidence to specific arguments. "
                       "AI assists after the structural work.",
        "what_to_do": "Pick a Contradiction on the left or create a new one. Add Arguments under it "
                      "with type and strength. Use the Evidence Tray on the right to find and attach evidence.",
    },
    "search": {
        "title": "Search",
        "description": "Search across every email, chat, attachment, and document with keyword + semantic ranking.",
        "what_to_do": "Type a query. Use the Filters panel for source type, date range, sender. "
                      "Click '+ Add to Argument' on a result to attach it to a Contradiction.",
    },
    # ... one entry for each page
}
```

The component renders the title + description + what-to-do as a single Streamlit expander labeled "About this page". Default expanded; collapses on click; collapse state preserved via `st.session_state[f"page_help_collapsed_{page_key}"]`.

### 4.4 CSS injection (reading_styles)

```css
/* Moderate global max-width — pages breathe instead of stretching to 1440px */
.main .block-container {
  max-width: 1100px;
}

/* Tighter reading column for long-form text */
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

.reading-content mark {
  background: #fef3c7;
  padding: 1px 3px;
  border-radius: 2px;
}

.reading-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: ui-serif, Georgia, "Times New Roman", serif;
  line-height: 1.7;
}

/* Hide Streamlit chrome that's unhelpful on a desktop app — optional */
header[data-testid="stHeader"] {
  background: transparent;
}
```

Injected once per page-init via `st.markdown(<style>...</style>, unsafe_allow_html=True)`. The CSS lives in a Python string in `reading_styles.py` so it's source-controlled with the rest of the code.

### 4.5 Email body renderer

`email_renderer.render(body: str) -> str` returns the body wrapped in HTML for `st.markdown(unsafe_allow_html=True)`:

1. Detect quoted lines: any line starting with `> ` (after optional leading whitespace) is grouped into consecutive blockquote sections.
2. Detect forwarded-chain boundary: the regex pattern `r"^On (.+) wrote:$"` (Outlook/Gmail standard) marks the boundary. Everything before the boundary is "current message"; everything after is "earlier replies", wrapped in a collapsible expander.
3. Render the current message in `<pre style="white-space: pre-wrap; font-family: serif; line-height: 1.6">` with quoted lines wrapped in `<blockquote>`.
4. The collapsible expander uses Streamlit's native `with st.expander("▸ Show earlier replies", expanded=False)` so it integrates with the page rerun model.

Edge cases:
- Email with no quoted content: just render the body in pre-wrap.
- Email body is HTML (`emails.body_html` is non-empty): for v1, fall back to plain text rendering of `body_text` and ignore HTML. (Rendering sanitized HTML is deferred — see Out of scope.)
- Body has multiple "On ... wrote:" boundaries (deeply forwarded chain): collapse everything after the FIRST boundary into a single expander. v2 could add nested collapses.

### 4.6 Snippet link component

`snippet_link.render(snippet: str, source_table: str, source_row_id: int, char_start: int, char_end: int)` renders the snippet text as a clickable element. On click, opens the View source dialog with three additions:

1. The dialog renders the full source body (using `email_renderer` for emails).
2. The cited span (`char_start` to `char_end`) is wrapped in `<mark id="cited-highlight">...</mark>`.
3. A `<script>` tag injected at the end of the dialog body runs `document.getElementById('cited-highlight')?.scrollIntoView({block: 'center', behavior: 'smooth'})` so the dialog opens already scrolled to the cited span.

Implementation note: Streamlit's `st.dialog`-decorated function is the natural home for this. The `<mark>` and `<script>` are rendered via `st.markdown(unsafe_allow_html=True)`. The script runs once per dialog open.

### 4.7 Row card extension

The existing `source_row_card.format_one_line_meta(...)` function is extended to accept `sender`, `recipients`, and `chat_name` keyword arguments and produce one of these formats:

- Email: `📧 [date] [sender_name or sender_email] → [recipient1, recipient2, +N more] · [subject]`
- Chat: `💬 [date] · [chat_name] · [sender] · [message_preview]`
- Attachment: `📎 [date] [filename] · from email of [sender]`
- Document: `📄 [date] [filename]`
- Photo: `📷 [taken_at_or_received_date] [filename] · [camera_make_model_if_known]`
- Annotation: `📝 [date] [note_preview]`

Truncation rules: subject/preview truncated to 80 chars with `…`; recipients past 2 collapse to `+N more`.

## 5. Data flow

No new tables. No new columns. No new RPCs. Every component reads existing data:

```
page_help          : reads PAGE_HELP[page_key] dict (in-Python constant)
reading_styles     : no data; injects static CSS string
email_renderer     : input is emails.body_text from existing schema
snippet_link       : input is Citation/Evidence row (already exists, has char_start/char_end/snippet)
source_row_card    : extended to read sender_email + recipients (JSON column on emails); chat_name on chat_messages
view_source_dialog : uses evidence_resolver.resolve() (existing) + email_renderer + <mark> + JS scroll
```

## 6. Error handling

| Scenario | Behavior |
|---|---|
| `PAGE_HELP[page_key]` missing | Render no expander (graceful) |
| `body_text` is empty or None in email | Render `[empty body]` placeholder |
| `body_html` exists but `body_text` is empty | Fall back to "HTML-only email — body not displayed in v1" message |
| `char_start > len(body)` (data drift) | Render full body without `<mark>`; log a warning at top of dialog |
| `char_end < char_start` (data drift) | Treat as `char_start = char_end` (zero-length mark — invisible) and log warning |
| Source row deleted (resolver returns deleted sentinel) | Render `[source row deleted]` notice with attestation hint |
| `email_renderer` regex fails to find any quoted/boundary patterns | Render full body in plain pre-wrap (always works) |
| `recipients` field is malformed JSON | Render `[recipients unavailable]` and continue with rest |

## 7. Testing

### 7.1 Unit tests

- `tests/case_theory_ui/test_email_renderer.py` — quote detection, thread boundary detection, multi-paragraph quote handling, edge cases (empty body, no boundaries, multiple boundaries)
- `tests/case_theory_ui/test_snippet_link.py` — `<mark>` wrapping at correct char range, JS scroll script presence, edge cases (offset overflow, zero-length range)
- `tests/case_theory_ui/test_page_help.py` — registry has entries for every page in `pages/`; each entry has the required keys
- `tests/case_theory_ui/test_source_row_card.py` — extend existing tests to cover the new email/chat/attachment formats with sender/recipients

### 7.2 Smoke tests

- Re-run cross-page smoke (`tests/case_theory_ui/test_cross_page_nav.py`) and confirm every page still loads with the new `page_help` expander present
- Add a smoke test that view source dialog opens for an email and produces output containing `<mark`

### 7.3 Manual verification

After implementation:
- Open every page in the browser; confirm the help expander shows and is dismissible
- Open the View source dialog on a long email with forwarded chain; confirm pre-wrap, blockquote styling, and "Show earlier replies" expander
- Click a snippet under an Argument; confirm the dialog opens, the highlight is visible, and the page is scrolled to the highlight
- Search "custody"; confirm result rows show sender → recipients in compact one-line format
- Open a long affidavit document; confirm reading-column max-width and serif body apply

## 8. Migration plan

No DB migration. CSS injection runs on every page load (idempotent). On first load after deployment, all pages render with the new help expander expanded; user can collapse per-page.

## 9. Performance considerations

- CSS injection per page: ~500 bytes of CSS, one-time per page rerun. Negligible.
- `email_renderer` regex on body: ~O(N) over body length. For a 50-page affidavit (~100 KB body), ~milliseconds.
- `snippet_link` `<mark>` wrapping: substring slicing, O(1) effectively.
- Page help expander: pure Streamlit native widget. No cost.

## 10. Acceptance criteria

- [ ] Every page in `pages/` has a default-open `page_help` expander as its first content
- [ ] `PAGE_HELP` registry has entries for all 14+ pages with title / description / what_to_do
- [ ] Every form field across all pages has a `help=` parameter where the field's purpose is non-trivial
- [ ] Reading-friendly CSS injected globally; long-form surfaces wrap content in `.reading-content`
- [ ] View source dialog renders emails with pre-wrap, serif font, blockquote styling on `> ` lines, and a "Show earlier replies" expander when a forwarded boundary is detected
- [ ] Argument editor's snippet display is clickable; click opens View source dialog with `<mark>` on cited span and JS auto-scroll
- [ ] Search results, Timeline rows, Evidence Tray, Document Library show sender → recipients in compact one-line format
- [ ] All existing tests still pass; new tests covering email_renderer, snippet_link, page_help, source_row_card extensions all pass
- [ ] Cross-page smoke test confirms every page renders without exception

## 11. Open questions / known unknowns

- The collapse-state of the `page_help` expander is per-Streamlit-session, not persistent across sessions. Users will see it expanded on first visit each session. This is acceptable for v1.
- The HTML-only email case (`body_html` set, `body_text` empty) currently falls back to a "HTML-only email — body not displayed in v1" message. If this turns out to be common in real data, add HTML sanitization + rendering in a follow-up.
- The regex for forwarded-chain boundary (`On ... wrote:`) is Outlook/Gmail standard. Other clients (Apple Mail, Thunderbird) may use different patterns. Detect during real-world use; extend the regex.

## 12. Out of scope (deferred)

- Drag-to-highlight text selection for snippet refinement (Streamlit limitation; deferred to custom-component work)
- HTML email rendering with sanitization (deferred unless real data shows HTML-only emails are common)
- Per-user preference: persistently remember which page-help expanders are dismissed across sessions (would require new `app_settings` rows; deferred)
- Theme variants: dark mode customization, font-size preference, etc.

## 13. Spec self-review

After writing this spec, I scanned for placeholders, contradictions, ambiguity, and scope:

- **Placeholders**: none found.
- **Internal consistency**: §4.6 (snippet link) and §4.4 (CSS) both reference `<mark>` styling; consistent (`#fef3c7` background, defined once in `reading_styles.py`).
- **Scope**: focused on a single coherent UX layer. No accidental schema changes. Witnesses sub-piece is already shipped (out of this spec).
- **Ambiguity**: `help=` should be added "where useful" — clarified by the example of skipping trivial cases (search box). Final decision left to per-field judgment during implementation.
- **Dependency creep**: no new packages. The `bleach` dependency mentioned in earlier discussion is dropped (HTML rendering deferred).
