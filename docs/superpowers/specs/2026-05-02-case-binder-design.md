# Case Binder — Calendar Dashboard Design

**Status:** Spec
**Author:** Claude (with Mani Chaudhary)
**Date:** 2026-05-02
**Supersedes:** binder-views, binder-views-v2, case-dashboard, year-view-and-drawer-v2 (visual companion drafts)

## Goal

Give the litigant one place to see the entire case in chronological order, retrieve any item fast, store new items with the right date, automate only the parts whose accuracy is mechanical, and feed downstream court exports. Five goals: **organize, retrieve, store chronologically, automate, export**. Jordan ceiling defence is one optional downstream use case, not the design driver.

## Non-Goals

- **NLP / LLM-dependent automations** (court-date detection from email body, witness auto-linking by first name, LLM day summaries, document-date extraction from "sworn this Nth day" phrasing, photo-to-event linking by EXIF GPS + date proximity). All deferred until precision can be measured on real case data.
- **Court export pipeline** (Plan 1.3 already specced separately). The Binder produces the data; Plan 1.3 renders bundles.
- **Jordan motion timeline as a headline view**. Delay attribution is collapsed/optional on the court-appearance form; rendering a Jordan timeline at export remains possible via Plan 1.3's pipeline.
- **Multi-year stacked view**. Year is the largest unit.

## Architecture

The Case Binder is a single new Streamlit page (`pages/case_binder.py`) plus a small set of supporting components and a few schema additions. It treats existing tables as read-only sources where possible — only `timeline_events` gets a metadata column, plus three small new tables.

**Five layers:**

1. **Storage** — extend `timeline_events`, add `binder_filter_chips`, `case_relevant_senders`, `item_links`, `binder_suggestions`. Tag emails as counsel correspondence via existing `evidence_tags`.
2. **Aggregation** — `casepulse/binder/aggregator.py` turns a (case_id, date_range, filter_chip) query into a list of dated items by UNION-ing `timeline_events`, case-scoped `emails`, `chat_messages`, `documents`, `photo_metadata`, and `attachments`. Returns a flat, time-sorted iterable. Calendar views and the day drawer both consume it.
3. **Calendar UI** — `casepulse/binder/calendar.py` wraps `streamlit-calendar` (FullCalendar bridge) with the four views (year/month/week/day) and selected-day callback.
4. **Day drawer** — `casepulse/binder/day_drawer.py` renders the chronological strip for one date with inline actions.
5. **Automations** — `casepulse/binder/automations/` holds four mechanical automations, each behind a Streamlit suggestion that the user accepts or dismisses. No automatic writes.

Sidebar reorganization is one section of this spec because it adds a new page and the user has explicitly asked for grouping.

---

## Data Model

### Existing tables — no schema change

- `cases` — case scoping.
- `evidence_tags(item_type, item_id, case_id, ...)` — already the cross-table case-scoping mechanism. Used to mark emails as counsel correspondence (`legal_issue = 'counsel_correspondence'`) and to scope ingested items to a case.
- `emails`, `chat_messages`, `documents`, `attachments`, `photos` (via `photo_metadata`) — read-only sources for auto-aggregation.
- `app_settings` — for non-per-case configuration (e.g., "outstanding flag age in days").

### Existing table — extended

**`timeline_events`** is the host for the four binder entry types. Today it has the right shape (date, time, category, description, source_type, source_id, refs, case_id) but lacks structured metadata for type-specific fields.

```sql
ALTER TABLE timeline_events ADD COLUMN metadata_json TEXT DEFAULT '';
```

Agreed category vocabulary for binder entries (existing `category` column). Names are case-type-neutral so they fit both criminal and family-court matters:
- `court_appearance` — court date in any forum (criminal court, family court, motions). Optional delay-attribution metadata for criminal Jordan-motion downstream.
- `disclosure` — any document-production exchange. Covers Crown disclosure (criminal), Form 13 financial-disclosure (family), discovery production. Direction tagged in metadata.
- `counsel_correspondence` — correspondence with any legal counsel. The `party` metadata field distinguishes (`crown` | `opposing_counsel` | `own_counsel` | `OCL` | `other`). Usually links to an email row via `source_type='email', source_id=<id>`.
- `personal_event` — personal timeline event (e.g. family dinner, therapy session, supervised access visit)

Other categories (`context`, etc.) continue to exist for the older Timeline export feature.

**`metadata_json` shape per category** (informally documented in code, validated by Pydantic models):

