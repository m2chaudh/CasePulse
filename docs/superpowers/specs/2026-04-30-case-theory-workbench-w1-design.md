# Design — Case Theory Workbench (Wave 1)

| Field | Value |
|---|---|
| Date | 2026-04-30 |
| Status | Draft — pending user review |
| Scope | Wave 1 of the CasePulse Case Theory Workbench |
| Wave 2 (deferred) | AI Curated / Discovery / Compare modes |
| Target jurisdictions | Ontario, Canada — both **Family Law** (Family Law Rules) and **Criminal** (Criminal Proceedings Rules / common law) |
| Authentication | *Canada Evidence Act* ss.31.1-31.8 (federal — criminal, divorce); *Ontario Evidence Act* s.34.1 (provincial — family/civil). s.31.6 Certificate of Authenticity auto-generated for both. |

## 1. Goal

Build a Case Theory Workbench inside CasePulse that lets the user manually map allegations made by an opposing party to their refutations and supporting evidence, and produces a court-defensible PDF bundle suitable for filing in **Ontario Family Court** *and* for use in **defence-side preparation in Ontario criminal proceedings**.

The user is the sole analyst, simultaneously fighting one family-law matter and one criminal matter. AI assistance is deferred to Wave 2 — Wave 1 is human-in-the-loop by design. The workbench must produce admissible exhibits per CEA ss.31.1-31.8 / OEA s.34.1, with the wrapper (affidavit cover, defence brief structure, exhibit numbering) chosen per case type.

## 2. Non-goals (Wave 1)

Explicitly out of scope, deferred:

- AI Curated mode — Wave 2
- AI Discovery mode (Contradiction Engine redesign) — Wave 2
- Compare view — Wave 2
- Concordance load files (`.DAT`/`.OPT`) — later
- Privilege log generation — later
- True PDF redaction (text-removal + metadata strip) — later
- US/UK/AUS jurisdiction export formats — later
- Voicemail / audio transcription (WhisperX) — later
- Near-duplicate clustering (MinHash + LSH) — later
- Entity resolution / alias unification — later
- AI Assistant sandbox fix (prompt-injection risk on Discover Senders) — small follow-up after W1
- Wholesale refactor of `casepulse/storage/database.py` (1,398 LoC god-class) — incremental escape only as W1 work touches it

## 3. Users and core workflow

Single user, sole analyst, Streamlit app on local desktop, PIN-locked. Both cases share the same data model and the same evidence pool — a chat showing the opposing party made an inconsistent statement is relevant in both. They differ in **export wrap**, not in case theory structure.

The four-phase flow:

```
BUILD     →  REFINE    →  PREVIEW   →  EXPORT
(workbench   (workbench   (workbench    (publish to
 layers 1+2)  layers 1+2)  layer 3 live) lawyer/court)
```

Two flows for evidence attachment, both first-class:

- **Workbench-first** — persistent Evidence Tray (right pane of Workbench page) for search/filter/attach without leaving the Argument editor.
- **Search-first** — dedicated Search page; each result has an inline "+ Add to Argument" popover.

## 4. Architecture

### 4.1 New components

```
casepulse/
  case_theory/                         # NEW
    __init__.py
    models.py                          # Pydantic types
    repository.py                      # CRUD on case-theory tables
    evidence_resolver.py               # polymorphic Evidence → source row
    exhibit_renderer.py                # exhibit cover sheets (preview + export)
    brief_renderer.py                  # brief sections (preview + export)
    metadata_extractor.py              # EXIF + reliability detection
    templates/                         # NEW: pluggable export templates
      __init__.py                      # registry
      base.py                          # protocol/abstract template
      ontario_family.py                # default for case_type='family'
      ontario_criminal_trial.py        # default for case_type='criminal' (trial prep)
      ontario_criminal_motion.py       # affidavit-style criminal pre-trial motions
      generic.py                       # fallback

  search/                              # NEW
    __init__.py
    fts.py                             # FTS5 schema + query builder
    citation.py                        # Citation type
    retrieval.py                       # hybrid: BM25 + embeddings + RRF
    rrf.py                             # reciprocal rank fusion

pages/
  11_Case_Theory.py                    # NEW: dual-pane Workbench
  12_Search.py                         # NEW: dedicated faceted search
  4_Timeline.py                        # MOD: + Add to Argument; FTS5 keyword filter
  5_Ask.py                             # MOD: hybrid retrieval; structured Citation
  8_Export.py                          # MOD: case-aware export presets
  9_Documents.py                       # MOD: + Add to Argument; auto-OCR
```