```jsonc
// court_appearance
{
  "forum": "criminal | family | civil",         // drives form labels
  "court_name": "OCJ Toronto",
  "judge": "Justice X",
  "own_counsel": "Smith",                       // generalised — was 'defence_counsel'
  "opposing_counsel": "Doe",                    // generalised — was 'crown_counsel'
  "purpose": "first_appearance | set_date | trial | motion | case_conference | settlement_conference | sentencing | other",
  "outcome": "free text",
  "delay_attribution": {              // OPTIONAL — collapsed on form, only meaningful for criminal forum
    "category": "defence | crown | inherent | exceptional",
    "days": 14,
    "note": "free text"
  }
}

// disclosure
{
  "kind": "crown | financial | discovery | other",  // labels the disclosure flavor — drives form copy
  "direction": "received | requested",
  "page_count": 47,
  "items": "synopsis, police report, witness statements",
  "completion_status": "expecting_more | complete",
  "expected_completion_date": "2024-04-13",   // null OK
  "follow_up_email_id": 1234,                 // null OK — structural 1:1 reference, stays as metadata
  "outstanding_flag": false                    // set true when Automation #3 suggestion is accepted
}

// counsel_correspondence
{
  "party": "crown | opposing_counsel | own_counsel | OCL | other",
  "linked_email_id": 1234,                    // structural 1:1 — the entry IS this email
  "summary": "Letter from opposing counsel re Form 13 production",
  "response_required": true,
  "response_due_date": "2024-04-01",
  "response_sent_email_id": 1456              // null OK
}

// personal_event
{
  "time_end": "22:00",                         // start time goes in timeline_events.time
  "location": "Sarah's residence",
  "evidence_relevance": "alibi | corroboration | contradiction | context"
  // NOTE: related items (witnesses, photos, documents, attachments, emails) are NOT stored here.
  // They live in `item_links` rows pointing to this timeline_event with relationship='part_of'.
  // Single source of truth.
}
```

Pydantic models live in `casepulse/binder/models.py` and validate on read/write.

### New tables

**`binder_filter_chips`** — custom saved filter chips, per case (plus global if `case_id IS NULL`).

```sql
CREATE TABLE IF NOT EXISTS binder_filter_chips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,    -- NULL = global
    label TEXT NOT NULL,
    emoji TEXT DEFAULT '★',
    filter_json TEXT NOT NULL,    -- {category: [...], sender: [...], keyword: [...], witness_id: [...], outstanding: bool, ...}
    pinned INTEGER DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_binder_filter_chips_case ON binder_filter_chips(case_id, sort_order);
```

**`case_relevant_senders`** — the configured address list used by **Automation #1 (scheduled / manual sync from flagged senders)** and **Automation #2 (counsel entry suggestion)**.

```sql
CREATE TABLE IF NOT EXISTS case_relevant_senders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    address TEXT NOT NULL,                  -- email address
    role TEXT NOT NULL,                     -- crown | opposing_counsel | witness | doctor | school | other
    display_name TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(case_id, address)
);
CREATE INDEX IF NOT EXISTS idx_case_senders_case ON case_relevant_senders(case_id, active);
CREATE INDEX IF NOT EXISTS idx_case_senders_addr ON case_relevant_senders(address);
```

**`item_links`** — user-curated typed relationships between any two items. The cross-ref system has three layers now: structural (metadata_json fields like `linked_email_id`), argument-evidence (existing `argument_evidence` table for argument↔evidence), and free-form user links (this table). Arguments stay on `argument_evidence` to avoid duplication; everything else uses `item_links`.

```sql
CREATE TABLE IF NOT EXISTS item_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    from_type TEXT NOT NULL,                   -- email | chat | document | attachment | photo | timeline_event | contradiction | witness
    from_id INTEGER NOT NULL,
    to_type TEXT NOT NULL,                     -- same vocabulary as from_type
    to_id INTEGER NOT NULL,
    relationship TEXT NOT NULL,                -- supports | contradicts | responds_to | references | part_of | related (fallback)
    note TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(case_id, from_type, from_id, to_type, to_id, relationship)
);
CREATE INDEX IF NOT EXISTS idx_item_links_from ON item_links(case_id, from_type, from_id);
CREATE INDEX IF NOT EXISTS idx_item_links_to   ON item_links(case_id, to_type,   to_id);
```

**Relationship vocabulary** (small, deliberately closed — picker is a select, not a free-text):

| Type | Use |
|---|---|
| `supports` | A supports B (e.g., document supports a disclosure entry) |
| `contradicts` | A contradicts B (e.g., chat contradicts an affidavit) |
| `responds_to` | A is a response to B (e.g., email responds to Crown letter) |
| `references` | A mentions or cites B (e.g., affidavit references a photo) |
| `part_of` | A is part of B (e.g., 12 photos part of a personal event; a document part of a disclosure batch) |
| `related` | Fallback — generic association |

Linking to an `argument` uses the existing `argument_evidence` table (with `role='supports'` or `'contradicts'`), not `item_links`. Linking to a `contradiction` uses `item_links` with `to_type='contradiction'`.

**`binder_suggestions`** — pending automation suggestions awaiting user accept/dismiss. Suggestions are durable, not transient — so they survive page reloads.

```sql
CREATE TABLE IF NOT EXISTS binder_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                     -- counsel_entry | outstanding_flag | dedup
    payload_json TEXT NOT NULL,             -- type-specific data needed to execute
    status TEXT DEFAULT 'pending',          -- pending | accepted | dismissed
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_binder_suggestions_pending ON binder_suggestions(case_id, status);
```

### Migration

Single new migration in `casepulse/storage/database.py` `apply_schema_extensions()` (idempotent; uses `IF NOT EXISTS` and `PRAGMA table_info` to detect missing column):

1. `ALTER TABLE timeline_events ADD COLUMN metadata_json TEXT DEFAULT ''` (skip if column exists).
2. `CREATE TABLE IF NOT EXISTS binder_filter_chips ...`
3. `CREATE TABLE IF NOT EXISTS case_relevant_senders ...`
4. `CREATE TABLE IF NOT EXISTS item_links ...`
5. `CREATE TABLE IF NOT EXISTS binder_suggestions ...`
6. Audit-log entry recording the schema extension (using existing audit mechanism).

No data migration is required — empty tables are correct for an existing case.

---

## Aggregation Layer

`casepulse/binder/aggregator.py`:

```python
class AggregatedItem(BaseModel):
    when: datetime              # date + time, time defaults to 00:00 if unknown
    source: Literal["timeline_event", "email", "chat", "document", "photo", "attachment"]
    source_id: int
    category: str               # "court_appearance" | "disclosure" | ... | "email" | "chat" | ...
    title: str
    summary: str = ""
    metadata: dict = {}         # rendering hints
    has_attachment: bool = False
    cross_refs: list[CrossRef] = []   # ↪ links to other items

def aggregate(
    case_id: int,
    date_start: date,
    date_end: date,
    chip_filter: ChipFilter | None = None,
) -> list[AggregatedItem]:
    """UNION across timeline_events, emails, chats, documents, photos, attachments.
    Scoped by case via evidence_tags or direct case_id where present.
    Sorted ascending by when."""
```

**Case scoping rules:**
- `timeline_events` rows: `WHERE case_id = ?`
- `emails`, `chat_messages`, `documents`, `attachments`: `INNER JOIN evidence_tags ON (item_type, item_id, case_id)`
- `photo_metadata`: same — joined via evidence_tags

**Filter rules** (from `chip_filter`):
- Built-in chips → `category IN (...)` predicate or source-table predicate
- Custom chips → `filter_json` decoded to predicates: `category`, `sender_address`, `keyword` (full-text-search match), `witness_id` (joined via `metadata_json` for personal_event or `witness_statements` for emails/chats), `outstanding` (bool — disclosure entries with completion_status = 'expecting_more' AND past N days)
- "Highlight" input is *additive*: items not matching the highlight are dimmed in UI but still present in result

**Performance:**
- Calendar reads aggregate per day → typical month is 30 days × ~20 items = 600 items, well within Streamlit page-render budget
- For the year view, query the per-week activity counts via a single GROUP BY query, not the full aggregate
- Use existing FTS5 indexes for keyword filters
- Add index `CREATE INDEX IF NOT EXISTS idx_emails_date_received ON emails(date_received)` if not already present

### Delta-sync refresh

The calendar always re-queries the aggregator on every render. Since Fetch Emails writes new rows to `emails` and `chat_messages`, the calendar reflects new data on the next render. **No explicit refresh hook is needed.** Documented as a property of the aggregator, not a feature.

When the user runs Fetch Emails (manual or scheduled), Automation #2 (counsel entry suggestion) fires for each newly-imported email whose `sender_email` matches an active `case_relevant_senders.address` with `role IN ('crown', 'opposing_counsel')`. Suggestions land in `binder_suggestions`; the calendar shows a banner per pending category in its header (see "Suggestion banners" below).

---

## UI Structure

### Page layout (`pages/case_binder.py`)

```
┌─────────────────────────────────────────────────────────────┐
│ Header: case selector (always visible) · view tabs ·        │
│         date nav · Today · Jump-to · Highlight              │
│         Filter chips row (built-in 8 + custom + "+ chip")   │
│         Suggestion banners — one per pending category       │
│           e.g. "📨 3 counsel suggestions · review →"        │
│                "⚠ 1 outstanding flag · review →"            │
├─────────────────────────────────────────────────────────────┤
│ Calendar (year | month | week | day)                        │
│   - cells contain: colored chips for binder entries         │
│     + muted counts for auto-aggregated items                │
│   - selected day outlined indigo                            │
├─────────────────────────────────────────────────────────────┤
│ Day drawer (open by default for selected day)               │
│   - nav: ‹prev | date | next› · Add Entry · Open Day view   │
│   - per-day filter chips (subset of the global ones)        │
│   - chronological strip with time-stamped rows              │
│   - inline actions per row                                  │
└─────────────────────────────────────────────────────────────┘
```

### Calendar component

**Library:** `streamlit-calendar` (existing FullCalendar wrapper). Verify it supports a custom "year view" — if not, fall back to a hand-rolled year view (52-week heat strip + 12 mini-month tables) and use `streamlit-calendar` only for month/week/day. The fallback is preferred regardless because the visual companion design has an activity heat strip that FullCalendar doesn't render natively.

**Year view** — implemented in `casepulse/binder/year_view.py`:
- Top: 52-cell heat strip, color intensity = sum of items that week. Click a cell → switch to month view of that week.
- Below: 12 mini-month tables in a 4-column grid. Each day cell colored by which binder entry types occurred that day (court / disclosure / counsel / personal). Click a day → opens day drawer for that date.
- Sidebar: generic stats — total entries, count per category, busiest week, total photos / emails / chats / docs. **No Jordan-specific running totals.**