### 4.2 Library additions

- `Pillow` (already installed) — EXIF extraction
- `dateparser` — fuzzy date parsing in search + metadata
- `pytesseract` — Tesseract OCR for image attachments; falls back to existing llava via `OllamaProvider` if confidence < 0.6
- `x-ray` (from freelawproject) — bad-redaction detection on PDFs
- `weasyprint` — HTML → PDF for the new W1 brief and exhibit pipelines. **Both** the in-app "Preview brief" and the canonical Court Bundle export use weasyprint over the same HTML templates — single rendering pipeline, no preview-vs-export divergence. The existing `fpdf2` library stays in place for the previously-built export presets (Timeline PDF, AI Package, Exhibit Bundle PDF) — those are unchanged in W1.

## 5. Data model

### 5.1 New tables

```sql
-- Themes (refinement D): reusable groupings for Contradictions
CREATE TABLE themes (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  display_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(case_id, title)
);
CREATE INDEX idx_themes_case ON themes(case_id);

-- Allegations (refinement A): claims made by opposing party
CREATE TABLE allegations (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  claimed_date TEXT,                   -- ISO date the allegation refers to
  source_evidence_id INTEGER REFERENCES evidence(id),  -- where she said it
  status TEXT DEFAULT 'active',        -- active / withdrawn / disputed
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_allegations_case ON allegations(case_id);
CREATE INDEX idx_allegations_date ON allegations(claimed_date);

-- Contradictions: the conflicts you note
CREATE TABLE contradictions (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  headline TEXT NOT NULL,
  status TEXT DEFAULT 'draft',         -- draft/reviewed/locked/used-in-filing
  theme_id INTEGER REFERENCES themes(id) ON DELETE SET NULL,
  display_order INTEGER DEFAULT 0,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_contradictions_case ON contradictions(case_id);
CREATE INDEX idx_contradictions_status ON contradictions(status);
CREATE INDEX idx_contradictions_theme ON contradictions(theme_id);

-- Bridge: Contradiction <-> Allegation (M:N)
CREATE TABLE contradiction_allegations (
  contradiction_id INTEGER NOT NULL REFERENCES contradictions(id) ON DELETE CASCADE,
  allegation_id INTEGER NOT NULL REFERENCES allegations(id) ON DELETE CASCADE,
  PRIMARY KEY (contradiction_id, allegation_id)
);

-- Arguments
CREATE TABLE arguments (
  id INTEGER PRIMARY KEY,
  contradiction_id INTEGER NOT NULL REFERENCES contradictions(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  reasoning_text TEXT,
  argument_type TEXT,    -- alibi/self_contradiction/witness/documentary/timing/pattern
  strength TEXT,         -- strong/moderate/circumstantial
  sequence INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_arguments_contradiction ON arguments(contradiction_id);
CREATE INDEX idx_arguments_type ON arguments(argument_type);
CREATE INDEX idx_arguments_strength ON arguments(strength);

-- Evidence: polymorphic pointer to source rows
CREATE TABLE evidence (
  id INTEGER PRIMARY KEY,
  evidence_kind TEXT NOT NULL,     -- email/chat/attachment/document/photo
  source_table TEXT NOT NULL,
  source_row_id INTEGER NOT NULL,
  char_start INTEGER,
  char_end INTEGER,
  snippet TEXT,                    -- denormalized; may be regenerated
  source_hash TEXT,                -- SHA-256 at evidence-creation time
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source_table, source_row_id, char_start, char_end)
);
CREATE INDEX idx_evidence_source ON evidence(source_table, source_row_id);
CREATE INDEX idx_evidence_kind ON evidence(evidence_kind);

-- Bridge: Argument <-> Evidence (M:N) — same evidence_id can appear in
-- multiple arguments across multiple cases
CREATE TABLE argument_evidence (
  argument_id INTEGER NOT NULL REFERENCES arguments(id) ON DELETE CASCADE,
  evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
  role TEXT DEFAULT 'supports',    -- supports/corroborates/refutes
  display_order INTEGER DEFAULT 0,
  notes TEXT,
  added_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (argument_id, evidence_id)
);

-- Photo metadata (1:1 with photo source rows)
CREATE TABLE photo_metadata (
  id INTEGER PRIMARY KEY,
  source_table TEXT NOT NULL,
  source_row_id INTEGER NOT NULL,
  taken_at TEXT,                   -- ISO8601, EXIF DateTimeOriginal
  camera_make TEXT,
  camera_model TEXT,
  lens TEXT,
  software TEXT,
  gps_lat REAL,
  gps_lon REAL,
  gps_accuracy REAL,
  orientation INTEGER,
  width INTEGER,
  height INTEGER,
  exif_present INTEGER DEFAULT 0,  -- 1 if any EXIF block found
  detected_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source_table, source_row_id)
);
CREATE INDEX idx_photo_metadata_source ON photo_metadata(source_table, source_row_id);
CREATE INDEX idx_photo_metadata_taken ON photo_metadata(taken_at);

-- Per-field reliability: strikes + attestations
CREATE TABLE metadata_attestations (
  id INTEGER PRIMARY KEY,
  photo_metadata_id INTEGER NOT NULL REFERENCES photo_metadata(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,        -- 'taken_at', 'gps_lat', ..., 'overall'
  status TEXT NOT NULL,            -- struck/attested
  reason TEXT,                     -- why struck
  attestation_text TEXT,           -- the sworn statement
  attested_by TEXT,
  attested_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_metadata_attestations_pm ON metadata_attestations(photo_metadata_id);
```

### 5.2 Schema modifications

```sql
-- Cases get a type so export wrappers can be selected
ALTER TABLE cases ADD COLUMN case_type TEXT NOT NULL DEFAULT 'family';
-- values: family / criminal / civil / other

-- Audit log gets a hash chain for tamper-evidence
ALTER TABLE audit_log ADD COLUMN prev_hash TEXT;
ALTER TABLE audit_log ADD COLUMN row_hash TEXT;
-- Application code computes row_hash = SHA-256(prev_hash || canonicalized(row_data))
-- Verification scans the chain at startup or on-demand.
```

### 5.3 Bug fixes folded into W1

- **`chat_messages.content_hash`** column exists in schema since the original SQLite design but is **never written** by any parser (`whatsapp_parser`, `chatvault_parser`, `appclose_parser`). One-time migration backfills hashes for all existing rows; ingest paths are updated to populate going forward.
- **Ask page silent date-filter broadening** (`rag/query_engine.py:~91`): when a date filter excludes all retrieved chunks, the code currently falls back to "ignore the filter and return everything." Fixed: when no results, log + return empty rather than silently widen.

### 5.4 FTS5 indices

Contentless virtual tables for the full extracted-text corpus:

```sql
CREATE VIRTUAL TABLE emails_fts USING fts5(
  subject, body_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter');

CREATE VIRTUAL TABLE chat_messages_fts USING fts5(
  message_text, sender, chat_name,
  content='', tokenize='unicode61 remove_diacritics 2 porter');

CREATE VIRTUAL TABLE attachments_fts USING fts5(
  filename, extracted_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter');

CREATE VIRTUAL TABLE documents_fts USING fts5(
  filename, extracted_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter');

CREATE VIRTUAL TABLE annotations_fts USING fts5(
  note_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter');

-- Triggers (one per table) keep indices in sync on INSERT/DELETE/UPDATE.
```