**Month view** — `streamlit-calendar` with custom `eventContent` callback rendering: one colored chip per binder entry (max 3, with "+ N more" overflow), then muted counts for auto-aggregated items. Today's cell highlighted; selected day bordered indigo.

**Week view** — FullCalendar `timeGridWeek`, default settings. Items render at their time-of-day.

**Day view** — FullCalendar `timeGridDay`. Identical content to the day drawer but full-screen.

**Click handlers:**
- Click a date cell (any view) → set `st.session_state.selected_date`, drawer re-renders below
- Click a chip → open the entry's edit dialog
- Right-click / long-press a day → "Add Entry on this date" shortcut menu

### Day drawer (`casepulse/binder/day_drawer.py`)

Renders a chronological strip of `AggregatedItem`s for one date. Layout matches the visual companion `calendar-with-drawer.html` step 3:

- Header: prev/date/next nav, Add Entry button, Open Day view button, per-day filter chips with counts
- Body: time-stamped left column (`hh:mm` or "—" if time unknown), type icon, title, summary, optional details (e.g., delay-attribution `<details>` collapsed for court appearances)
- Inline actions per row (rendered as small links in a row):
  - All rows: "Open" / "Edit" / "+ Link"
  - Email/chat rows: "View source", "+ Add to Argument" (existing case-theory tray), "↪ Convert to binder entry"
  - Email rows that match a flagged counsel sender (`role IN ('crown','opposing_counsel')`): "↪ Accept counsel suggestion" (amber) — accepts the corresponding `binder_suggestions` row
  - Disclosure rows: "Mark complete"
  - Personal-event rows: photo grid (max 8 visible, "+N" overflow) and witness chips, both populated from `item_links` rows pointing to this event
- Footer: pagination prompt for very busy days (`…42 more · show all`)

The drawer is stateless beyond `st.session_state.selected_date`. All data comes from `aggregator.aggregate(case_id, day, day, chip_filter)`.

### Filter chips (`casepulse/binder/filter_chips.py`)

**Built-in chips (always present, not editable):**
- All · 📅 Court · 📥 Disclosure · 📨 Counsel · 🗓 Personal · 📧 Emails · 💬 Chats · 📷 Photos · 📄 Docs

(📨 Counsel matches all `counsel_correspondence` regardless of `party`. To filter by party — e.g., "Crown only" or "OCL only" — create a custom chip with `category=counsel_correspondence, party=<value>`.)

**Custom chips** — defined per case via the **Manage Custom Chips** dialog:
- Form fields: emoji picker, label, filter builder (category select, sender select with autocomplete from senders + `case_relevant_senders`, keyword input that runs against FTS, witness select, "outstanding" boolean), pin/unpin, sort order
- Live preview: while editing, show the count of matching items in the current month
- Limit: 12 custom chips per case (UI gating, not a hard DB constraint)

**State management:** `selected_chip` lives in `st.session_state`. Switching a chip re-renders the calendar and day drawer; counts in the chip badges come from the aggregator (one per chip, cached per render).

**One custom chip ships as a case-creation default:** "Witness mentions" — any item whose body mentions any active witness's name (surname required to reduce false positives). Users can delete it. (The Outstanding default chip was dropped — disclosure entries already render ⚠ on the calendar when the outstanding flag is set, so a chip would duplicate that signal.)

### Add Entry form

A single Streamlit dialog with a category radio at the top. The form re-renders below to show fields for the chosen category:

- **Court appearance** — date · forum radio (criminal / family / civil) · court_name · judge · own_counsel · opposing_counsel · purpose select · outcome textarea · `<details>Optional: log delay attribution</details>` (only meaningful for criminal forum)
- **Disclosure** — date · kind radio (Crown / financial / discovery / other) · direction radio · page_count · items textarea · completion_status radio · expected_completion_date (if expecting_more) · follow_up_email picker (autocomplete from emails)
- **Counsel correspondence** — date · party radio (crown / opposing_counsel / own_counsel / OCL / other) · linked_email picker (optional; if filled, pre-fills date/sender/subject) · summary · response_required checkbox · response_due_date
- **Personal event** — date · time_start · time_end · location · description · evidence_relevance select · related-items multi-selects (witness · photo · document · attachment · email — each with autocomplete; pre-filtered to that date by default but the user can clear the filter to pick from the full corpus). The form keeps the multi-selects for usability; on save, each selected item is written as an `item_links` row, not as JSON inside the event's metadata. Single source of truth.

**Saving:**
1. Insert one `timeline_events` row (with `category`, `metadata_json`).
2. Insert one `evidence_tags` row to scope the event to the active case.
3. For **Counsel correspondence** entries with `linked_email_id`, also insert an `evidence_tags` row tagging the email with `legal_issue='counsel_correspondence'`.
4. For **Personal event** entries, insert one `item_links` row per selected related item — `from = (item_type, item_id)`, `to = (timeline_event, <new id>)`, `relationship = 'part_of'`. Witnesses use `from_type='witness'`.

### "Attach existing item to this day" shortcut

In the day drawer header, alongside "+ Add Entry", a "+ Attach to this day" button opens a lightweight picker (document / attachment / email / photo / chat / witness). When the user picks an item:

1. If a "day-anchor" `timeline_event` already exists for that date (a `personal_event` row with no time and `metadata_json.is_day_anchor=true`), reuse it. Otherwise create one with title "Items attached to this day".
2. Insert an `item_links` row: `from = (item_type, item_id)`, `to = (timeline_event, <anchor id>)`, `relationship = 'part_of'`.

The user can later edit the day-anchor event into a fuller personal-event entry if it grows into one.

### Workflow help (`casepulse/ui/workflow_help.py`)

A reusable help component shown at the top of the Setup page (collapsible, default open if no data exists yet) and as the empty-state body of the Case Binder when the active case has no data. Renders a numbered, plain-language onboarding path. **Everything stays on your machine — nothing is sent anywhere except when you explicitly fetch your own email or run an export.**

1. **Connect your email accounts.** Setup → Accounts. OAuth (Gmail) or IMAP credentials. You can connect more than one account (work, personal, archive).
2. **Discover senders for a date window.** Data Sources → Discover Senders. Pick a date window covering the period your matter spans. The app does a lightweight header-only scan (no message bodies yet) and surfaces unique sender addresses so you can flag which are case-relevant — Crown counsel, opposing counsel, your own counsel, OCL, witnesses, doctor, school, employer, anyone whose mail matters. Flagged addresses save per-case in `case_relevant_senders` and become the source list for the next step and for Automation #1.
3. **Fetch emails (full bodies, only flagged senders recommended).** Data Sources → Fetch Emails. Toggle "Only flagged senders" to pull bodies and attachments just for the addresses you flagged in step 2 — small, fast, signal-rich. Or pull everything in the window if you want to triage in CasePulse instead of in your inbox. Re-running is delta: only new mail is pulled.
4. **Import chats.** Data Sources → Import Chats. Drop in a WhatsApp / iMessage / Signal / SMS export. Each message lands on the calendar at its timestamp.
5. **Add documents and other evidence.** Data Sources → Documents. Drop in anything that didn't arrive by email — court-served PDFs, affidavits, police reports, financial statements, transcripts, audio recordings, voicemails, photos shared via AirDrop, screenshots of social-media posts or texts you can't easily export, paper documents you've scanned. The app extracts text and reads any embedded date. For photos, EXIF is read first; if missing, you'll be asked once per photo (your attestation is signed and timestamped).
6. **Watch the calendar fill in.** Workspace → Case Binder. Emails, chats, documents and photos all auto-aggregate to their natural date — you don't add them manually. The page is your daily home base.
7. **Attach extras to specific dates and link related items.** Click any day → drawer opens → **+ Attach to this day** to link an item whose own date is different but is relevant to that day; **+ Add Entry** for court appearances, disclosure, counsel correspondence, or personal events; **+ Link** on any item to typed-relate it to another item or to an Argument / Contradiction.

**Two mental models that overlap a little but are distinct:**
- **Case Binder** — *what* happened *when*. Factual chronology. Everything ingested or logged shows up here.
- **Case Theory** — *why* it matters and *how* to argue it. Allegations → Arguments → Evidence. Items in the Binder become evidence in Case Theory via "+ Add to Argument" and `item_links`.

The component takes a `state: WorkflowState` argument so it can show a checkmark next to steps already completed (e.g., ✓ once any account exists, ✓ once any sender is flagged, ✓ once the first email is fetched, ✓ once any document is uploaded). Rendering the same component on Setup and on the empty Binder gives the user a consistent mental model regardless of where they enter.

### Suggestion banners

Pending suggestions surface inline as banners on the calendar header — one banner per kind, suppressed when zero pending. Examples: `📨 3 counsel suggestions · review →`, `⚠ 1 outstanding flag · review →`, `🧬 2 possible duplicates · review →`. Clicking a banner expands it inline below the header into a list of that kind's pending rows:

- Each row: summary ("Email from Doe (opposing counsel) on Mar 14 — log as counsel correspondence?"), Accept / Dismiss buttons
- Accept executes the side-effect (e.g., create the timeline_events row with `category='counsel_correspondence'` and `party='opposing_counsel'`, tag the email via `evidence_tags`) and sets `status='accepted'`
- Dismiss sets `status='dismissed'`
- Banner count decrements; banner disappears when it hits zero

This replaces the earlier "right-side suggestion drawer" idea — banners cost less UI surface and keep triage in the user's reading flow.

---

## Performance

The corpus grows continuously and the Binder is the daily entry point — slow renders here mean the whole tool feels broken. Concrete budgets:

| Operation | Budget | Test |
|---|---|---|
| Year view render (heat strip + 12 mini-calendars) | ≤ 1.0 s | with 100 K aggregated rows, no per-day data, only weekly GROUP BY counts |
| Month view render | ≤ 0.7 s | with 5 K rows in the visible month |
| Day drawer render | ≤ 0.3 s | with 200 items on the day (busy day; pagination caps at 60 visible) |
| Add Entry save | ≤ 0.2 s | including item_links writes |
| Aggregator query (single day) | ≤ 0.05 s | with 100 K aggregated rows in the corpus |