`content=''` keeps the source rows authoritative; FTS5 stores only the inverted index. BM25 ranking, `snippet()` for highlights, `highlight()` for in-context emphasis.

### 5.5 Citation model

```python
class Citation(BaseModel):
    table: Literal["emails", "chat_messages", "attachments", "documents", "annotations"]
    row_id: int
    char_start: int | None = None
    char_end: int | None = None
    snippet: str | None = None
    source_hash: str | None = None  # SHA-256 at citation time

    def resolve(self) -> ResolvedSource:
        """Look up the row + verify hash if present."""
```

Used everywhere a pointer to source-text is needed: search results, Evidence rows, Ask-page citations (replaces LLM-generated string citations), brief / exhibit renderers.

## 6. Hybrid retrieval

```python
def hybrid_search(query: str, *, facets: SearchFacets, k: int = 50) -> list[SearchHit]:
    bm25_hits = fts.bm25_search(query, facets, k=k)        # FTS5
    embed_hits = vectorstore.query(query, facets, k=k)     # ChromaDB (existing)
    return rrf(bm25_hits, embed_hits, k=k, c=60)           # RRF fusion
```

- BM25 from FTS5 (~10-50 ms on 50k-row corpus).
- Embedding retrieval reuses existing ChromaDB + sentence-transformers; **also re-indexed to include `documents`** (currently invisible to RAG — known gap, fixed here).
- Reciprocal Rank Fusion: `score = Σ 1 / (c + rank)` across modalities. `c=60` per the original paper.
- **No cross-encoder reranker in W1** — deferred to W2 (where it pairs with the Contradiction Engine redesign). RRF gives most of the gain at zero model cost.

## 7. OCR pipeline for images

Email-attachment + chat-media images currently never OCR'd at ingest. W1:

1. At ingest, `metadata_extractor.extract_image()` runs Pillow → populates `photo_metadata`.
2. If the image likely contains text (heuristic: aspect ratio, dimensions, MIME), queue an async OCR job.
3. Worker runs `pytesseract` (fast, no GPU). On confidence < 0.6 → flag `ocr_status = needs_review`; user can manually trigger llava (existing button on Documents page).
4. Extracted text written to `attachments.extracted_text` / `documents.extracted_text`; FTS5 trigger picks it up automatically.

## 8. UI

### 8.1 Page 11 — Case Theory (dual-pane Workbench)

`st.columns([1, 1])` layout.

**Left pane (Argument editor):**
- Top: Case + Contradiction picker (uses `case_type` to colour-code entries: ⚖ family / 🔒 criminal)
- Contradiction header (headline, theme, status, linked Allegations)
- Argument list — each card editable inline (title, type, strength, reasoning_text, attached evidence with status badges)
- "Add Argument" button at bottom

**Right pane (Evidence Tray):**
- Search box (`st.session_state.tray_query` for persistence)
- Faceted filters (date range, source type, sender, has_attachment, taken_at present, theme tag)
- Recent + Pinned section above results
- Result list: source-type icon + 1-line metadata + thumbnail (photos) + status badge + "+ add" or "✓ attached"

**Click "+ add" on a tray result:**
- Creates Evidence + argument_evidence rows
- Default: snippet = whole row (`char_start = NULL`); role = "supports"
- One Streamlit rerun; tray filters preserved

**Click "✎ refine snippet"** on attached Evidence:
- `st.dialog` shows full source with paragraph-numbered list; user picks paragraph (Streamlit doesn't support text selection natively — paragraph picker is W1 fallback; revisit with custom component in a later wave)

**Keyboard shortcuts** (via `streamlit-shortcuts` or small custom JS):
- `cmd-K` → focus tray search
- `cmd-Enter` → attach focused tray result
- `esc` → close dialog

### 8.2 Page 12 — Search

- Search box at top
- Faceted filter sidebar (source, date, sender, has_attachment, has_taken_at, theme)
- Results: BM25-ranked, snippets highlighted via `snippet()`
- Each row: source-type icon + metadata + snippet + [+ Add to Argument] inline popover trigger + "View source" + "View as exhibit"
- Saved searches sidebar (stretch — basic save/load only)

### 8.3 Modified pages

- **Timeline (`pages/4_Timeline.py`)**: keyword filter switches to FTS5; each row gets [+ Add to Argument] inline popover; thread grouping unchanged. Inline raw `sqlite3.connect` calls (lines 400-403, 495-498) replaced with calls through `Database`.
- **Ask (`pages/5_Ask.py`)**: backend swap to `hybrid_search`; citations switch from LLM-generated strings to `Citation` tuples; click citation → jump to source row in Timeline. Date-filter silent-broadening bug fixed.
- **Export (`pages/8_Export.py`)**: new presets keyed by `case_type` (see §10).
- **Documents (`pages/9_Documents.py`)**: each document gets [+ Add to Argument] button; ingest pipeline auto-OCRs images + extracts EXIF; documents indexed in ChromaDB (closing the existing gap).

### 8.4 [+ Add to Argument] popover

Triggered from any row (Timeline, Search, Documents). Streamlit's `st.dialog` (compact, centered — Streamlit doesn't expose a true anchored-popover primitive in stable releases) sized small and pre-filled with `st.session_state.recent_argument_id`, so most cases are 1-click confirm. If true anchored popover UX is essential, a custom JS component is feasible later (out of W1).

- Type-ahead input switches target via fuzzy match on argument title
- Optional snippet selection (whole-row default)
- Optional role selection (supports/corroborates/refutes; default supports)
- Confirm

## 9. Photo metadata reliability

### 9.1 Extraction at ingest

`metadata_extractor.extract_image(path)` returns a `PhotoMetadata` Pydantic model. If `exif_present == False` (e.g., from WhatsApp), the row is still created with `width`/`height`/`orientation` populated from the file alone.

### 9.2 Reliability state

For each metadata field, the workbench shows one of:

- **reliable** — present, consistent, user has not touched
- **stripped** — auto-detected (field is None due to platform stripping)
- **unreliable** — user manually struck (with optional reason)
- **attested** — user added a sworn statement covering this field's content

UI: per-field row showing value, status indicator, and inline action (✗ strike with reason / + attest with sworn-statement form). Attestations persist in `metadata_attestations`.

### 9.3 Court export rendering

- Reliable fields: shown plainly
- Stripped fields: shown struck-through with footnote "Source platform stripped EXIF on transfer"
- Unreliable fields: struck-through with reason if provided
- Attestations: italic sworn paragraph below metadata block with `attested_by` and `attested_at` signature line

CEA s.31.1's standard ("evidence capable of supporting a finding") explicitly accepts user attestation as authentication when EXIF is gone.

## 10. Court-defensibility features

### 10.1 Hash verification

Every Evidence row stores `source_hash` at creation time. On render (preview or export):
- Re-compute hash of source row content
- Match → ✓ verified badge
- Mismatch → ⚠ check badge + warning in export schedule

Backfill on first run: existing rows in `attachments`, `documents`, `chat_messages` get `content_hash` populated. `chat_messages.content_hash` is now also written by ingest going forward.

### 10.2 Canada Evidence Act s.31.6 Certificate

Auto-generated PDF page included in every Court Bundle export — same template for both case types:

```
CERTIFICATE OF AUTHENTICITY
Canada Evidence Act, R.S.C. 1985, c. C-5, s. 31.6

I, [USER NAME], residing at [USER ADDRESS], CERTIFY that:

1. The electronic documents listed in the Schedule below were extracted
   from the source(s) identified by the operation of CasePulse, an
   electronic documents system, version [SOFTWARE VERSION].

2. The system was operating properly at the relevant time of extraction.

3. Each electronic document is identified by its SHA-256 hash, computed
   at the time of ingestion. Each hash matches the file as held by the
   system at the time of this certification.

4. The electronic documents have not been modified since ingestion.

5. The integrity of the electronic documents system can be verified by
   the system's audit log, which is hash-chained from genesis.

DATED at [LOCATION] this [DAY] day of [MONTH], [YEAR].

____________________________
Signature of [USER NAME]
```