**Indexes** (added in the migration):
- `idx_emails_date_received ON emails(date_received)` (if not present)
- `idx_chat_messages_timestamp ON chat_messages(timestamp)` (if not present)
- `idx_documents_created ON documents(created_at)` (if not present)
- `idx_timeline_date_case ON timeline_events(case_id, date)` (extends the existing `idx_timeline_date`)
- `idx_evidence_tags_case_type ON evidence_tags(case_id, item_type)` (if not present)

**Caching:** the aggregator's per-chip count results are cached for 30 seconds in `st.session_state` keyed by `(case_id, view, date_range, chip_id)`. Mutations (Add Entry, Accept suggestion) clear the cache for the active case.

**Perf test** — Phase A includes one perf test that seeds 100 K mixed rows and asserts each budget. Failing the budget fails CI; the test is run on every push.

## Privacy & Data Locality

CasePulse runs entirely on the user's machine. The Binder makes no network calls except via the user's existing Fetch Emails (OAuth/IMAP to your own provider) and Export (writes files locally). No telemetry, no cloud sync, no external LLM calls in the Binder itself. The Workflow help and the Setup page both display this prominently:

> **Your data stays on this device.** CasePulse only reaches out when you tell it to fetch your own email or run an export. Nothing is sent to Anthropic, Google, or anyone else.

The audit log records every state-changing action (entry created, suggestion accepted, item linked, etc.) with a hash chain so that a defensible export can show what happened and when, on this machine, in your hands.

## Photo Dating Chain

When a photo is imported (drag-drop on the Documents page or from an attachment):

1. Try EXIF DateTimeOriginal → `photo_metadata.captured_at`, `reliability='reliable'`
2. If missing, try filesystem mtime — only for direct file uploads, not photos that originated as email attachments or chat-app shares (the existing `photo_metadata.source` discriminator already records this). When the source indicates email/chat origin, skip mtime entirely → `reliability='stripped'`
3. If still missing, prompt the user with a date picker → `reliability='attested'`, write a `metadata_attestations` row

In the calendar, photos with `reliability='reliable'` or `'attested'` are placed on their captured_at date. Photos with `reliability='stripped'` or `'unreliable'` go on a "Photos with unknown date" stack at the bottom of the day drawer for the import date until the user dates them.

This already exists per Plan 1.1; the Binder reads from it without modification.

---

## Automations (4, all mechanical)

All automations write to `binder_suggestions`. None mutate other tables directly. The user accepts or dismisses each suggestion.

### Automation #1 — Scheduled / manual sync from flagged senders

**Mechanism:** When the user runs Fetch Emails (existing page), the sync optionally filters by `case_relevant_senders.address` for the active case. A new "Sync only flagged senders" toggle appears on the Fetch Emails page next to the existing controls.

**Implementation:** No new code in `casepulse/binder/automations/`; this is a small change in `pages/9_Fetch_Emails.py` (or its post-reorg equivalent) that reads `case_relevant_senders` and passes the address list as an IMAP filter (`OR FROM ...`).

**Background scheduling** is out of scope for this spec — Streamlit doesn't host long-running daemons. The user runs Fetch manually. (A future Plan can add a system cron / launchd entry that drives the same sync.)

### Automation #2 — Counsel entry suggestion

**Trigger:** After every Fetch Emails run, scan newly-imported `emails` rows. For each email where `sender_email` matches an active `case_relevant_senders.address` with `role IN ('crown','opposing_counsel','own_counsel','OCL')`, write a `binder_suggestions` row with `kind='counsel_entry'` and payload `{email_id, suggested_date, suggested_subject, party}` — `party` is derived from the matching sender's `role`.

**Implementation:** `casepulse/binder/automations/counsel_suggest.py` exposes `scan_for_counsel_suggestions(case_id, since: datetime) -> int` that the Fetch Emails post-hook calls.

### Automation #3 — Outstanding flag

**Trigger:** When the calendar page loads, run a single SQL query: find `timeline_events` rows with `category='disclosure'` and `metadata_json -> '$.completion_status' = 'expecting_more'` whose `date` is more than N days in the past (N from `app_settings`, default 30). For each, ensure a `binder_suggestions` row with `kind='outstanding_flag'` exists.

When the suggestion is accepted, the disclosure entry's metadata gets `outstanding_flag=true`, and the calendar renders ⚠ on the entry. (It's still a manual accept — the user might know the file came in via a different channel.)

**Implementation:** `casepulse/binder/automations/outstanding.py`. Idempotent — does not duplicate an existing pending suggestion for the same disclosure entry.

### Automation #4 — Deduplicate & link

**Trigger A** — When the user opens the Add Entry form for a Counsel correspondence and starts typing the linked email's subject, autocomplete suggests existing email rows by subject + sender. If they pick one, the suggestion is "Already in your emails of [date] — link existing instead of creating a new free-form entry?" If they accept, the form pre-fills from the email and saves a Counsel-correspondence entry linked to that email.

**Trigger B** — When the user uploads a document or attachment whose `content_hash` matches an existing `documents` or `attachments` row, show "Already in your [emails / documents] of [date]" and offer "Link existing" instead of "Save as new".

**Implementation:** `casepulse/binder/automations/dedup.py`. Pure SQL by `content_hash`. The UI lives in the Add Entry form and the import flow.