Followed by the **Schedule of Electronic Documents** — a table of exhibit ref, description, source path, ingestion date, SHA-256 hash.

### 10.3 Audit log hash chain

W1 adds `prev_hash` and `row_hash` columns to `audit_log`. Application code on every insert: `row_hash = SHA-256(prev_hash || canonicalized(row_data))`. Verification scans the chain at app startup; chain breaks (deletions / tampering) raise a UI banner.

### 10.4 X-Ray defensive scan

[`x-ray`](https://github.com/freelawproject/x-ray) finds black rectangles drawn over still-extractable text in PDFs. W1 runs X-Ray:
- On every PDF you produce → blocks export by default if bad redactions are found, surfaces page numbers; user can override with explicit "Export anyway — I've reviewed page X" confirmation
- On every PDF you import → flags in Documents UI with the page numbers; surfaces opposing counsel's mistakes

## 11. Three-layer fidelity rendering

| Layer | Surface | Renderer |
|---|---|---|
| 1 — Tray result | Search results, Tray, Timeline rows, Ask citations | inline 1-line |
| 2 — Argument list | Workbench (attached evidence cards) | medium card with status |
| 3 — Court exhibit | "View as exhibit" + "Preview brief" + final export | full exhibit page |

Layer 3 has TWO entry points using the SAME renderer code path:
- "View as exhibit" button in workbench — single Evidence in court form
- "Preview brief" button at Contradiction level — full case-theory section
- Final Export — wraps the brief + all referenced exhibits + s.31.6 cert into one PDF

Both preview and canonical export use `weasyprint` over the same HTML templates — there's a single rendering pipeline, no risk of preview-vs-export divergence. The in-app preview is shown via Streamlit's PDF iframe embed (base64 data URL). Existing fpdf2-based legacy export presets (Timeline PDF, AI Package, Exhibit Bundle PDF) remain unchanged in W1.

## 12. Export templates (case_type-aware)

Four templates registered in `case_theory.templates.__init__.TEMPLATES`:

| Template | Default for | Wrapping | Exhibit numbering |
|---|---|---|---|
| `ontario_family` | `case_type='family'` | Affidavit + sworn cover sheets | Lettered A, B, C… |
| `ontario_criminal_motion` | `case_type='criminal'` (motion mode) | Affidavit + sworn cover sheets | Lettered A, B, C… |
| `ontario_criminal_trial` | `case_type='criminal'` (trial mode) | Defence Brief — no affidavit wrap | Numbered 1, 2, 3… |
| `generic` | `case_type='other'`, `'civil'` | Plain brief + simple cover | Lettered A, B, C… |

User can override the default at export time. Each template implements a `BriefTemplate` protocol with methods for: title page, theme heading, contradiction section, argument formatting, exhibit cover sheet, schedule, certificate page.

### 12.1 Ontario Family Law brief structure

```
[Title page — case style, parties, court file no., affiant, date]
[Index of Themes / Contradictions]

For each Theme:
  [Theme heading]
  For each Contradiction (display_order):
    [Headline]
    Allegations referenced:
      [Allegation #N — claim_text — source ref]
    For each Argument (sequence):
      [Argument heading: type · strength]
      [Reasoning text — inline cites: "(see Exhibit __)"]

[Schedule of Exhibits — A...Z table]
[s.31.6 Certificate of Authenticity]
```

**Exhibit cover sheet (Ontario Family):**

```
EXHIBIT "[A]"

This is Exhibit "[A]" referred to in the
Affidavit of [Affiant Name] sworn (or affirmed)
before me, this _____ day of ________, 20__.

____________________________________
A Commissioner for Taking Affidavits, etc.

[Description / source / EXIF / hash block]
[Body of original source — full content]
```

### 12.2 Ontario Criminal Trial defence brief structure

```
[Title page — R. v. [Accused], court file no., counsel of record, date]

[Theory of Defence] — short narrative paragraph entered at export time
via a textarea (last value cached in app_settings as theory_of_defence_draft;
optional — section is omitted if blank)

[Crown Allegations]
  For each Allegation, the corresponding Contradiction(s) we've assembled

For each Theme:
  [Theme heading]
  For each Contradiction (status='reviewed' or 'locked'):
    [Headline — what the Crown alleges]
    [Defence response — Arguments organized by type:]
      • Alibi
      • Self-contradiction (complainant's prior inconsistent statements)
      • Documentary
      • Timing
      • Pattern
    Each Argument cites Exhibits.

[List of Exhibits — Schedule with numbered refs]
[s.31.6 Certificate of Authenticity]
```

**Exhibit cover sheet (Criminal Trial — no affidavit wrap):**

```
EXHIBIT [1]

[Description / source / EXIF / hash block]
[Body of original source — full content]
```

Exhibits in this template are tendered through witness testimony at trial; no sworn cover is needed.

### 12.3 Ontario Criminal Motion (Charter / s.276 / preliminary motions)

Same structure as Family Law (affidavit + lettered exhibits) but with criminal case-style title page and substantive sections oriented around the legal issue under motion (e.g., *Charter* breach, admissibility).

### 12.4 Generic

Plain brief without procedural-form cover; same exhibit format as Family.

### 12.5 Affiant / commissioner fields

Stored in `app_settings` (set once via Settings page): `affiant_name`, `affiant_address`, `affiant_location`. Commissioner fields remain blank in the export — to be signed and witnessed before filing.

## 13. Migrations + ingest backfill

On first launch after W1 deployment:

1. Run new schema DDL (idempotent — `CREATE TABLE IF NOT EXISTS`)
2. Add `case_type` to `cases`, `prev_hash` and `row_hash` to `audit_log` if missing
3. Backfill `chat_messages.content_hash` for all existing rows
4. Build FTS5 indices from existing `emails`, `chat_messages`, `attachments`, `documents`, `annotations`
5. Queue EXIF extraction for existing image attachments + image documents (background job)
6. Queue ChromaDB indexing for existing `documents` rows (currently invisible)
7. One-time setup banner shows progress; workbench pages usable as soon as schema is up; FTS / EXIF / ChromaDB backfill runs in background

Per-step idempotency required — user may close app mid-backfill.

## 14. Performance considerations

- **FTS5 size**: ~30% of body text size in indices. For a ~50k-email corpus, expect FTS index ~300-500 MB.
- **Streamlit rerun cost**: every interaction reruns the page script. Tray search must be < 200 ms — FTS5 query + result rendering. Use `st.cache_data` for static components.
- **EXIF extraction**: Pillow ~50 ms / image — inline during ingest for new images.
- **OCR**: Tesseract on 1080p screenshot ~1-2 s; runs in background queue, never blocks ingest.
- **Hash verification on render**: cache by Evidence ID; recompute only when source changes (mtime check).
- **Unified timeline merge** in `database.py:946` is Python-side and slow past ~50k items — left for now (W1 doesn't degrade further; full fix in a later refactor wave).

## 15. Error handling

- **Schema validation failures (Pydantic)**: log + reject; surface in UI with field/reason.
- **FTS5 query parse errors**: catch `sqlite3.OperationalError`; show "query syntax error" with link to FTS syntax help.
- **Hash mismatch on render**: ⚠ badge; do not block export, but cert schedule disclaims the row.
- **Missing source files** (attachment file deleted): "source unavailable" in workbench; export skips with warning footnote.
- **OCR failure**: row stays at `ocr_status = needs_review`; user can manually retry with llava.
- **EXIF extraction failure**: row created with all metadata fields NULL + `exif_present = 0`; treated as "stripped".
- **Audit chain break**: app starts but shows banner; user can re-baseline (records new genesis row, prior chain marked as severed).

## 16. Testing

- **Unit tests** (`pytest`) for `case_theory.repository`, `evidence_resolver`, `metadata_extractor`, `search.fts`, `search.retrieval`, `Citation` round-trip, all four `templates/`.
- **Property-based tests** (`hypothesis`) for parsers (forwarded email, WhatsApp, AppClose) — generate random conformant inputs, confirm round-trip + idempotency.
- **Golden-file tests** for `exhibit_renderer` and `brief_renderer` across all 4 templates: fixture input → rendered HTML (deterministic; the actual template output) compared against committed expected HTML. Plus a smoke test that asserts the resulting PDF (via `pdftotext` extraction) contains key strings — exhibit headers, cert text, schedule rows. Avoids brittle PDF-binary diffs.
- **Snapshot tests** for FTS5 query → result IDs (catches ranking regressions).
- **Migration tests** — start from current schema, run migration, verify schema + data integrity; round-trip backfills.
- **Smoke tests** — Streamlit pages 4, 5, 8, 9, 11, 12 load with a fixture DB.
- **CI** (`/.github/workflows/ci.yml`): GitHub Actions runs tests on every PR. Currently only the release-build workflow exists — W1 adds PR validation.

Test data: anonymized corpus of ~200 fixture rows (sample emails, chats, photo with stripped EXIF, photo with full EXIF, scanned PDF requiring OCR, document with bad redaction).

## 17. Security and threat model

- New tables don't change the existing threat model materially. Photo metadata + attestations stored plaintext SQLite (consistent with current state).
- Audit-log hash chain provides tamper-evidence within the database; the database file itself remains plaintext on disk (encryption is a separate later wave).
- s.31.6 cert is signed manually by the user after export. Crypto-signed certs (using `python-cryptography`) deferred.
- AI Assistant on Discover Senders has unsupervised DB-write authority via parsed JSON (current bug; **explicitly out of W1**, separate small follow-up).

## 18. Open questions

- **Snippet selection UX** — Streamlit doesn't support text selection natively. W1 uses paragraph-picker as fallback; revisit with custom component in W2 if it feels clumsy.
- **Dual-pane on small screens** — Streamlit columns collapse below ~768px; W1 falls back to single-column with tabbed Workbench/Tray on mobile (acceptable, dev machine usage primary).
- **Multi-case UI** — schema is `case_id`-aware; UI assumes one active case at a time (case picker in sidebar). Fast switching between family + criminal cases is essential since the same evidence flows into both.
- **Cross-case evidence reuse** — Evidence rows are not case-scoped (only Argument is); same `evidence_id` can appear in arguments across cases. UI should make this discoverable ("This evidence is also cited in Family Argument #5").

## 19. Acceptance criteria for "W1 done"

- [ ] All new tables created and migrations applied successfully on existing DB
- [ ] FTS5 search returns results for "test" within 200 ms on 10k-row corpus
- [ ] User can: create a Theme, create a Contradiction under it, link an Allegation, add an Argument with type+strength, attach 3 Evidence items via Tray, refine a snippet, strike a metadata field, add an attestation
- [ ] [+ Add to Argument] popover works from Timeline + Search + Documents pages
- [ ] "View as exhibit" button renders Ontario Family-style exhibit cover with s.31.6 cert reference
- [ ] "Preview brief" button renders full case-theory section
- [ ] All four export templates produce valid PDFs from the same case-theory data: `ontario_family`, `ontario_criminal_trial`, `ontario_criminal_motion`, `generic`
- [ ] `case_type` on each Case correctly defaults the export template
- [ ] Hash verification badges appear correctly for verified + mismatched evidence
- [ ] Audit log hash chain verifies on startup
- [ ] X-Ray scan flags a known-bad-redaction PDF in fixtures
- [ ] All new tests pass; CI runs on PR; no regressions to existing manual flows
- [ ] Streamlit pages 11, 12 load and render without errors
- [ ] EXIF auto-extracted on new image ingest; OCR queued via Tesseract
- [ ] Documents table now indexed in ChromaDB; Ask page can find imported documents
- [ ] Ask page date-filter silent-broadening bug fixed
- [ ] `chat_messages.content_hash` populated for all existing + new rows