### Out of scope (deferred until precision can be measured)

- Court date detection from email body (NLP)
- Witness auto-linking by first name (name collisions)
- LLM day summaries (untested generation quality)
- Document-date extraction from "sworn this Nth day" patterns (format variability)
- Photo-to-event linking by EXIF GPS + date proximity (multi-input correlation)

Each one needs a labeled-accuracy test on real case data before turning on.

---

## Cross-References & Relationships

Three layers, all rendered the same way (`↪ Related to ...` in the day drawer and View Source dialog):

1. **Structural metadata** — explicit 1:1 FK-like fields on entries. Cheap, queryable, the natural shape. Kept only where the reference is intrinsic to the entry's identity:
   - `disclosure.metadata_json.follow_up_email_id`
   - `counsel_correspondence.metadata_json.{linked_email_id, response_sent_email_id}`

2. **Argument linking** — `argument_evidence` (existing case-theory table). The drawer shows "✓ In Argument #N · supports" or "✓ In Argument #N · contradicts". No duplication elsewhere.

3. **User-curated typed links — `item_links`.** Everything else. Includes the items related to a personal event (`from = item, to = personal_event, relationship = part_of`), items linked to a contradiction, items linked to a disclosure batch, and any free-form user link. Renders with the relationship type as a small label: `↪ supports Disclosure of Mar 14`, `↪ responds to letter of Mar 4`, `↪ contradicts Affidavit (sworn Mar 12)`.

The aggregator emits `cross_refs: list[CrossRef]` per item, populated from all three layers. The day drawer renders them inline. Single source of truth: there's exactly one place to look for any given relationship — no array-vs-table data drift.

### Linking UI

Two entry points:

**View Source dialog** — when the user opens an email, chat, document, attachment, or photo, a "Related" panel sits below the content. Lists existing relationships (with delete affordance), and a `+ Link to...` button that opens the link picker.

**Link picker dialog**:
- "From" is fixed to the item that opened the picker.
- "Relationship" select (the 6-type vocabulary above).
- "To" is a typed search input that autocompletes across emails / chats / documents / attachments / photos / timeline_events / contradictions for the active case. Items are scoped to the case via `evidence_tags`.
- Optional note (one line).
- Save → writes one `item_links` row.

**Day drawer inline action** — every item row has a `+ Link` link in its inline-actions row, opening the same picker pre-filled with the item.

**Reverse view** — when viewing an Argument, Contradiction, or any binder entry, the View page shows incoming links: "These items reference this entry: ..." with the same delete affordance.

---

## Sidebar Reorganization

The user has asked for category grouping in the sidebar. Streamlit's modern `st.navigation()` API supports section headers; the older `pages/` directory pattern does not. Migration plan:

1. Move pages out of the `pages/` directory into `pages_modules/` (rename to plain snake_case files: `case_binder.py`, `case_theory.py`, etc., dropping the numeric prefixes).
2. In `Home.py`, register sections via `st.navigation`:

```python
nav = st.navigation({
    "Setup":         [st.Page("pages_modules/setup.py", title="Setup", icon=":material/key:"),
                      st.Page("pages_modules/accounts.py", title="Accounts", icon=":material/mail:")],
    "Data Sources": [st.Page("pages_modules/discover_senders.py", title="Discover Senders"),
                     st.Page("pages_modules/fetch_emails.py", title="Fetch Emails"),
                     st.Page("pages_modules/import_chats.py", title="Import Chats"),
                     st.Page("pages_modules/documents.py", title="Documents")],
    "Workspace":    [st.Page("pages_modules/case_binder.py", title="Case Binder", default=True),
                     st.Page("pages_modules/cases.py", title="Cases"),
                     st.Page("pages_modules/witnesses.py", title="Witnesses"),
                     st.Page("pages_modules/case_theory.py", title="Case Theory")],
    "Find & Reason":[st.Page("pages_modules/search.py", title="Search"),
                     st.Page("pages_modules/ask.py", title="Ask"),
                     st.Page("pages_modules/contradictions.py", title="Contradictions")],
    "Export":       [st.Page("pages_modules/export.py", title="Export"),
                     st.Page("pages_modules/timeline.py", title="Timeline (HTML)")],
})
nav.run()
```

3. The existing `pages/` directory is deleted in the same change. Internal page imports continue to work (no behavior change inside each page).
4. **Default landing page becomes Case Binder** (`default=True`) — the user's most common entry point post-launch.

**Verify:** Streamlit version supports `st.navigation` with section grouping (1.36+). Plan task includes a `streamlit --version` check and an upgrade if needed.

---

## Phasing

### Phase A — Calendar dashboard with manual entries (~1 week)

- Schema migration (timeline_events.metadata_json + 4 new tables, including `item_links` so Phase A can already write part_of links from personal events)
- Performance indexes on emails / chat_messages / documents / timeline_events / evidence_tags
- Aggregator (timeline_events + emails + chats + documents + photos), with cross_refs populated from item_links + structural metadata + argument_evidence
- Year view (heat strip + 12 mini-calendars, hand-rolled)
- Month view (streamlit-calendar with custom event content)
- Week + Day views (streamlit-calendar default)
- Day drawer (chronological strip) with **+ Attach to this day** shortcut (creates day-anchor + item_links)
- Built-in filter chips (9: All + 8 categories with 📨 Counsel)
- Add Entry form (4 categories — court_appearance, disclosure, counsel_correspondence, personal_event) — Personal-event form's multi-selects write `item_links` rows, not metadata arrays
- Workflow help component + Setup page intro + Case Binder empty state, with the 7-step onboarding path and the Privacy callout
- Sidebar reorganization (5 sections via `st.navigation`)
- Make Case Binder the default landing page
- **Perf test** seeded with 100 K mixed rows asserts all five render budgets
- **Smoke test** that imports every page module to catch broken imports after the `pages/` → `pages_modules/` migration
- Tests: aggregator unit tests (case scoping, filter predicates, cross_refs assembly), calendar render AppTest, drawer AppTest, schema migration test, workflow-state checkmark logic, item_links round-trip + UNIQUE constraint test

**Deliverable:** the user can manually log court dates, disclosures, counsel-correspondence entries (criminal or family), personal events, see them on the calendar alongside auto-aggregated emails/chats/docs/photos, and click any day to see a chronological strip. New users see a numbered onboarding path on Setup and on the empty Binder.

### Phase B — Custom chips, automations, suggestion banners (~1 week)

- Custom filter chips (Manage dialog, live preview, **one** ship-default: "Witness mentions")
- `case_relevant_senders` config UI (a section on the Discover Senders page or a new Senders sub-page under Workspace)
- Link picker dialog + "+ Link" inline action on every item row in day drawer + View Source dialog "Related" panel + reverse-view ("incoming links to this item") on Argument / Contradiction / binder entry pages (the `item_links` table itself ships in Phase A; Phase B adds the broader user-facing UI)
- Automation #1 — Sync filter on Fetch Emails (toggle: "Only flagged senders")
- Automation #2 — Counsel entry suggestion (post-Fetch hook, fires for any flagged role in `{crown, opposing_counsel, own_counsel, OCL}`)
- Automation #3 — Outstanding flag (calendar-load hook)
- Automation #4 — Dedup link (Add Entry autocomplete + import-time dedup hook)
- Suggestion banners on the calendar header (one per kind, expand inline)
- Tests: each automation gets unit + integration tests; suggestion-banner AppTest covering accept/dismiss flow; dedup hash-collision test; reverse-view AppTest; counsel-suggest correctly derives `party` from `case_relevant_senders.role`

**Deliverable:** the calendar self-organizes incoming counsel emails into per-party suggestions, the user only sees the ones that need triage, outstanding disclosure flags surface automatically, and duplicate uploads are caught.

### Out of scope (later spec)

- Court export pipeline (Plan 1.3 — already specced)
- Background scheduled sync (system cron/launchd integration)
- NLP / LLM automations (deferred until accuracy is measured)
- Multi-case calendar view (one case at a time is sufficient)

---

## Testing Strategy

- **Unit:** Pydantic models for each metadata_json shape. Aggregator query correctness with seeded data. Each automation in isolation.
- **Integration:** Schema migration on a real existing DB. End-to-end Add Entry → calendar render → drawer click.
- **AppTest:** Each new component has a Streamlit AppTest covering golden path + one edge case.
- **Real-data verification:** After implementation, run against the user's actual case DB. Verify (a) existing timeline_events still render, (b) no orphan rows after migration, (c) no perf regression on month-view queries with 500+ items.

---

## Open Questions

None. All earlier ambiguities resolved during brainstorming:

1. ~~timeline_events reuse vs new table~~ → **Reuse with metadata_json column.**
2. ~~Jordan as headline vs optional~~ → **Optional, collapsed on court-appearance form, available for Plan 1.3 export.**
3. ~~LLM-dependent automations~~ → **Deferred until measured.**
4. ~~Sidebar grouping mechanism~~ → **`st.navigation` migration, 5 sections.**
5. ~~Delta-sync calendar refresh~~ → **Free property of stateless aggregator; documented, no extra hook.**
6. ~~Crown vs counsel naming~~ → **Renamed to counsel_correspondence with party field; works for both criminal and family.**
7. ~~Personal-event metadata arrays vs item_links~~ → **All item-to-item linking goes through item_links; metadata holds only event-intrinsic data.**
8. ~~Suggestion drawer vs header banners~~ → **Header banners; less UI surface, in-flow triage.**
9. ~~Default custom chips count~~ → **One: "Witness mentions". Outstanding dropped (⚠ icon already conveys it).**

## Acknowledged but out of scope (for follow-up specs)

- **Backup / .db export** — your evidence vault lives in one SQLite file; a one-button "Backup database" on Setup is worth its own small spec.
- **Date-range events** (e.g., a stalking pattern across months) — `timeline_events.approx` is already there; a future extension can add `date_end`.
- **Multi-device sync** — currently single-device, copy the encrypted .db when you switch machines.
- **Court mode UI** — when physically in court, you want big text and a single search box; the existing Search page covers it functionally.
- **Background scheduled sync** — Streamlit doesn't host daemons; a future Plan can add a system cron / launchd entry that drives the same Fetch Emails sync.
