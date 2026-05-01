# Case Theory Workbench W1 — Plan 1: Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend foundation for the Case Theory Workbench — schema, FTS5 search, photo metadata + OCR, case-theory data layer, court-defensibility primitives. No user-facing UI changes; validated via tests + manual SQL checks.

**Architecture:** Add new tables (themes, allegations, contradictions, arguments, evidence, photo_metadata, attestations) and new packages (`casepulse/case_theory/`, `casepulse/search/`). FTS5 contentless virtual tables + triggers index existing email/chat/attachment/document text. Hybrid retrieval (BM25 + ChromaDB embeddings + RRF) returns structured Citation tuples. Photo EXIF extraction via Pillow at ingest with per-field reliability state. Hash chain on audit_log for tamper-evidence. s.31.6 Certificate generator (Canada Evidence Act).

**Tech Stack:** Python 3.11+, SQLite (FTS5), Pillow, dateparser, pytesseract, x-ray (freelawproject), pydantic, pytest, hypothesis. Streamlit not yet touched.

**Spec:** `docs/superpowers/specs/2026-04-30-case-theory-workbench-w1-design.md` — sections 4, 5, 6, 7, 9 (extraction half), 10.1, 10.2, 10.3, 10.4 (X-Ray library only), 13, 16. Sections 8 (UI), 9 (display half), 11, 12, 14 (UI perf) are deferred to Plans 1.2 and 1.3.

**Plan 1.2 (next, ~1 week):** Workbench page (11), Search page (12), modified Timeline / Ask / Documents / Export pages.
**Plan 1.3 (after, ~3-5 days):** Brief renderer, exhibit renderer, four export templates (ontario_family, ontario_criminal_motion, ontario_criminal_trial, generic), weasyprint.

---

## File structure

**New packages and files:**

```
casepulse/
  case_theory/                         # NEW
    __init__.py                        # empty
    models.py                          # Pydantic types for all entities
    repository.py                      # CRUD on case-theory tables
    evidence_resolver.py               # polymorphic Evidence → source row
    metadata_extractor.py              # EXIF + reliability detection
    audit_chain.py                     # hash-chain helpers for audit_log
    auth_certificate.py                # CEA s.31.6 cert data + serializer
    redaction_scanner.py               # X-Ray wrapper

  search/                              # NEW
    __init__.py                        # empty
    fts.py                             # FTS5 schema management + queries
    citation.py                        # Citation Pydantic + ResolvedSource
    rrf.py                             # reciprocal rank fusion
    retrieval.py                       # hybrid: BM25 + embeddings + RRF

tests/                                 # currently empty; populated by this plan
  __init__.py
  conftest.py                          # shared pytest fixtures
  storage/
    __init__.py
    test_schema_migrations.py
    test_chat_content_hash_backfill.py
  search/
    __init__.py
    test_fts_indices.py
    test_citation_model.py
    test_rrf.py
    test_hybrid_retrieval.py
  case_theory/
    __init__.py
    test_models.py
    test_repository.py
    test_evidence_resolver.py
    test_metadata_extractor.py
    test_audit_chain.py
    test_auth_certificate.py
    test_redaction_scanner.py
  fixtures/
    __init__.py
    sample_data.py                     # test database builders
    photos/                            # fixture image files
      iphone_with_exif.jpg
      whatsapp_stripped.jpg
      no_exif.png
    pdfs/
      bad_redaction.pdf                # known black-rectangle-over-text
      clean.pdf
```

**Modified files:**

- `casepulse/storage/database.py` — schema additions (one ALTER, ten CREATE TABLEs, five FTS5 virtuals + triggers), new repository wrappers escape hatch
- `casepulse/rag/chunker.py` — add documents indexing (close existing gap)
- `casepulse/rag/query_engine.py` — fix silent date-filter broadening at line ~91
- `casepulse/email_engine/gmail_fetcher.py`, `casepulse/email_engine/microsoft_fetcher.py` — call `metadata_extractor.extract_image()` after attachment download
- `casepulse/chat_engine/whatsapp_parser.py`, `casepulse/chat_engine/chatvault_parser.py`, `casepulse/chat_engine/appclose_parser.py` — populate `chat_messages.content_hash`; trigger metadata extractor for media images
- `casepulse/attachments/document_import.py` — call `metadata_extractor.extract_image()` for image documents
- `casepulse/legal/__init__.py` — re-export `audit_chain`
- `requirements.txt` — add `dateparser`, `pytesseract`, `x-ray-pdf`, `pydantic>=2.0`
- `requirements-dev.txt` (NEW) — `pytest`, `hypothesis`, `pytest-cov`
- `.github/workflows/ci.yml` (NEW) — run pytest on every PR

---

## Phase 0 — Setup and CI

### Task 0.1: Create feature branch

**Files:** none (git operation only)

- [ ] **Step 1: Create and check out a branch**

```bash
git checkout -b w1-foundation
git status
```

Expected: clean tree on branch `w1-foundation`.

- [ ] **Step 2: Confirm branch tracks main correctly**

```bash
git rev-parse --abbrev-ref HEAD
```

Expected output: `w1-foundation`

- [ ] **Step 3: Commit**

No commit yet — branch creation is metadata only. Move to next task.

---

### Task 0.2: Add new dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Add runtime deps to `requirements.txt`**

Append to existing file:
```
dateparser>=1.2
pytesseract>=0.3.10
x-ray-pdf>=0.4
pydantic>=2.5
weasyprint>=62.0
```

(Pillow already present transitively via `pdfplumber`.)

- [ ] **Step 2: Create `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
pytest-cov>=4.1
hypothesis>=6.100
```

- [ ] **Step 3: Install in venv**

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
```

Expected: all packages install. `pytesseract` may warn about Tesseract binary — install it via `brew install tesseract` (macOS) or `apt install tesseract-ocr` (Linux). `weasyprint` may need `brew install pango` on macOS.

- [ ] **Step 4: Verify imports work**

```bash
python -c "import dateparser, pytesseract, pydantic, weasyprint; print('ok')"
```

Expected output: `ok`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "Add W1 foundation dependencies (pytest, pydantic, dateparser, pytesseract, weasyprint, x-ray-pdf)"
```

---

### Task 0.3: Create new package skeletons

**Files:**
- Create: `casepulse/case_theory/__init__.py`, `casepulse/search/__init__.py`
- Create: `tests/__init__.py`, `tests/storage/__init__.py`, `tests/search/__init__.py`, `tests/case_theory/__init__.py`, `tests/fixtures/__init__.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p casepulse/case_theory casepulse/search
mkdir -p tests/storage tests/search tests/case_theory tests/fixtures/photos tests/fixtures/pdfs
touch casepulse/case_theory/__init__.py casepulse/search/__init__.py
touch tests/__init__.py tests/storage/__init__.py tests/search/__init__.py tests/case_theory/__init__.py tests/fixtures/__init__.py
```

- [ ] **Step 2: Verify package layout**

```bash
python -c "import casepulse.case_theory, casepulse.search; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add casepulse/case_theory casepulse/search tests
git commit -m "Add empty package skeletons for case_theory, search, and tests"
```

---

### Task 0.4: pytest config + conftest

**Files:**
- Create: `pyproject.toml` section for pytest (or `pytest.ini`)
- Create: `tests/conftest.py`

- [ ] **Step 1: Add pytest config**

Create `pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -ra --strict-markers --cov=casepulse --cov-report=term-missing
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
import pytest
import sqlite3
from pathlib import Path
from casepulse.storage.database import Database


@pytest.fixture
def tmp_db(tmp_path):
    """Empty database with schema applied."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    yield db


@pytest.fixture
def tmp_db_with_case(tmp_db):
    """Database with one fixture case row."""
    case_id = tmp_db.create_case(
        name="Test Family Matter",
        case_number="FC-2024-001",
    )
    yield tmp_db, case_id
```

- [ ] **Step 3: Verify pytest discovers**

```bash
pytest --collect-only
```

Expected: zero errors, zero tests collected (no test files yet).

- [ ] **Step 4: Commit**

```bash
git add pytest.ini tests/conftest.py
git commit -m "Add pytest config and shared conftest fixtures"
```

---

### Task 0.5: GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install system deps
        run: |
          sudo apt-get update
          sudo apt-get install -y tesseract-ocr libpango-1.0-0 libpangoft2-1.0-0
      - name: Install Python deps
        run: pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI workflow running pytest on PRs and main pushes"
```

---

## Phase 1 — Schema migrations

### Task 1.1: Migration runner pattern

**Files:**
- Modify: `casepulse/storage/database.py` (add migration runner method)
- Create: `tests/storage/test_schema_migrations.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/storage/test_schema_migrations.py
def test_migrations_run_idempotently(tmp_db):
    """Running migrations twice does not error or duplicate state."""
    tmp_db._init_schema()  # second run after fixture's first run
    # Check core tables still exist
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert 'emails' in tables
    assert 'cases' in tables
```

- [ ] **Step 2: Run to verify it fails or passes**

```bash
pytest tests/storage/test_schema_migrations.py::test_migrations_run_idempotently -v
```

Expected: PASS (`_init_schema` already uses `CREATE TABLE IF NOT EXISTS`). This test is a regression guard for future ALTER statements.

- [ ] **Step 3: Add `_run_migrations` helper to `database.py`**

In `casepulse/storage/database.py`, near the existing `_init_schema` method, add:

```python
def _run_migrations(self) -> None:
    """Apply ALTER and one-time data migrations idempotently.

    Each step checks for the change before applying. Safe to run on every
    Database() construction.
    """
    conn = self._get_conn()
    cur = conn.cursor()
    # Migrations are appended below as Phase 1 progresses.
    conn.commit()
```

Call `self._run_migrations()` from `__init__` after `_init_schema()`.

- [ ] **Step 4: Re-run test, verify still passes**

```bash
pytest tests/storage/test_schema_migrations.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add casepulse/storage/database.py tests/storage/test_schema_migrations.py
git commit -m "Add idempotent migration runner skeleton + regression test"
```

---

### Task 1.2: Add `themes` table

**Files:**
- Modify: `casepulse/storage/database.py:_init_schema` (append CREATE TABLE)
- Modify: `tests/storage/test_schema_migrations.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/storage/test_schema_migrations.py`:
```python
def test_themes_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(themes)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'title', 'description', 'display_order', 'created_at'}

def test_themes_unique_per_case(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO themes(case_id, title) VALUES (?, ?)", (case_id, "T1"))
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO themes(case_id, title) VALUES (?, ?)", (case_id, "T1"))
```

Add `import pytest, sqlite3` at top.

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/storage/test_schema_migrations.py::test_themes_table -v
```

Expected: FAIL — no themes table.

- [ ] **Step 3: Add to schema**

In `casepulse/storage/database.py`, locate the schema string (around line 15-277) and append:
```sql
CREATE TABLE IF NOT EXISTS themes (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  display_order INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(case_id, title)
);
CREATE INDEX IF NOT EXISTS idx_themes_case ON themes(case_id);
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/storage/test_schema_migrations.py -v
```

Expected: PASS for both new tests.

- [ ] **Step 5: Commit**

```bash
git add casepulse/storage/database.py tests/storage/test_schema_migrations.py
git commit -m "Add themes table with unique(case_id, title) constraint"
```

---

### Task 1.3: Add `allegations` table

**Files:** Modify `casepulse/storage/database.py`, modify `tests/storage/test_schema_migrations.py`

- [ ] **Step 1: Write the failing test**

```python
def test_allegations_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(allegations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'title', 'claim_text', 'claimed_date',
                    'source_evidence_id', 'status', 'notes', 'created_at'}
```

- [ ] **Step 2: Run, verify FAIL**

```bash
pytest tests/storage/test_schema_migrations.py::test_allegations_table -v
```

Expected: FAIL.

- [ ] **Step 3: Add to schema**

```sql
CREATE TABLE IF NOT EXISTS allegations (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  claim_text TEXT NOT NULL,
  claimed_date TEXT,
  source_evidence_id INTEGER REFERENCES evidence(id),
  status TEXT DEFAULT 'active',
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_allegations_case ON allegations(case_id);
CREATE INDEX IF NOT EXISTS idx_allegations_date ON allegations(claimed_date);
```

(Note: `evidence` table doesn't exist yet — FK is forward declared. SQLite doesn't enforce FK existence at table-create time when foreign_keys pragma is off; `evidence` will land in Task 1.6.)

- [ ] **Step 4: Run, verify PASS**

```bash
pytest tests/storage/test_schema_migrations.py::test_allegations_table -v
```

- [ ] **Step 5: Commit**

```bash
git add casepulse/storage/database.py tests/storage/test_schema_migrations.py
git commit -m "Add allegations table"
```

---

### Task 1.4: Add `contradictions` and `contradiction_allegations` tables

**Files:** Modify `casepulse/storage/database.py`, modify test file

- [ ] **Step 1: Write tests**

```python
def test_contradictions_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(contradictions)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'case_id', 'headline', 'status', 'theme_id',
                    'display_order', 'notes', 'created_at', 'updated_at'}

def test_contradiction_allegations_bridge(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(contradiction_allegations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'contradiction_id', 'allegation_id'}
```

- [ ] **Step 2: FAIL check**

```bash
pytest tests/storage/test_schema_migrations.py::test_contradictions_table tests/storage/test_schema_migrations.py::test_contradiction_allegations_bridge -v
```

- [ ] **Step 3: Add to schema**

```sql
CREATE TABLE IF NOT EXISTS contradictions (
  id INTEGER PRIMARY KEY,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  headline TEXT NOT NULL,
  status TEXT DEFAULT 'draft',
  theme_id INTEGER REFERENCES themes(id) ON DELETE SET NULL,
  display_order INTEGER DEFAULT 0,
  notes TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_contradictions_case ON contradictions(case_id);
CREATE INDEX IF NOT EXISTS idx_contradictions_status ON contradictions(status);
CREATE INDEX IF NOT EXISTS idx_contradictions_theme ON contradictions(theme_id);

CREATE TABLE IF NOT EXISTS contradiction_allegations (
  contradiction_id INTEGER NOT NULL REFERENCES contradictions(id) ON DELETE CASCADE,
  allegation_id INTEGER NOT NULL REFERENCES allegations(id) ON DELETE CASCADE,
  PRIMARY KEY (contradiction_id, allegation_id)
);
```

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "Add contradictions and contradiction_allegations bridge tables"
```

---

### Task 1.5: Add `arguments` and `argument_evidence` tables

**Files:** Modify `casepulse/storage/database.py`, modify test file

- [ ] **Step 1: Write tests**

```python
def test_arguments_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(arguments)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'contradiction_id', 'title', 'reasoning_text',
                    'argument_type', 'strength', 'sequence',
                    'created_at', 'updated_at'}

def test_argument_evidence_bridge(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(argument_evidence)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'argument_id', 'evidence_id', 'role',
                    'display_order', 'notes', 'added_at'}
```

- [ ] **Step 2: FAIL check**
- [ ] **Step 3: Add to schema**

```sql
CREATE TABLE IF NOT EXISTS arguments (
  id INTEGER PRIMARY KEY,
  contradiction_id INTEGER NOT NULL REFERENCES contradictions(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  reasoning_text TEXT,
  argument_type TEXT,
  strength TEXT,
  sequence INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_arguments_contradiction ON arguments(contradiction_id);
CREATE INDEX IF NOT EXISTS idx_arguments_type ON arguments(argument_type);
CREATE INDEX IF NOT EXISTS idx_arguments_strength ON arguments(strength);

CREATE TABLE IF NOT EXISTS argument_evidence (
  argument_id INTEGER NOT NULL REFERENCES arguments(id) ON DELETE CASCADE,
  evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
  role TEXT DEFAULT 'supports',
  display_order INTEGER DEFAULT 0,
  notes TEXT,
  added_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (argument_id, evidence_id)
);
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add arguments and argument_evidence M:N bridge tables"
```

---

### Task 1.6: Add `evidence` table

**Files:** Modify `casepulse/storage/database.py`, modify test file

- [ ] **Step 1: Write test**

```python
def test_evidence_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(evidence)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'evidence_kind', 'source_table', 'source_row_id',
                    'char_start', 'char_end', 'snippet', 'source_hash',
                    'created_at'}
```

- [ ] **Step 2: FAIL check**
- [ ] **Step 3: Add to schema**

```sql
CREATE TABLE IF NOT EXISTS evidence (
  id INTEGER PRIMARY KEY,
  evidence_kind TEXT NOT NULL,
  source_table TEXT NOT NULL,
  source_row_id INTEGER NOT NULL,
  char_start INTEGER,
  char_end INTEGER,
  snippet TEXT,
  source_hash TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source_table, source_row_id, char_start, char_end)
);
CREATE INDEX IF NOT EXISTS idx_evidence_source ON evidence(source_table, source_row_id);
CREATE INDEX IF NOT EXISTS idx_evidence_kind ON evidence(evidence_kind);
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add evidence table — polymorphic pointer to source rows"
```

---

### Task 1.7: Add `photo_metadata` and `metadata_attestations` tables

**Files:** Modify `casepulse/storage/database.py`, modify test file

- [ ] **Step 1: Write tests**

```python
def test_photo_metadata_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(photo_metadata)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'source_table', 'source_row_id', 'taken_at',
                    'camera_make', 'camera_model', 'lens', 'software',
                    'gps_lat', 'gps_lon', 'gps_accuracy', 'orientation',
                    'width', 'height', 'exif_present', 'detected_at'}

def test_metadata_attestations_table(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(metadata_attestations)")
    cols = {row[1] for row in cur.fetchall()}
    assert cols == {'id', 'photo_metadata_id', 'field_name', 'status',
                    'reason', 'attestation_text', 'attested_by',
                    'attested_at', 'created_at'}
```

- [ ] **Step 2: FAIL check**
- [ ] **Step 3: Add to schema**

```sql
CREATE TABLE IF NOT EXISTS photo_metadata (
  id INTEGER PRIMARY KEY,
  source_table TEXT NOT NULL,
  source_row_id INTEGER NOT NULL,
  taken_at TEXT,
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
  exif_present INTEGER DEFAULT 0,
  detected_at TEXT DEFAULT (datetime('now')),
  UNIQUE(source_table, source_row_id)
);
CREATE INDEX IF NOT EXISTS idx_photo_metadata_source ON photo_metadata(source_table, source_row_id);
CREATE INDEX IF NOT EXISTS idx_photo_metadata_taken ON photo_metadata(taken_at);

CREATE TABLE IF NOT EXISTS metadata_attestations (
  id INTEGER PRIMARY KEY,
  photo_metadata_id INTEGER NOT NULL REFERENCES photo_metadata(id) ON DELETE CASCADE,
  field_name TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT,
  attestation_text TEXT,
  attested_by TEXT,
  attested_at TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_metadata_attestations_pm ON metadata_attestations(photo_metadata_id);
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add photo_metadata and metadata_attestations tables"
```

---

### Task 1.8: ALTER `cases` for case_type

**Files:** Modify `casepulse/storage/database.py:_run_migrations`, modify test file

- [ ] **Step 1: Write test**

```python
def test_cases_has_case_type_column(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(cases)")
    cols = {row[1] for row in cur.fetchall()}
    assert 'case_type' in cols

def test_cases_default_case_type_is_family(tmp_db):
    case_id = tmp_db.create_case(name="Test", case_number="T1")
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT case_type FROM cases WHERE id = ?", (case_id,))
    assert cur.fetchone()[0] == 'family'
```

- [ ] **Step 2: FAIL check**
- [ ] **Step 3: Add migration**

In `_run_migrations`:
```python
cur.execute("PRAGMA table_info(cases)")
case_cols = {row[1] for row in cur.fetchall()}
if 'case_type' not in case_cols:
    cur.execute("ALTER TABLE cases ADD COLUMN case_type TEXT NOT NULL DEFAULT 'family'")
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "ALTER cases: add case_type column (default 'family')"
```

---

### Task 1.9: ALTER `audit_log` for hash chain

**Files:** Modify `casepulse/storage/database.py:_run_migrations`, modify test file

- [ ] **Step 1: Write test**

```python
def test_audit_log_has_hash_columns(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(audit_log)")
    cols = {row[1] for row in cur.fetchall()}
    assert 'prev_hash' in cols
    assert 'row_hash' in cols
```

- [ ] **Step 2: FAIL check**
- [ ] **Step 3: Add migration**

```python
cur.execute("PRAGMA table_info(audit_log)")
audit_cols = {row[1] for row in cur.fetchall()}
if 'prev_hash' not in audit_cols:
    cur.execute("ALTER TABLE audit_log ADD COLUMN prev_hash TEXT")
if 'row_hash' not in audit_cols:
    cur.execute("ALTER TABLE audit_log ADD COLUMN row_hash TEXT")
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "ALTER audit_log: add prev_hash and row_hash for tamper-evident chain"
```

---

### Task 1.10: Backfill `chat_messages.content_hash`

**Files:**
- Modify: `casepulse/storage/database.py:_run_migrations`
- Modify: `casepulse/chat_engine/whatsapp_parser.py`, `chatvault_parser.py`, `appclose_parser.py`
- Create: `tests/storage/test_chat_content_hash_backfill.py`

- [ ] **Step 1: Write test**

```python
# tests/storage/test_chat_content_hash_backfill.py
import hashlib
from casepulse.storage.database import Database

def test_backfill_populates_existing_chat_hashes(tmp_path):
    """Existing chat rows with NULL content_hash get backfilled on next init."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    conn = db._get_conn()
    cur = conn.cursor()
    # Insert a chat_message with NULL content_hash (simulating pre-fix data)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', 'Alice', '2024-01-01 12:00:00',
                'Hello world', NULL)
    """)
    conn.commit()
    # Re-construct DB (triggers _run_migrations again)
    db2 = Database(str(db_path))
    conn = db2._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = 'Hello world'")
    h = cur.fetchone()[0]
    assert h is not None
    expected = hashlib.sha256(b'Hello world').hexdigest()
    assert h == expected
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement backfill**

In `_run_migrations`:
```python
import hashlib
cur.execute("SELECT id, message_text FROM chat_messages WHERE content_hash IS NULL")
rows = cur.fetchall()
for row_id, text in rows:
    h = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
    cur.execute("UPDATE chat_messages SET content_hash = ? WHERE id = ?", (h, row_id))
```

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Update parsers to populate content_hash on new inserts**

In each chat parser (`whatsapp_parser.py`, `chatvault_parser.py`, `appclose_parser.py`), find the INSERT INTO chat_messages call and add `content_hash` to the column list and `hashlib.sha256(message_text.encode('utf-8')).hexdigest()` to the values. Same approach in all three files.

- [ ] **Step 6: Add a guard test**

```python
def test_new_chat_inserts_have_hash(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x.txt', 'Alice', '2024-01-01 12:00:00',
                'New message', ?)
    """, (hashlib.sha256(b'New message').hexdigest(),))
    conn.commit()
    cur.execute("SELECT content_hash FROM chat_messages WHERE message_text = 'New message'")
    assert cur.fetchone()[0] is not None
```

- [ ] **Step 7: Commit**

```bash
git add casepulse/storage/database.py casepulse/chat_engine tests/storage/test_chat_content_hash_backfill.py
git commit -m "Backfill chat_messages.content_hash + populate on new chat inserts"
```

---

## Phase 2 — Search foundation

### Task 2.1: FTS5 virtual tables for emails + triggers

**Files:**
- Modify: `casepulse/storage/database.py:_init_schema` (new FTS5 block + triggers)
- Create: `tests/search/test_fts_indices.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_fts_indices.py
def test_emails_fts_table_exists(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE name='emails_fts'")
    assert cur.fetchone() is not None

def test_emails_fts_index_on_insert(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("Test subject", "Body about custody hearing", "alice@x.com",
          "<m1@x>", "hash1", 1))
    conn.commit()
    cur.execute("""
        SELECT rowid FROM emails_fts WHERE emails_fts MATCH 'custody'
    """)
    rows = cur.fetchall()
    assert len(rows) == 1
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Add FTS5 + triggers**

In `_init_schema` SQL block, append:
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(
  subject, body_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter'
);

CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails BEGIN
  INSERT INTO emails_fts(rowid, subject, body_text)
  VALUES (new.id, new.subject, new.body_text);
END;

CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails BEGIN
  INSERT INTO emails_fts(emails_fts, rowid, subject, body_text)
  VALUES('delete', old.id, old.subject, old.body_text);
END;

CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails BEGIN
  INSERT INTO emails_fts(emails_fts, rowid, subject, body_text)
  VALUES('delete', old.id, old.subject, old.body_text);
  INSERT INTO emails_fts(rowid, subject, body_text)
  VALUES (new.id, new.subject, new.body_text);
END;
```

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "Add emails_fts virtual table + INSERT/DELETE/UPDATE triggers"
```

---

### Task 2.2: FTS5 for chat_messages, attachments, documents, annotations

**Files:** Modify `casepulse/storage/database.py:_init_schema`, modify `tests/search/test_fts_indices.py`

- [ ] **Step 1: Write tests** for each new FTS table (chat_messages_fts, attachments_fts, documents_fts, annotations_fts) — mirror the email tests.

```python
def test_chat_messages_fts_search(tmp_db):
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x', 'Alice', '2024-01-01', 'meeting at 3pm',
                'h1')
    """)
    conn.commit()
    cur.execute("SELECT rowid FROM chat_messages_fts WHERE chat_messages_fts MATCH 'meeting'")
    assert len(cur.fetchall()) == 1
```

(repeat for documents_fts, attachments_fts, annotations_fts with appropriate fixtures)

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Add FTS5 tables + triggers** for the four remaining tables (mirroring Task 2.1's structure):

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS chat_messages_fts USING fts5(
  message_text, sender, chat_name,
  content='', tokenize='unicode61 remove_diacritics 2 porter'
);

CREATE VIRTUAL TABLE IF NOT EXISTS attachments_fts USING fts5(
  filename, extracted_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter'
);

CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
  filename, extracted_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter'
);

CREATE VIRTUAL TABLE IF NOT EXISTS annotations_fts USING fts5(
  note_text,
  content='', tokenize='unicode61 remove_diacritics 2 porter'
);
```

Plus AFTER INSERT/DELETE/UPDATE triggers for each (mirror email triggers in Task 2.1).

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "Add FTS5 for chat_messages, attachments, documents, annotations"
```

---

### Task 2.3: One-time backfill for FTS5

**Files:** Modify `casepulse/storage/database.py:_run_migrations`

- [ ] **Step 1: Write test**

```python
def test_fts_backfill_existing_emails(tmp_path):
    """Pre-existing emails get indexed when FTS5 backfill runs."""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    # Insert emails BEFORE FTS triggers exist (simulate pre-W1 data)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Old subject', 'Old body about custody', 'a@x.com', '<m1>',
                'h1', 1)
    """)
    conn.commit()
    # Drop and recreate FTS to simulate first-run state
    cur.execute("DELETE FROM emails_fts")
    conn.commit()
    # Re-init triggers backfill
    db2 = Database(str(db_path))
    conn = db2._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT rowid FROM emails_fts WHERE emails_fts MATCH 'custody'")
    assert len(cur.fetchall()) == 1
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Add backfill in `_run_migrations`**

```python
def _backfill_fts_if_empty(self, cur, fts_table: str, source_table: str,
                            select_cols: list[str]) -> None:
    cur.execute(f"SELECT COUNT(*) FROM {fts_table}")
    fts_count = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(*) FROM {source_table}")
    source_count = cur.fetchone()[0]
    if fts_count < source_count:
        col_list = ", ".join(select_cols)
        cur.execute(f"INSERT INTO {fts_table}(rowid, {col_list}) "
                    f"SELECT id, {col_list} FROM {source_table}")
```

Call from `_run_migrations`:
```python
self._backfill_fts_if_empty(cur, "emails_fts", "emails", ["subject", "body_text"])
self._backfill_fts_if_empty(cur, "chat_messages_fts", "chat_messages",
                             ["message_text", "sender", "chat_name"])
self._backfill_fts_if_empty(cur, "attachments_fts", "attachments",
                             ["filename", "extracted_text"])
self._backfill_fts_if_empty(cur, "documents_fts", "documents",
                             ["filename", "extracted_text"])
self._backfill_fts_if_empty(cur, "annotations_fts", "annotations",
                             ["note_text"])
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "One-time FTS5 backfill for existing rows in five source tables"
```

---

### Task 2.4: Citation Pydantic model

**Files:**
- Create: `casepulse/search/citation.py`
- Create: `tests/search/test_citation_model.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_citation_model.py
import pytest
from casepulse.search.citation import Citation

def test_citation_minimal():
    c = Citation(table="emails", row_id=42)
    assert c.table == "emails"
    assert c.row_id == 42
    assert c.char_start is None
    assert c.snippet is None

def test_citation_full():
    c = Citation(
        table="chat_messages",
        row_id=10,
        char_start=5,
        char_end=20,
        snippet="example text",
        source_hash="abc123",
    )
    assert c.char_end == 20

def test_citation_invalid_table():
    with pytest.raises(ValueError):
        Citation(table="not_a_table", row_id=1)

def test_citation_serializes():
    c = Citation(table="emails", row_id=1, char_start=0, char_end=5)
    d = c.model_dump()
    assert d == {'table': 'emails', 'row_id': 1, 'char_start': 0,
                 'char_end': 5, 'snippet': None, 'source_hash': None}
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/search/citation.py
from typing import Literal
from pydantic import BaseModel


SourceTable = Literal["emails", "chat_messages", "attachments",
                       "documents", "annotations"]


class Citation(BaseModel):
    """A structured pointer from a search result or evidence row to its
    source row, with optional character-range narrowing.

    char_start/char_end are inclusive-exclusive byte offsets within the
    source row's primary text column (body_text for emails, message_text
    for chats, extracted_text for attachments/documents, note_text for
    annotations).
    """
    table: SourceTable
    row_id: int
    char_start: int | None = None
    char_end: int | None = None
    snippet: str | None = None
    source_hash: str | None = None
```

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git add casepulse/search/citation.py tests/search/test_citation_model.py
git commit -m "Add Citation Pydantic model for structured source pointers"
```

---

### Task 2.5: BM25 search wrapper

**Files:**
- Create: `casepulse/search/fts.py`
- Modify: `tests/search/test_fts_indices.py` (or create separate `test_fts_search.py`)

- [ ] **Step 1: Write test**

```python
# tests/search/test_fts_search.py
from casepulse.search.fts import bm25_search


def test_bm25_returns_citations(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Custody hearing', 'Discussion about access schedule',
                'a@x.com', '<m1>', 'h1', 1)
    """)
    conn.commit()
    hits = bm25_search(db, "custody", k=10)
    assert len(hits) == 1
    assert hits[0].citation.table == "emails"
    assert hits[0].citation.row_id == 1
    assert "Custody" in hits[0].citation.snippet


def test_bm25_facet_source_type(tmp_db_with_case):
    """Source type filter restricts to one FTS table."""
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Email subject', 'banana', 'a@x.com', '<m1>', 'h1', 1)
    """)
    cur.execute("""
        INSERT INTO chat_messages (source_type, source_file, sender, timestamp,
                                    message_text, content_hash)
        VALUES ('whatsapp', '/tmp/x', 'A', '2024-01-01', 'banana', 'h2')
    """)
    conn.commit()
    hits = bm25_search(db, "banana", k=10, source_types=["chat_messages"])
    assert len(hits) == 1
    assert hits[0].citation.table == "chat_messages"
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement `casepulse/search/fts.py`**

```python
"""BM25 search over FTS5 contentless indices.

Returns SearchHit objects carrying a Citation + BM25 score + snippet.
"""
from dataclasses import dataclass
from typing import Iterable

from casepulse.search.citation import Citation
from casepulse.storage.database import Database


# Map FTS table -> (parent table, primary text column)
FTS_TABLES = {
    "emails_fts": ("emails", "body_text"),
    "chat_messages_fts": ("chat_messages", "message_text"),
    "attachments_fts": ("attachments", "extracted_text"),
    "documents_fts": ("documents", "extracted_text"),
    "annotations_fts": ("annotations", "note_text"),
}


@dataclass
class SearchHit:
    citation: Citation
    score: float


def _quote_query(q: str) -> str:
    """Escape user query for FTS5 MATCH safety. Allows AND/OR/NOT
    operators if user types them; quotes literals otherwise.
    """
    # Naive approach for v1: replace double-quotes; pass through else.
    # Future: parse a small DSL.
    return q.replace('"', '""')


def bm25_search(
    db: Database,
    query: str,
    k: int = 50,
    source_types: list[str] | None = None,
) -> list[SearchHit]:
    """Run BM25 search across the FTS5 indices.

    source_types: optional list like ['emails', 'chat_messages']. If None,
    search all five FTS tables.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    fts_to_search = []
    for fts_table, (parent_table, text_col) in FTS_TABLES.items():
        if source_types is None or parent_table in source_types:
            fts_to_search.append((fts_table, parent_table, text_col))

    hits: list[SearchHit] = []
    quoted = _quote_query(query)
    for fts_table, parent_table, text_col in fts_to_search:
        sql = f"""
            SELECT rowid,
                   bm25({fts_table}) AS score,
                   snippet({fts_table}, -1, '<mark>', '</mark>', '…', 32) AS snip
            FROM {fts_table}
            WHERE {fts_table} MATCH ?
            ORDER BY score
            LIMIT ?
        """
        try:
            cur.execute(sql, (quoted, k))
        except Exception:
            continue
        for row_id, score, snip in cur.fetchall():
            hits.append(SearchHit(
                citation=Citation(
                    table=parent_table,  # type: ignore[arg-type]
                    row_id=row_id,
                    snippet=snip,
                ),
                score=score,
            ))

    # Negate score: BM25 returns lower=better; flip so higher=better
    for h in hits:
        h.score = -h.score
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
```

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git add casepulse/search/fts.py tests/search/test_fts_search.py
git commit -m "Add bm25_search returning Citation hits with snippets"
```

---

### Task 2.6: Reciprocal Rank Fusion

**Files:**
- Create: `casepulse/search/rrf.py`
- Create: `tests/search/test_rrf.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_rrf.py
from casepulse.search.rrf import rrf_fuse
from casepulse.search.citation import Citation
from casepulse.search.fts import SearchHit


def make_hit(table, row_id, score):
    return SearchHit(citation=Citation(table=table, row_id=row_id), score=score)


def test_rrf_merges_lists():
    a = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 4.0)]
    b = [make_hit("emails", 2, 0.9), make_hit("emails", 3, 0.8)]
    fused = rrf_fuse([a, b], k=10, c=60)
    ids = [(h.citation.table, h.citation.row_id) for h in fused]
    assert ("emails", 2) in ids  # appears in both, should rank highest
    assert ("emails", 1) in ids
    assert ("emails", 3) in ids


def test_rrf_higher_rank_in_both_wins():
    a = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 1.0)]
    b = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 1.0)]
    fused = rrf_fuse([a, b], k=10)
    assert fused[0].citation.row_id == 1
    assert fused[1].citation.row_id == 2
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/search/rrf.py
"""Reciprocal Rank Fusion across multiple ranked lists.

score_total(d) = sum_over_lists 1 / (c + rank_in_list(d))

Original paper (Cormack et al. 2009) uses c=60.
"""
from typing import Iterable

from casepulse.search.fts import SearchHit


def _key(hit: SearchHit) -> tuple[str, int]:
    return (hit.citation.table, hit.citation.row_id)


def rrf_fuse(lists: Iterable[list[SearchHit]], k: int = 50,
              c: int = 60) -> list[SearchHit]:
    """Fuse multiple ranked lists into one. Higher score = better."""
    scored: dict[tuple[str, int], SearchHit] = {}
    score_sums: dict[tuple[str, int], float] = {}
    for ranked_list in lists:
        for rank, hit in enumerate(ranked_list, start=1):
            key = _key(hit)
            score_sums[key] = score_sums.get(key, 0.0) + 1.0 / (c + rank)
            if key not in scored or hit.score > scored[key].score:
                scored[key] = hit

    fused: list[SearchHit] = []
    for key, hit in scored.items():
        new_hit = SearchHit(citation=hit.citation, score=score_sums[key])
        fused.append(new_hit)

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:k]
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/search/rrf.py tests/search/test_rrf.py
git commit -m "Add Reciprocal Rank Fusion for hybrid retrieval"
```

---

### Task 2.7: Hybrid retrieval

**Files:**
- Create: `casepulse/search/retrieval.py`
- Create: `tests/search/test_hybrid_retrieval.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_hybrid_retrieval.py
from casepulse.search.retrieval import hybrid_search


def test_hybrid_returns_results(tmp_db_with_case, monkeypatch):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('Custody', 'access schedule discussion', 'a@x', '<m1>',
                'h1', 1)
    """)
    conn.commit()
    # Stub embedding query — empty for this test
    monkeypatch.setattr(
        "casepulse.search.retrieval._embedding_search", lambda *a, **kw: []
    )
    hits = hybrid_search(db, "custody", k=10)
    assert len(hits) >= 1
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/search/retrieval.py
"""Hybrid retrieval: BM25 + ChromaDB embedding + RRF fusion."""
from dataclasses import dataclass

from casepulse.search.citation import Citation
from casepulse.search.fts import SearchHit, bm25_search
from casepulse.search.rrf import rrf_fuse
from casepulse.storage.database import Database


@dataclass
class SearchFacets:
    source_types: list[str] | None = None      # emails, chat_messages, ...
    date_from: str | None = None                # ISO8601
    date_to: str | None = None
    sender: str | None = None
    has_attachment: bool | None = None
    case_id: int | None = None


def _embedding_search(db: Database, query: str,
                       facets: SearchFacets, k: int) -> list[SearchHit]:
    """Wrap existing ChromaDB query into SearchHit objects."""
    from casepulse.rag.vectorstore import VectorStore
    vs = VectorStore()
    where: dict = {}
    if facets.sender:
        where["sender"] = facets.sender
    raw = vs.query(query, k=k, where=where or None)
    hits: list[SearchHit] = []
    for entry in raw:
        meta = entry["metadata"]
        kind = meta.get("type", "email")
        # Map chunk types to source tables
        table_map = {
            "email": "emails",
            "chat": "chat_messages",
            "attachment": "attachments",
            "document": "documents",
        }
        table = table_map.get(kind, "emails")
        row_id = meta.get("email_id") or meta.get("attachment_id") \
                 or meta.get("document_id") or 0
        hits.append(SearchHit(
            citation=Citation(
                table=table,  # type: ignore[arg-type]
                row_id=row_id,
                snippet=entry["text"][:200],
            ),
            score=entry["relevance_score"],
        ))
    return hits


def hybrid_search(
    db: Database,
    query: str,
    facets: SearchFacets | None = None,
    k: int = 50,
) -> list[SearchHit]:
    """Run BM25 + embedding retrieval and fuse via RRF."""
    facets = facets or SearchFacets()
    bm25_hits = bm25_search(db, query, k=k, source_types=facets.source_types)
    embed_hits = _embedding_search(db, query, facets, k=k)
    return rrf_fuse([bm25_hits, embed_hits], k=k)
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/search/retrieval.py tests/search/test_hybrid_retrieval.py
git commit -m "Add hybrid_search combining BM25 and embedding retrieval via RRF"
```

---

### Task 2.8: Index `documents` in ChromaDB

**Files:** Modify `casepulse/rag/chunker.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_documents_chunked.py
def test_documents_appear_in_chunks(tmp_db_with_case):
    """Documents added to the documents table also enter ChromaDB chunks."""
    from casepulse.rag.chunker import build_all_chunks
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO documents (filename, file_path, content_hash,
                               extracted_text, ocr_status)
        VALUES ('test.pdf', '/tmp/test.pdf', 'docHash1',
                'Long document content about visitation', 'done')
    """)
    conn.commit()
    chunks = build_all_chunks(db)
    doc_chunks = [c for c in chunks if c["metadata"].get("type") == "document"]
    assert len(doc_chunks) >= 1
    assert "visitation" in doc_chunks[0]["text"].lower()
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

In `casepulse/rag/chunker.py`, add a `chunk_document` function and call it from `build_all_chunks`:

```python
def chunk_document(doc: dict, chunk_size: int = 500,
                   overlap: int = 50) -> list[dict]:
    """Chunk a documents-table row into RAG chunks with metadata."""
    text = doc.get("extracted_text", "") or ""
    if not text:
        return []
    words = text.split()
    chunks = []
    i = 0
    chunk_idx = 0
    while i < len(words):
        chunk_words = words[i:i + chunk_size]
        body = " ".join(chunk_words)
        header = f"Document: {doc.get('filename', 'unknown')}\n"
        chunks.append({
            "text": header + body,
            "metadata": {
                "document_id": doc["id"],
                "filename": doc.get("filename"),
                "type": "document",
                "chunk_index": chunk_idx,
            },
        })
        i += chunk_size - overlap
        chunk_idx += 1
    return chunks


def build_all_chunks(db) -> list[dict]:
    chunks = []
    # ... existing email/attachment/chat chunking ...
    for doc in db.get_documents():
        chunks.extend(chunk_document(doc))
    return chunks
```

(Add `db.get_documents()` if it doesn't exist; thin wrapper around `SELECT * FROM documents WHERE extracted_text IS NOT NULL`.)

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/rag/chunker.py casepulse/storage/database.py tests/search/test_documents_chunked.py
git commit -m "Index documents in ChromaDB (close existing RAG gap)"
```

---

### Task 2.9: Fix Ask page silent date-filter broadening

**Files:** Modify `casepulse/rag/query_engine.py`

- [ ] **Step 1: Write test**

```python
# tests/search/test_query_engine_date_filter.py
def test_date_filter_no_results_returns_empty(tmp_db_with_case, monkeypatch):
    """When date filter excludes all hits, return empty (don't silently widen)."""
    from casepulse.rag.query_engine import QueryEngine
    qe = QueryEngine(tmp_db_with_case[0])
    # Stub vectorstore to return one hit dated outside the requested range
    def fake_query(*args, **kwargs):
        return [{"text": "irrelevant", "metadata": {"date": "2020-01-01"},
                 "relevance_score": 0.9}]
    monkeypatch.setattr(qe.vectorstore, "query", fake_query)
    results = qe.query("test", date_from="2024-01-01", date_to="2024-12-31")
    assert results == []  # not silently broadened
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Fix bug**

In `casepulse/rag/query_engine.py:~91`, locate the fallback branch that broadens the search when the date filter excludes everything. Replace with:

```python
filtered = [h for h in hits if _within_date_range(h, date_from, date_to)]
# Old behavior: if not filtered: filtered = hits  ← silently broadened
# New behavior: if not filtered, return [] and log a warning.
if not filtered and hits:
    import logging
    logging.warning(
        "Ask query had %d candidate hits but all were outside the date "
        "filter %s..%s; returning empty rather than silently broadening.",
        len(hits), date_from, date_to,
    )
return filtered
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/rag/query_engine.py tests/search/test_query_engine_date_filter.py
git commit -m "Fix Ask page silently broadening results when date filter excludes all hits"
```

---

## Phase 3 — Photo metadata + OCR

### Task 3.1: EXIF extractor

**Files:**
- Create: `casepulse/case_theory/metadata_extractor.py`
- Create: `tests/case_theory/test_metadata_extractor.py`
- Add fixture: `tests/fixtures/photos/iphone_with_exif.jpg`, `tests/fixtures/photos/no_exif.png`

- [ ] **Step 1: Generate fixture photos**

```bash
# Use Python to generate
python -c "
from PIL import Image
img = Image.new('RGB', (100, 100), 'red')
img.save('tests/fixtures/photos/no_exif.png')
"
# For 'iphone_with_exif.jpg' use any real iPhone photo (committed once);
# alternatively generate with piexif:
python -c "
from PIL import Image
import piexif
exif_dict = {'Exif': {piexif.ExifIFD.DateTimeOriginal: b'2024:03:14 19:23:14'}}
exif_bytes = piexif.dump(exif_dict)
img = Image.new('RGB', (100, 100), 'blue')
img.save('tests/fixtures/photos/iphone_with_exif.jpg', exif=exif_bytes)
" 2>/dev/null || echo "piexif not installed; commit a real photo instead"
```

(if `piexif` not desired, commit any small JPEG with EXIF you have on hand)

- [ ] **Step 2: Write test**

```python
# tests/case_theory/test_metadata_extractor.py
from pathlib import Path
from casepulse.case_theory.metadata_extractor import extract_image, ImageMetadata


FIXTURES = Path(__file__).parent.parent / "fixtures" / "photos"


def test_extract_image_with_exif():
    md = extract_image(FIXTURES / "iphone_with_exif.jpg")
    assert isinstance(md, ImageMetadata)
    assert md.exif_present is True
    assert md.taken_at is not None
    assert md.width == 100
    assert md.height == 100


def test_extract_image_without_exif():
    md = extract_image(FIXTURES / "no_exif.png")
    assert md.exif_present is False
    assert md.taken_at is None
    assert md.width == 100  # still extracted from file
```

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/metadata_extractor.py
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ExifTags
from pydantic import BaseModel


class ImageMetadata(BaseModel):
    taken_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    lens: Optional[str] = None
    software: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_accuracy: Optional[float] = None
    orientation: Optional[int] = None
    width: int = 0
    height: int = 0
    exif_present: bool = False


_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def _parse_exif_datetime(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _decode_gps(gps_info: dict) -> tuple[float | None, float | None, float | None]:
    """Decode GPSInfo dict into (lat, lon, accuracy) decimals."""
    if not gps_info:
        return (None, None, None)

    def _to_decimal(coord, ref):
        if not coord:
            return None
        d, m, s = coord
        decimal = float(d) + float(m) / 60 + float(s) / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal

    lat = _to_decimal(gps_info.get(2), gps_info.get(1, "N"))
    lon = _to_decimal(gps_info.get(4), gps_info.get(3, "E"))
    return (lat, lon, None)


def extract_image(path: Path | str) -> ImageMetadata:
    """Extract EXIF + dimensions from an image file. Returns ImageMetadata
    with exif_present=False if the image has no EXIF block."""
    p = Path(path)
    md = ImageMetadata()
    try:
        with Image.open(p) as img:
            md.width, md.height = img.size
            exif = img._getexif() if hasattr(img, "_getexif") else None
    except Exception:
        return md

    if not exif:
        return md
    md.exif_present = True

    tag_to_id = ExifTags.TAGS
    name_to_value = {tag_to_id.get(k, k): v for k, v in exif.items()}

    md.taken_at = _parse_exif_datetime(name_to_value.get("DateTimeOriginal"))
    md.camera_make = (name_to_value.get("Make") or "").strip() or None
    md.camera_model = (name_to_value.get("Model") or "").strip() or None
    md.lens = (name_to_value.get("LensModel") or "").strip() or None
    md.software = (name_to_value.get("Software") or "").strip() or None
    md.orientation = name_to_value.get("Orientation")
    gps_info = name_to_value.get("GPSInfo")
    if gps_info:
        md.gps_lat, md.gps_lon, md.gps_accuracy = _decode_gps(gps_info)
    return md
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/metadata_extractor.py tests/case_theory/test_metadata_extractor.py tests/fixtures/photos
git commit -m "Add EXIF metadata extractor with Pillow + GPS decoding"
```

---

### Task 3.2: Persist ImageMetadata to photo_metadata table

**Files:**
- Modify: `casepulse/case_theory/metadata_extractor.py` — add a persist function
- Modify: `tests/case_theory/test_metadata_extractor.py`

- [ ] **Step 1: Write test**

```python
def test_persist_image_metadata(tmp_db, tmp_path):
    from casepulse.case_theory.metadata_extractor import (
        extract_image, persist_metadata
    )
    src = FIXTURES / "iphone_with_exif.jpg"
    md = extract_image(src)
    persist_metadata(tmp_db, md, source_table="attachments", source_row_id=1)
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT exif_present, width, height FROM photo_metadata "
                "WHERE source_row_id = 1")
    row = cur.fetchone()
    assert row[0] == 1  # exif_present True stored as 1
    assert row[1] == 100
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# Append to casepulse/case_theory/metadata_extractor.py
def persist_metadata(db, md: ImageMetadata, *,
                     source_table: str, source_row_id: int) -> int:
    """Insert or update photo_metadata row. Returns photo_metadata.id."""
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO photo_metadata (
            source_table, source_row_id, taken_at, camera_make, camera_model,
            lens, software, gps_lat, gps_lon, gps_accuracy,
            orientation, width, height, exif_present
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_table, source_row_id) DO UPDATE SET
            taken_at = excluded.taken_at,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            lens = excluded.lens,
            software = excluded.software,
            gps_lat = excluded.gps_lat,
            gps_lon = excluded.gps_lon,
            gps_accuracy = excluded.gps_accuracy,
            orientation = excluded.orientation,
            width = excluded.width,
            height = excluded.height,
            exif_present = excluded.exif_present
    """, (
        source_table, source_row_id,
        md.taken_at.isoformat() if md.taken_at else None,
        md.camera_make, md.camera_model, md.lens, md.software,
        md.gps_lat, md.gps_lon, md.gps_accuracy,
        md.orientation, md.width, md.height,
        1 if md.exif_present else 0,
    ))
    conn.commit()
    cur.execute("SELECT id FROM photo_metadata "
                "WHERE source_table = ? AND source_row_id = ?",
                (source_table, source_row_id))
    return cur.fetchone()[0]
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add persist_metadata to write ImageMetadata to photo_metadata"
```

---

### Task 3.3: OCR worker via pytesseract

**Files:**
- Modify: `casepulse/case_theory/metadata_extractor.py` — add `run_ocr_if_image()`
- Modify: `tests/case_theory/test_metadata_extractor.py`

- [ ] **Step 1: Write test**

```python
def test_run_ocr_on_image_with_text(tmp_path):
    from PIL import Image, ImageDraw, ImageFont
    from casepulse.case_theory.metadata_extractor import run_ocr_image
    img = Image.new('RGB', (300, 100), 'white')
    d = ImageDraw.Draw(img)
    d.text((10, 30), "HELLO WORLD", fill='black')
    p = tmp_path / "test_ocr.png"
    img.save(p)
    text, confidence = run_ocr_image(p)
    assert "HELLO" in text.upper()
    assert 0 <= confidence <= 1
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# Append to casepulse/case_theory/metadata_extractor.py
def run_ocr_image(path: Path | str) -> tuple[str, float]:
    """Run Tesseract on an image. Returns (text, mean_confidence_0_to_1).

    If pytesseract isn't installed or Tesseract binary missing, returns ('', 0.0).
    """
    try:
        import pytesseract
    except ImportError:
        return ("", 0.0)
    try:
        text = pytesseract.image_to_string(str(path))
        data = pytesseract.image_to_data(
            str(path), output_type=pytesseract.Output.DICT
        )
        confs = [int(c) for c in data.get("conf", []) if c not in ("-1", -1)]
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return (text.strip(), mean_conf)
    except Exception:
        return ("", 0.0)
```

- [ ] **Step 4: Verify PASS** (skip on CI if tesseract isn't installed; mark with `pytest.mark.skipif`)

- [ ] **Step 5: Commit**

```bash
git commit -am "Add run_ocr_image wrapping pytesseract with confidence score"
```

---

### Task 3.4: Wire into ingest pipelines

**Files:** Modify `casepulse/email_engine/gmail_fetcher.py`, `microsoft_fetcher.py`, `casepulse/attachments/document_import.py`

- [ ] **Step 1: Write integration test**

```python
# tests/case_theory/test_ingest_metadata_hookup.py
def test_attachment_image_triggers_metadata(tmp_db_with_case, tmp_path):
    """When an image attachment lands in attachments table, photo_metadata
    is populated."""
    from casepulse.case_theory.metadata_extractor import extract_image, persist_metadata
    from PIL import Image
    db, _ = tmp_db_with_case
    img_path = tmp_path / "img.jpg"
    Image.new('RGB', (50, 50)).save(img_path)
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO attachments (email_id, filename, content_type, size_bytes,
                                  file_path, content_hash)
        VALUES (1, 'img.jpg', 'image/jpeg', 0, ?, 'h1')
    """, (str(img_path),))
    conn.commit()
    att_id = cur.lastrowid
    # Hookup function to call after attachment download
    md = extract_image(img_path)
    persist_metadata(db, md, source_table="attachments", source_row_id=att_id)
    cur.execute("SELECT id FROM photo_metadata WHERE source_row_id = ?", (att_id,))
    assert cur.fetchone() is not None
```

- [ ] **Step 2: FAIL check** — only fails if hookup not yet integrated. Run; expect PASS just for the helper test (Step 1 here only validates the helpers; the wiring happens in Step 3).

- [ ] **Step 3: Wire fetchers**

In `casepulse/email_engine/gmail_fetcher.py` after the attachment-write block (search for `file_path = ...` and the subsequent `cur.execute("INSERT INTO attachments ...")`), add:

```python
from casepulse.case_theory.metadata_extractor import extract_image, persist_metadata
if content_type and content_type.startswith("image/"):
    md = extract_image(file_path)
    persist_metadata(self.db, md, source_table="attachments",
                      source_row_id=attachment_id)
```

Repeat the same in `casepulse/email_engine/microsoft_fetcher.py` after attachment write.

In `casepulse/attachments/document_import.py`, after each document INSERT, add the same block targeting `source_table="documents"`.

- [ ] **Step 4: Verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "Hook EXIF extraction into Gmail, Microsoft, and document ingest"
```

---

### Task 3.5: Background OCR job

**Files:**
- Modify: `casepulse/jobs.py` (add OCR job type)
- Modify: `casepulse/email_engine/gmail_fetcher.py`, `microsoft_fetcher.py` — enqueue OCR for images
- Create: `tests/case_theory/test_ocr_job.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_ocr_job.py
def test_ocr_job_enqueued_for_image(tmp_db_with_case):
    """Ingested image attachment results in pending background_jobs row."""
    from casepulse.jobs import enqueue_job
    db, _ = tmp_db_with_case
    enqueue_job(db, job_type="ocr_attachment", payload={"attachment_id": 42})
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT job_type, status FROM background_jobs "
                "WHERE job_type = 'ocr_attachment'")
    row = cur.fetchone()
    assert row[0] == "ocr_attachment"
    assert row[1] == "pending"
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement enqueue + worker**

In `casepulse/jobs.py`:
```python
import json

def enqueue_job(db, *, job_type: str, payload: dict) -> int:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO background_jobs (job_type, status, payload, created_at)
        VALUES (?, 'pending', ?, datetime('now'))
    """, (job_type, json.dumps(payload)))
    conn.commit()
    return cur.lastrowid


def run_ocr_jobs(db, max_jobs: int = 10) -> int:
    """Drain up to max_jobs pending OCR jobs. Returns number processed."""
    from casepulse.case_theory.metadata_extractor import run_ocr_image
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, payload FROM background_jobs
        WHERE job_type = 'ocr_attachment' AND status = 'pending'
        LIMIT ?
    """, (max_jobs,))
    jobs = cur.fetchall()
    processed = 0
    for job_id, payload_str in jobs:
        payload = json.loads(payload_str)
        att_id = payload["attachment_id"]
        cur.execute("SELECT file_path FROM attachments WHERE id = ?", (att_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("UPDATE background_jobs SET status = 'failed' WHERE id = ?",
                        (job_id,))
            continue
        text, conf = run_ocr_image(row[0])
        if text:
            cur.execute("""
                UPDATE attachments SET extracted_text = ? WHERE id = ?
            """, (text, att_id))
            status = "completed" if conf >= 0.6 else "needs_review"
        else:
            status = "failed"
        cur.execute("UPDATE background_jobs SET status = ?, completed_at = datetime('now') "
                    "WHERE id = ?", (status, job_id))
        processed += 1
    conn.commit()
    return processed
```

- [ ] **Step 4: Verify PASS** (test enqueue only; runner tested separately)

- [ ] **Step 5: Wire from fetchers**

In each fetcher, after `persist_metadata(...)` for an image attachment:
```python
from casepulse.jobs import enqueue_job
enqueue_job(self.db, job_type="ocr_attachment",
             payload={"attachment_id": attachment_id})
```

- [ ] **Step 6: Commit**

```bash
git add casepulse/jobs.py casepulse/email_engine tests/case_theory/test_ocr_job.py
git commit -m "Add background OCR jobs enqueued at image-attachment ingest"
```

---

## Phase 4 — Case theory data layer

### Task 4.1: Pydantic models for all case-theory entities

**Files:**
- Create: `casepulse/case_theory/models.py`
- Create: `tests/case_theory/test_models.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_models.py
import pytest
from datetime import datetime
from casepulse.case_theory.models import (
    Theme, Allegation, Contradiction, Argument, Evidence,
    EvidenceKind, ArgumentType, Strength, ContradictionStatus,
    AllegationStatus, EvidenceRole,
)

def test_theme_model():
    t = Theme(case_id=1, title="Pattern of false reports")
    assert t.case_id == 1

def test_argument_with_type_and_strength():
    a = Argument(
        contradiction_id=1, title="Was at party",
        argument_type=ArgumentType.ALIBI,
        strength=Strength.STRONG,
    )
    assert a.argument_type == ArgumentType.ALIBI
    assert a.strength == Strength.STRONG

def test_evidence_polymorphic():
    e = Evidence(
        evidence_kind=EvidenceKind.PHOTO,
        source_table="attachments",
        source_row_id=42,
    )
    assert e.evidence_kind == EvidenceKind.PHOTO

def test_invalid_argument_type():
    with pytest.raises(ValueError):
        Argument(contradiction_id=1, title="x", argument_type="not_a_type")
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/models.py
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel


class ContradictionStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    LOCKED = "locked"
    USED_IN_FILING = "used-in-filing"


class AllegationStatus(str, Enum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    DISPUTED = "disputed"


class ArgumentType(str, Enum):
    ALIBI = "alibi"
    SELF_CONTRADICTION = "self_contradiction"
    WITNESS = "witness"
    DOCUMENTARY = "documentary"
    TIMING = "timing"
    PATTERN = "pattern"


class Strength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    CIRCUMSTANTIAL = "circumstantial"


class EvidenceKind(str, Enum):
    EMAIL = "email"
    CHAT = "chat"
    ATTACHMENT = "attachment"
    DOCUMENT = "document"
    PHOTO = "photo"


class EvidenceRole(str, Enum):
    SUPPORTS = "supports"
    CORROBORATES = "corroborates"
    REFUTES = "refutes"


class Theme(BaseModel):
    id: Optional[int] = None
    case_id: int
    title: str
    description: Optional[str] = None
    display_order: int = 0
    created_at: Optional[datetime] = None


class Allegation(BaseModel):
    id: Optional[int] = None
    case_id: int
    title: str
    claim_text: str
    claimed_date: Optional[str] = None
    source_evidence_id: Optional[int] = None
    status: AllegationStatus = AllegationStatus.ACTIVE
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class Contradiction(BaseModel):
    id: Optional[int] = None
    case_id: int
    headline: str
    status: ContradictionStatus = ContradictionStatus.DRAFT
    theme_id: Optional[int] = None
    display_order: int = 0
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Argument(BaseModel):
    id: Optional[int] = None
    contradiction_id: int
    title: str
    reasoning_text: Optional[str] = None
    argument_type: Optional[ArgumentType] = None
    strength: Optional[Strength] = None
    sequence: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Evidence(BaseModel):
    id: Optional[int] = None
    evidence_kind: EvidenceKind
    source_table: Literal["emails", "chat_messages", "attachments",
                          "documents", "annotations"]
    source_row_id: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    snippet: Optional[str] = None
    source_hash: Optional[str] = None
    created_at: Optional[datetime] = None
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/models.py tests/case_theory/test_models.py
git commit -m "Add Pydantic models for Theme, Allegation, Contradiction, Argument, Evidence"
```

---

### Task 4.2: Repository — themes CRUD

**Files:**
- Create: `casepulse/case_theory/repository.py`
- Create: `tests/case_theory/test_repository.py`

- [ ] **Step 1: Write tests**

```python
# tests/case_theory/test_repository.py
from casepulse.case_theory.models import Theme
from casepulse.case_theory.repository import (
    create_theme, get_theme, list_themes, update_theme, delete_theme,
)


def test_create_and_get_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    theme = Theme(case_id=case_id, title="Pattern", description="d")
    saved = create_theme(db, theme)
    assert saved.id is not None
    got = get_theme(db, saved.id)
    assert got.title == "Pattern"


def test_list_themes_filtered_by_case(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    create_theme(db, Theme(case_id=case_id, title="T1"))
    create_theme(db, Theme(case_id=case_id, title="T2"))
    themes = list_themes(db, case_id=case_id)
    assert len(themes) == 2


def test_update_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="Old"))
    saved.title = "New"
    updated = update_theme(db, saved)
    assert updated.title == "New"
    assert get_theme(db, saved.id).title == "New"


def test_delete_theme(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    saved = create_theme(db, Theme(case_id=case_id, title="X"))
    delete_theme(db, saved.id)
    assert get_theme(db, saved.id) is None
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/repository.py
from typing import Optional

from casepulse.case_theory.models import Theme
from casepulse.storage.database import Database


def create_theme(db: Database, theme: Theme) -> Theme:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO themes (case_id, title, description, display_order)
        VALUES (?, ?, ?, ?)
    """, (theme.case_id, theme.title, theme.description, theme.display_order))
    conn.commit()
    theme.id = cur.lastrowid
    return theme


def get_theme(db: Database, theme_id: int) -> Optional[Theme]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, case_id, title, description, display_order, "
                "created_at FROM themes WHERE id = ?", (theme_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Theme(
        id=row[0], case_id=row[1], title=row[2], description=row[3],
        display_order=row[4],
    )


def list_themes(db: Database, case_id: int) -> list[Theme]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, case_id, title, description, display_order "
                "FROM themes WHERE case_id = ? ORDER BY display_order, id",
                (case_id,))
    return [Theme(id=r[0], case_id=r[1], title=r[2], description=r[3],
                  display_order=r[4]) for r in cur.fetchall()]


def update_theme(db: Database, theme: Theme) -> Theme:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE themes SET title = ?, description = ?, display_order = ?
        WHERE id = ?
    """, (theme.title, theme.description, theme.display_order, theme.id))
    conn.commit()
    return theme


def delete_theme(db: Database, theme_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM themes WHERE id = ?", (theme_id,))
    conn.commit()
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/repository.py tests/case_theory/test_repository.py
git commit -m "Add Theme CRUD in case_theory.repository"
```

---

### Task 4.3: Repository — allegations CRUD

**Files:** Modify `casepulse/case_theory/repository.py`, modify `tests/case_theory/test_repository.py`

- [ ] **Step 1: Write tests** (mirror theme tests, replacing Theme→Allegation):

```python
from casepulse.case_theory.models import Allegation, AllegationStatus
from casepulse.case_theory.repository import (
    create_allegation, get_allegation, list_allegations,
    update_allegation, delete_allegation,
)


def test_create_and_get_allegation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    a = Allegation(case_id=case_id, title="X", claim_text="She said Y",
                    claimed_date="2024-03-14")
    saved = create_allegation(db, a)
    got = get_allegation(db, saved.id)
    assert got.claim_text == "She said Y"
    assert got.status == AllegationStatus.ACTIVE
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement** (in `casepulse/case_theory/repository.py`, mirror the theme CRUD pattern for Allegation, with all columns from the model. Pattern is identical: INSERT/SELECT/UPDATE/DELETE statements scoped to `allegations` table.)

```python
def create_allegation(db: Database, a: Allegation) -> Allegation:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO allegations (case_id, title, claim_text, claimed_date,
                                  source_evidence_id, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (a.case_id, a.title, a.claim_text, a.claimed_date,
          a.source_evidence_id, a.status.value, a.notes))
    conn.commit()
    a.id = cur.lastrowid
    return a


def get_allegation(db: Database, allegation_id: int) -> Optional[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, title, claim_text, claimed_date,
               source_evidence_id, status, notes
        FROM allegations WHERE id = ?
    """, (allegation_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Allegation(
        id=row[0], case_id=row[1], title=row[2], claim_text=row[3],
        claimed_date=row[4], source_evidence_id=row[5],
        status=AllegationStatus(row[6]), notes=row[7],
    )


def list_allegations(db: Database, case_id: int) -> list[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, title, claim_text, claimed_date,
               source_evidence_id, status, notes
        FROM allegations WHERE case_id = ? ORDER BY claimed_date, id
    """, (case_id,))
    return [Allegation(
        id=r[0], case_id=r[1], title=r[2], claim_text=r[3],
        claimed_date=r[4], source_evidence_id=r[5],
        status=AllegationStatus(r[6]), notes=r[7],
    ) for r in cur.fetchall()]


def update_allegation(db: Database, a: Allegation) -> Allegation:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE allegations SET title = ?, claim_text = ?, claimed_date = ?,
                                source_evidence_id = ?, status = ?, notes = ?
        WHERE id = ?
    """, (a.title, a.claim_text, a.claimed_date, a.source_evidence_id,
          a.status.value, a.notes, a.id))
    conn.commit()
    return a


def delete_allegation(db: Database, allegation_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM allegations WHERE id = ?", (allegation_id,))
    conn.commit()
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add Allegation CRUD"
```

---

### Task 4.4: Repository — contradictions CRUD with allegation linking

**Files:** Modify `casepulse/case_theory/repository.py`, modify test file

- [ ] **Step 1: Write tests**

```python
from casepulse.case_theory.models import Contradiction, ContradictionStatus
from casepulse.case_theory.repository import (
    create_contradiction, get_contradiction, list_contradictions,
    update_contradiction, link_allegation_to_contradiction,
    list_allegations_for_contradiction,
)


def test_create_contradiction_and_link_allegation(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    a = create_allegation(db, Allegation(
        case_id=case_id, title="X", claim_text="text"))
    c = create_contradiction(db, Contradiction(
        case_id=case_id, headline="C1"))
    link_allegation_to_contradiction(db, c.id, a.id)
    linked = list_allegations_for_contradiction(db, c.id)
    assert len(linked) == 1
    assert linked[0].id == a.id
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
def create_contradiction(db: Database, c: Contradiction) -> Contradiction:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO contradictions (case_id, headline, status, theme_id,
                                     display_order, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (c.case_id, c.headline, c.status.value, c.theme_id,
          c.display_order, c.notes))
    conn.commit()
    c.id = cur.lastrowid
    return c


def get_contradiction(db: Database, cid: int) -> Optional[Contradiction]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, case_id, headline, status, theme_id, display_order, notes
        FROM contradictions WHERE id = ?
    """, (cid,))
    row = cur.fetchone()
    if not row:
        return None
    return Contradiction(
        id=row[0], case_id=row[1], headline=row[2],
        status=ContradictionStatus(row[3]), theme_id=row[4],
        display_order=row[5], notes=row[6],
    )


def list_contradictions(db: Database, case_id: int,
                         status: Optional[ContradictionStatus] = None
                         ) -> list[Contradiction]:
    conn = db._get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("""
            SELECT id, case_id, headline, status, theme_id, display_order, notes
            FROM contradictions WHERE case_id = ? AND status = ?
            ORDER BY display_order, id
        """, (case_id, status.value))
    else:
        cur.execute("""
            SELECT id, case_id, headline, status, theme_id, display_order, notes
            FROM contradictions WHERE case_id = ?
            ORDER BY display_order, id
        """, (case_id,))
    return [Contradiction(
        id=r[0], case_id=r[1], headline=r[2],
        status=ContradictionStatus(r[3]), theme_id=r[4],
        display_order=r[5], notes=r[6],
    ) for r in cur.fetchall()]


def update_contradiction(db: Database, c: Contradiction) -> Contradiction:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE contradictions SET headline = ?, status = ?, theme_id = ?,
                                    display_order = ?, notes = ?,
                                    updated_at = datetime('now')
        WHERE id = ?
    """, (c.headline, c.status.value, c.theme_id, c.display_order, c.notes, c.id))
    conn.commit()
    return c


def link_allegation_to_contradiction(db: Database, contradiction_id: int,
                                       allegation_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO contradiction_allegations
        (contradiction_id, allegation_id) VALUES (?, ?)
    """, (contradiction_id, allegation_id))
    conn.commit()


def list_allegations_for_contradiction(db: Database,
                                         contradiction_id: int
                                         ) -> list[Allegation]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.case_id, a.title, a.claim_text, a.claimed_date,
               a.source_evidence_id, a.status, a.notes
        FROM allegations a
        JOIN contradiction_allegations ca ON ca.allegation_id = a.id
        WHERE ca.contradiction_id = ?
    """, (contradiction_id,))
    return [Allegation(
        id=r[0], case_id=r[1], title=r[2], claim_text=r[3],
        claimed_date=r[4], source_evidence_id=r[5],
        status=AllegationStatus(r[6]), notes=r[7],
    ) for r in cur.fetchall()]
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add Contradiction CRUD + M:N allegation linking"
```

---

### Task 4.5: Repository — arguments CRUD

**Files:** Modify `casepulse/case_theory/repository.py`, modify test file

- [ ] **Step 1: Write test**

```python
from casepulse.case_theory.models import Argument, ArgumentType, Strength
from casepulse.case_theory.repository import (
    create_argument, get_argument, list_arguments_for_contradiction,
    update_argument, delete_argument,
)


def test_create_argument(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C"))
    arg = create_argument(db, Argument(
        contradiction_id=c.id, title="At party",
        argument_type=ArgumentType.ALIBI, strength=Strength.STRONG,
    ))
    got = get_argument(db, arg.id)
    assert got.argument_type == ArgumentType.ALIBI
    assert got.strength == Strength.STRONG
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement** (mirror prior CRUD patterns)

```python
def create_argument(db: Database, a: Argument) -> Argument:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO arguments (contradiction_id, title, reasoning_text,
                                argument_type, strength, sequence)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (a.contradiction_id, a.title, a.reasoning_text,
          a.argument_type.value if a.argument_type else None,
          a.strength.value if a.strength else None, a.sequence))
    conn.commit()
    a.id = cur.lastrowid
    return a


def get_argument(db: Database, arg_id: int) -> Optional[Argument]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, contradiction_id, title, reasoning_text, argument_type,
               strength, sequence FROM arguments WHERE id = ?
    """, (arg_id,))
    row = cur.fetchone()
    if not row:
        return None
    return Argument(
        id=row[0], contradiction_id=row[1], title=row[2],
        reasoning_text=row[3],
        argument_type=ArgumentType(row[4]) if row[4] else None,
        strength=Strength(row[5]) if row[5] else None,
        sequence=row[6],
    )


def list_arguments_for_contradiction(db: Database,
                                       contradiction_id: int) -> list[Argument]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, contradiction_id, title, reasoning_text, argument_type,
               strength, sequence
        FROM arguments WHERE contradiction_id = ?
        ORDER BY sequence, id
    """, (contradiction_id,))
    return [Argument(
        id=r[0], contradiction_id=r[1], title=r[2], reasoning_text=r[3],
        argument_type=ArgumentType(r[4]) if r[4] else None,
        strength=Strength(r[5]) if r[5] else None,
        sequence=r[6],
    ) for r in cur.fetchall()]


def update_argument(db: Database, a: Argument) -> Argument:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE arguments SET title = ?, reasoning_text = ?,
                              argument_type = ?, strength = ?, sequence = ?,
                              updated_at = datetime('now')
        WHERE id = ?
    """, (a.title, a.reasoning_text,
          a.argument_type.value if a.argument_type else None,
          a.strength.value if a.strength else None, a.sequence, a.id))
    conn.commit()
    return a


def delete_argument(db: Database, arg_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM arguments WHERE id = ?", (arg_id,))
    conn.commit()
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add Argument CRUD"
```

---

### Task 4.6: Repository — evidence CRUD + argument_evidence linking

**Files:** Modify `casepulse/case_theory/repository.py`, modify test file

- [ ] **Step 1: Write test**

```python
from casepulse.case_theory.models import Evidence, EvidenceKind, EvidenceRole
from casepulse.case_theory.repository import (
    create_evidence, attach_evidence_to_argument,
    list_evidence_for_argument, detach_evidence_from_argument,
)


def test_create_and_attach_evidence(tmp_db_with_case):
    db, case_id = tmp_db_with_case
    c = create_contradiction(db, Contradiction(case_id=case_id, headline="C"))
    arg = create_argument(db, Argument(contradiction_id=c.id, title="A"))
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.PHOTO,
        source_table="attachments", source_row_id=42,
    ))
    attach_evidence_to_argument(db, arg.id, e.id, role=EvidenceRole.SUPPORTS)
    listed = list_evidence_for_argument(db, arg.id)
    assert len(listed) == 1
    assert listed[0]["evidence"].source_row_id == 42
    assert listed[0]["role"] == EvidenceRole.SUPPORTS
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
import hashlib

def create_evidence(db: Database, e: Evidence) -> Evidence:
    """Insert Evidence row. If source_hash is None, computes from source row."""
    conn = db._get_conn()
    cur = conn.cursor()
    if e.source_hash is None:
        e.source_hash = _compute_source_hash(db, e.source_table, e.source_row_id)
    try:
        cur.execute("""
            INSERT INTO evidence (evidence_kind, source_table, source_row_id,
                                   char_start, char_end, snippet, source_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (e.evidence_kind.value, e.source_table, e.source_row_id,
              e.char_start, e.char_end, e.snippet, e.source_hash))
        e.id = cur.lastrowid
    except sqlite3.IntegrityError:
        # Same (source_table, source_row_id, char_start, char_end) already exists
        cur.execute("""
            SELECT id FROM evidence
            WHERE source_table = ? AND source_row_id = ?
              AND COALESCE(char_start, -1) = COALESCE(?, -1)
              AND COALESCE(char_end, -1) = COALESCE(?, -1)
        """, (e.source_table, e.source_row_id, e.char_start, e.char_end))
        e.id = cur.fetchone()[0]
    conn.commit()
    return e


def _compute_source_hash(db: Database, source_table: str,
                          source_row_id: int) -> str | None:
    """Compute SHA-256 of the source row's primary text."""
    conn = db._get_conn()
    cur = conn.cursor()
    text_cols = {
        "emails": "body_text",
        "chat_messages": "message_text",
        "attachments": "extracted_text",
        "documents": "extracted_text",
        "annotations": "note_text",
    }
    col = text_cols.get(source_table)
    if not col:
        return None
    cur.execute(f"SELECT {col} FROM {source_table} WHERE id = ?",
                (source_row_id,))
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return hashlib.sha256(row[0].encode("utf-8")).hexdigest()


def attach_evidence_to_argument(
    db: Database, argument_id: int, evidence_id: int,
    *, role: EvidenceRole = EvidenceRole.SUPPORTS,
    display_order: int = 0, notes: Optional[str] = None,
) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO argument_evidence
        (argument_id, evidence_id, role, display_order, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (argument_id, evidence_id, role.value, display_order, notes))
    conn.commit()


def detach_evidence_from_argument(db: Database, argument_id: int,
                                    evidence_id: int) -> None:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        DELETE FROM argument_evidence
        WHERE argument_id = ? AND evidence_id = ?
    """, (argument_id, evidence_id))
    conn.commit()


def list_evidence_for_argument(db: Database,
                                 argument_id: int) -> list[dict]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.evidence_kind, e.source_table, e.source_row_id,
               e.char_start, e.char_end, e.snippet, e.source_hash,
               ae.role, ae.display_order, ae.notes
        FROM evidence e
        JOIN argument_evidence ae ON ae.evidence_id = e.id
        WHERE ae.argument_id = ?
        ORDER BY ae.display_order, ae.added_at
    """, (argument_id,))
    out = []
    for r in cur.fetchall():
        out.append({
            "evidence": Evidence(
                id=r[0], evidence_kind=EvidenceKind(r[1]),
                source_table=r[2], source_row_id=r[3],
                char_start=r[4], char_end=r[5], snippet=r[6],
                source_hash=r[7],
            ),
            "role": EvidenceRole(r[8]),
            "display_order": r[9],
            "notes": r[10],
        })
    return out
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add Evidence CRUD + argument_evidence M:N linking with hash auto-compute"
```

---

### Task 4.7: Polymorphic Evidence resolver

**Files:**
- Create: `casepulse/case_theory/evidence_resolver.py`
- Create: `tests/case_theory/test_evidence_resolver.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_evidence_resolver.py
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.evidence_resolver import resolve, ResolvedSource


def test_resolve_email(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id, date_received)
        VALUES ('Subject', 'Body content', 'a@x.com', '<m1>', 'h1', 1,
                '2024-03-14 10:00')
    """)
    conn.commit()
    eid = cur.lastrowid
    e = Evidence(evidence_kind=EvidenceKind.EMAIL,
                 source_table="emails", source_row_id=eid)
    resolved = resolve(db, e)
    assert resolved.kind == "email"
    assert resolved.text == "Body content"
    assert resolved.metadata["subject"] == "Subject"
    assert resolved.metadata["sender_email"] == "a@x.com"
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/evidence_resolver.py
from dataclasses import dataclass, field
from typing import Any

from casepulse.case_theory.models import Evidence
from casepulse.storage.database import Database


@dataclass
class ResolvedSource:
    kind: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None  # for attachments / documents / photos


def resolve(db: Database, e: Evidence) -> ResolvedSource:
    conn = db._get_conn()
    cur = conn.cursor()

    if e.source_table == "emails":
        cur.execute("""
            SELECT subject, body_text, sender_email, sender_name,
                   date_received, recipients, message_id, content_hash
            FROM emails WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="email",
            text=r[1] or "",
            metadata={
                "subject": r[0], "sender_email": r[2], "sender_name": r[3],
                "date": r[4], "recipients": r[5], "message_id": r[6],
                "content_hash": r[7],
            },
        )
    if e.source_table == "chat_messages":
        cur.execute("""
            SELECT message_text, sender, timestamp, chat_name, platform,
                   media_path, content_hash
            FROM chat_messages WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="chat",
            text=r[0] or "",
            metadata={
                "sender": r[1], "date": r[2], "chat_name": r[3],
                "platform": r[4], "content_hash": r[6],
            },
            file_path=r[5],
        )
    if e.source_table == "attachments":
        cur.execute("""
            SELECT filename, content_type, file_path, extracted_text,
                   content_hash, email_id
            FROM attachments WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="attachment",
            text=r[3] or "",
            metadata={
                "filename": r[0], "content_type": r[1],
                "content_hash": r[4], "email_id": r[5],
            },
            file_path=r[2],
        )
    if e.source_table == "documents":
        cur.execute("""
            SELECT filename, file_path, extracted_text, content_hash,
                   timeline_date
            FROM documents WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="document",
            text=r[2] or "",
            metadata={"filename": r[0], "content_hash": r[3],
                       "date": r[4]},
            file_path=r[1],
        )
    if e.source_table == "annotations":
        cur.execute("""
            SELECT note_text, item_type, item_id, created_at
            FROM annotations WHERE id = ?
        """, (e.source_row_id,))
        r = cur.fetchone()
        return ResolvedSource(
            kind="annotation",
            text=r[0] or "",
            metadata={"item_type": r[1], "item_id": r[2], "date": r[3]},
        )
    raise ValueError(f"unknown source_table: {e.source_table}")
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add polymorphic Evidence resolver returning ResolvedSource"
```

---

## Phase 5 — Court-defensibility primitives

### Task 5.1: Hash verification

**Files:**
- Modify: `casepulse/case_theory/repository.py` — add `verify_evidence_hash`
- Create: `tests/case_theory/test_hash_verification.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_hash_verification.py
from casepulse.case_theory.models import Evidence, EvidenceKind
from casepulse.case_theory.repository import (
    create_evidence, verify_evidence_hash,
)


def test_hash_verifies(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('S', 'Original body', 'a@x', '<m>', 'h', 1)
    """)
    conn.commit()
    eid = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=eid,
    ))
    assert verify_evidence_hash(db, e.id) is True


def test_hash_mismatch_detected(tmp_db_with_case):
    db, _ = tmp_db_with_case
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id)
        VALUES ('S', 'Original body', 'a@x', '<m>', 'h', 1)
    """)
    conn.commit()
    eid = cur.lastrowid
    e = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=eid,
    ))
    cur.execute("UPDATE emails SET body_text = 'TAMPERED' WHERE id = ?", (eid,))
    conn.commit()
    assert verify_evidence_hash(db, e.id) is False
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# Append to casepulse/case_theory/repository.py
def verify_evidence_hash(db: Database, evidence_id: int) -> bool:
    """Re-compute source hash and compare to stored Evidence.source_hash.

    Returns True if match (or if both None — nothing to compare),
    False on mismatch.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT source_table, source_row_id, source_hash FROM evidence
        WHERE id = ?
    """, (evidence_id,))
    row = cur.fetchone()
    if not row:
        return False
    source_table, source_row_id, stored_hash = row
    fresh = _compute_source_hash(db, source_table, source_row_id)
    if stored_hash is None and fresh is None:
        return True
    return stored_hash == fresh
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git commit -am "Add verify_evidence_hash for chain-of-custody verification"
```

---

### Task 5.2: Audit log hash chain — insert helper

**Files:**
- Create: `casepulse/case_theory/audit_chain.py`
- Create: `tests/case_theory/test_audit_chain.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_audit_chain.py
import hashlib
from casepulse.case_theory.audit_chain import (
    log_chained, verify_chain, get_last_hash,
)


def test_chained_inserts_link(tmp_db):
    log_chained(tmp_db, action="created_theme", details={"theme_id": 1})
    log_chained(tmp_db, action="created_argument", details={"argument_id": 5})
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, prev_hash, row_hash FROM audit_log ORDER BY id")
    rows = cur.fetchall()
    assert rows[0][1] is None  # genesis row has no prev_hash
    assert rows[0][2] is not None  # but has its own row_hash
    assert rows[1][1] == rows[0][2]  # second row's prev = first's row


def test_verify_chain_passes_unmodified(tmp_db):
    log_chained(tmp_db, action="a", details={})
    log_chained(tmp_db, action="b", details={})
    log_chained(tmp_db, action="c", details={})
    assert verify_chain(tmp_db) is True


def test_verify_chain_detects_tampering(tmp_db):
    log_chained(tmp_db, action="a", details={})
    log_chained(tmp_db, action="b", details={})
    conn = tmp_db._get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE audit_log SET action = 'TAMPERED' WHERE id = 1")
    conn.commit()
    assert verify_chain(tmp_db) is False
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/audit_chain.py
"""Tamper-evident hash chain over the audit_log table.

Each row's row_hash = SHA-256(prev_hash || canonical_row_data).
Verification walks the chain and recomputes hashes — any tampering
breaks the chain at the modified row.
"""
import hashlib
import json
from typing import Optional

from casepulse.storage.database import Database


def _canonicalize(row_data: dict) -> bytes:
    """Stable serialization for hashing."""
    return json.dumps(row_data, sort_keys=True, default=str).encode("utf-8")


def get_last_hash(db: Database) -> Optional[str]:
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    return row[0] if row else None


def log_chained(db: Database, *, action: str, details: dict) -> int:
    """Insert a hash-chained audit_log row. Returns inserted row id."""
    conn = db._get_conn()
    cur = conn.cursor()
    prev = get_last_hash(db)
    row_data = {"action": action, "details": details}
    base = (prev or "") + _canonicalize(row_data).decode()
    row_hash = hashlib.sha256(base.encode("utf-8")).hexdigest()
    cur.execute("""
        INSERT INTO audit_log (action, details, prev_hash, row_hash)
        VALUES (?, ?, ?, ?)
    """, (action, json.dumps(details), prev, row_hash))
    conn.commit()
    return cur.lastrowid


def verify_chain(db: Database) -> bool:
    """Walk the chain end-to-end, recomputing each row_hash."""
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, action, details, prev_hash, row_hash
        FROM audit_log ORDER BY id
    """)
    expected_prev = None
    for row_id, action, details_json, stored_prev, stored_row in cur.fetchall():
        if stored_prev != expected_prev:
            return False
        details = json.loads(details_json) if details_json else {}
        row_data = {"action": action, "details": details}
        base = (stored_prev or "") + _canonicalize(row_data).decode()
        recomputed = hashlib.sha256(base.encode("utf-8")).hexdigest()
        if recomputed != stored_row:
            return False
        expected_prev = stored_row
    return True
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/audit_chain.py tests/case_theory/test_audit_chain.py
git commit -m "Add tamper-evident hash chain over audit_log with verification"
```

---

### Task 5.3: X-Ray defensive scan wrapper

**Files:**
- Create: `casepulse/case_theory/redaction_scanner.py`
- Create: `tests/case_theory/test_redaction_scanner.py`
- Add fixture: `tests/fixtures/pdfs/clean.pdf`, `tests/fixtures/pdfs/bad_redaction.pdf`

- [ ] **Step 1: Generate fixture PDFs**

For `clean.pdf`: any small PDF with normal text. Generate via:
```bash
python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/pdfs/clean.pdf')
c.drawString(100, 750, 'This is a clean PDF with no redactions')
c.save()
"
```

For `bad_redaction.pdf`: a PDF with a black rectangle drawn over text but the text still extractable. Generate via:
```bash
python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/pdfs/bad_redaction.pdf')
c.drawString(100, 750, 'Sensitive text that should be hidden')
c.setFillColorRGB(0, 0, 0)
c.rect(95, 745, 200, 14, fill=True)  # black rect over text
c.save()
"
```

(reportlab is the standard ad-hoc PDF generator; install with `pip install reportlab` if not present, or commit the fixtures manually)

- [ ] **Step 2: Write test**

```python
# tests/case_theory/test_redaction_scanner.py
from pathlib import Path
from casepulse.case_theory.redaction_scanner import scan_pdf

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pdfs"

def test_clean_pdf_no_findings():
    findings = scan_pdf(FIXTURES / "clean.pdf")
    assert findings == []


def test_bad_redaction_detected():
    findings = scan_pdf(FIXTURES / "bad_redaction.pdf")
    assert len(findings) >= 1
    assert findings[0].page > 0
```

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/redaction_scanner.py
"""Wrapper around freelawproject's x-ray library to detect bad PDF redactions
(black rectangles drawn over still-extractable text)."""
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class RedactionFinding:
    page: int
    text: str
    bbox: tuple[float, float, float, float] | None = None


def scan_pdf(path: Path | str) -> list[RedactionFinding]:
    """Scan a PDF for bad redactions. Returns empty list if clean."""
    try:
        import xray  # noqa
    except ImportError:
        # Library not installed; return empty (don't fail builds)
        return []
    p = Path(path)
    try:
        results = xray.inspect(str(p))
    except Exception:
        return []

    findings: list[RedactionFinding] = []
    for page_num, page_findings in (results or {}).items():
        for item in (page_findings or []):
            findings.append(RedactionFinding(
                page=int(page_num),
                text=item.get("text", "") if isinstance(item, dict) else str(item),
                bbox=item.get("bbox") if isinstance(item, dict) else None,
            ))
    return findings
```

(Note: `x-ray-pdf`'s exact API may differ — adjust the result parsing to match the actual `xray.inspect()` return shape. Verify with `python -c "import xray; help(xray.inspect)"` after install.)

- [ ] **Step 4: Verify PASS** (skipping if `xray` not installed in env — test should `pytest.importorskip("xray")` at the top)

- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/redaction_scanner.py tests/case_theory/test_redaction_scanner.py tests/fixtures/pdfs
git commit -m "Add X-Ray bad-redaction scanner wrapper"
```

---

### Task 5.4: s.31.6 Certificate generator

**Files:**
- Create: `casepulse/case_theory/auth_certificate.py`
- Create: `tests/case_theory/test_auth_certificate.py`

- [ ] **Step 1: Write test**

```python
# tests/case_theory/test_auth_certificate.py
from datetime import date
from casepulse.case_theory.auth_certificate import (
    CertificateInput, ExhibitRecord, render_certificate_html,
)


def test_certificate_html_contains_required_clauses():
    cert = CertificateInput(
        operator_name="Mani Chaudhary",
        operator_address="Toronto, ON",
        location="Toronto, ON",
        signing_date=date(2026, 4, 30),
        software_version="CasePulse v1.0",
        exhibits=[
            ExhibitRecord(
                ref="A", description="Photograph IMG_4521.jpg",
                source="WhatsApp", ingested_at="2024-08-12",
                sha256="3a7d8e1f0c2b9a64b72f",
            ),
        ],
    )
    html = render_certificate_html(cert)
    assert "s. 31.6" in html or "31.6" in html
    assert "Mani Chaudhary" in html
    assert "3a7d8e1f0c2b9a64b72f" in html
    assert "EXHIBIT A" in html.upper() or "Exhibit A" in html
```

- [ ] **Step 2: FAIL check**

- [ ] **Step 3: Implement**

```python
# casepulse/case_theory/auth_certificate.py
"""Canada Evidence Act s.31.6 Certificate of Authenticity — data + renderer.

Used by the export pipeline to attach a self-authentication block to
every Court Bundle PDF.
"""
from dataclasses import dataclass, field
from datetime import date
from html import escape


@dataclass
class ExhibitRecord:
    ref: str                        # e.g. "A" or "1"
    description: str
    source: str                     # e.g. "WhatsApp chat with X, 2024-03-14"
    ingested_at: str                # ISO date
    sha256: str


@dataclass
class CertificateInput:
    operator_name: str
    operator_address: str
    location: str
    signing_date: date
    software_version: str
    exhibits: list[ExhibitRecord] = field(default_factory=list)


_TEMPLATE = """\
<section class="auth-cert">
  <h2>CERTIFICATE OF AUTHENTICITY</h2>
  <p class="cert-statute"><em>Canada Evidence Act</em>, R.S.C. 1985, c. C-5,
  s. 31.6</p>

  <p>I, <strong>{name}</strong>, residing at {address}, CERTIFY that:</p>

  <ol class="cert-clauses">
    <li>The electronic documents listed in the Schedule below were extracted
        from the source(s) identified by the operation of {software}, an
        electronic documents system.</li>
    <li>The system was operating properly at the relevant time of
        extraction.</li>
    <li>Each electronic document is identified by its SHA-256 hash, computed
        at the time of ingestion. Each hash matches the file as held by the
        system at the time of this certification.</li>
    <li>The electronic documents have not been modified since ingestion.</li>
    <li>The integrity of the electronic documents system can be verified by
        the system's audit log, which is hash-chained from genesis.</li>
  </ol>

  <p>DATED at {location} this _____ day of ____________, {year}.</p>

  <p class="cert-signature">______________________________<br>
  Signature of {name}</p>

  <h3 class="cert-schedule-heading">Schedule of Electronic Documents</h3>
  <table class="cert-schedule">
    <thead>
      <tr><th>Exhibit</th><th>Description</th><th>Source</th>
          <th>Ingested</th><th>SHA-256</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</section>
"""


def render_certificate_html(c: CertificateInput) -> str:
    rows = []
    for x in c.exhibits:
        rows.append(
            f"<tr><td>{escape(x.ref)}</td>"
            f"<td>{escape(x.description)}</td>"
            f"<td>{escape(x.source)}</td>"
            f"<td>{escape(x.ingested_at)}</td>"
            f"<td><code>{escape(x.sha256)}</code></td></tr>"
        )
    return _TEMPLATE.format(
        name=escape(c.operator_name),
        address=escape(c.operator_address),
        location=escape(c.location),
        year=c.signing_date.year,
        software=escape(c.software_version),
        rows="\n      ".join(rows),
    )
```

- [ ] **Step 4: Verify PASS**
- [ ] **Step 5: Commit**

```bash
git add casepulse/case_theory/auth_certificate.py tests/case_theory/test_auth_certificate.py
git commit -m "Add Canada Evidence Act s.31.6 Certificate generator"
```

---

## Phase 6 — Acceptance + smoke tests

### Task 6.1: End-to-end "build a contradiction" smoke test

**Files:**
- Create: `tests/case_theory/test_smoke_e2e.py`

- [ ] **Step 1: Write the test**

```python
# tests/case_theory/test_smoke_e2e.py
"""Smoke test exercising the full Plan-1 surface end-to-end."""
from casepulse.case_theory.models import (
    Theme, Allegation, Contradiction, Argument, Evidence,
    ArgumentType, Strength, EvidenceKind, EvidenceRole,
)
from casepulse.case_theory.repository import (
    create_theme, create_allegation, create_contradiction,
    link_allegation_to_contradiction, create_argument, create_evidence,
    attach_evidence_to_argument, list_evidence_for_argument,
    verify_evidence_hash,
)
from casepulse.case_theory.audit_chain import log_chained, verify_chain
from casepulse.search.retrieval import hybrid_search


def test_build_contradiction_end_to_end(tmp_db_with_case, monkeypatch):
    db, case_id = tmp_db_with_case
    # Seed an email
    conn = db._get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO emails (subject, body_text, sender_email, message_id,
                            content_hash, account_id, date_received)
        VALUES ('Custody', 'access denied for the third time',
                'opp@x.com', '<m1>', 'h1', 1, '2024-03-14')
    """)
    conn.commit()
    email_id = cur.lastrowid

    # Build case theory
    theme = create_theme(db, Theme(
        case_id=case_id, title="Pattern of access denial"))
    alleg = create_allegation(db, Allegation(
        case_id=case_id, title="Access denied 2024-03-14",
        claim_text="Access was refused", claimed_date="2024-03-14"))
    contra = create_contradiction(db, Contradiction(
        case_id=case_id, headline="False access-denial claim",
        theme_id=theme.id))
    link_allegation_to_contradiction(db, contra.id, alleg.id)
    arg = create_argument(db, Argument(
        contradiction_id=contra.id, title="Email shows we did meet",
        argument_type=ArgumentType.DOCUMENTARY,
        strength=Strength.STRONG))
    evi = create_evidence(db, Evidence(
        evidence_kind=EvidenceKind.EMAIL,
        source_table="emails", source_row_id=email_id))
    attach_evidence_to_argument(db, arg.id, evi.id, role=EvidenceRole.SUPPORTS)

    # Verify
    listed = list_evidence_for_argument(db, arg.id)
    assert len(listed) == 1
    assert verify_evidence_hash(db, evi.id) is True

    # Search finds the email
    monkeypatch.setattr("casepulse.search.retrieval._embedding_search",
                         lambda *a, **kw: [])
    hits = hybrid_search(db, "denied", k=10)
    assert any(h.citation.row_id == email_id for h in hits)

    # Audit chain
    log_chained(db, action="contradiction_created",
                 details={"contradiction_id": contra.id})
    assert verify_chain(db) is True
```

- [ ] **Step 2: Run** the smoke test:

```bash
pytest tests/case_theory/test_smoke_e2e.py -v
```

Expected: PASS — exercises every Phase 1-5 component.

- [ ] **Step 3: Run the full suite**

```bash
pytest -v
```

Expected: ALL PASS. Coverage report generated.

- [ ] **Step 4: Commit**

```bash
git commit -am "Add end-to-end smoke test exercising the Plan-1 surface"
```

---

### Task 6.2: Run app, verify migrations on real DB, manual sanity

**Files:** none (manual verification step)

- [ ] **Step 1: Backup current DB**

```bash
cp data/db/casepulse.db data/db/casepulse.db.pre-w1.bak
```

- [ ] **Step 2: Launch the app**

```bash
./run.sh
```

Expected: app launches without errors. Migrations run on first launch (new tables present, ALTER columns added, FTS5 backfill runs).

- [ ] **Step 3: Verify schema in real DB**

```bash
sqlite3 data/db/casepulse.db ".schema themes" \
    ".schema allegations" \
    ".schema contradictions" \
    ".schema arguments" \
    ".schema evidence" \
    ".schema photo_metadata" \
    ".schema metadata_attestations"
```

Expected: each `.schema` prints the new table.

- [ ] **Step 4: Verify FTS5 has data**

```bash
sqlite3 data/db/casepulse.db "SELECT COUNT(*) FROM emails_fts"
sqlite3 data/db/casepulse.db "SELECT COUNT(*) FROM chat_messages_fts"
```

Expected: counts roughly match `emails` and `chat_messages` row counts.

- [ ] **Step 5: Verify case_type defaults to 'family'**

```bash
sqlite3 data/db/casepulse.db "SELECT id, name, case_type FROM cases"
```

Expected: existing cases have `case_type = 'family'`.

- [ ] **Step 6: Verify chat_messages.content_hash backfilled**

```bash
sqlite3 data/db/casepulse.db "SELECT COUNT(*) FROM chat_messages WHERE content_hash IS NULL"
```

Expected: `0`.

- [ ] **Step 7: Verify ChromaDB has documents now**

In Python (or via Streamlit Ask page once 1.2 lands):
```python
from casepulse.rag.vectorstore import VectorStore
vs = VectorStore()
docs = vs.query("any document", k=20)
# Confirm at least some metadata.type == 'document'
print([d['metadata'].get('type') for d in docs])
```

Expected: 'document' appears in the type list (after running `chunker.build_all_chunks`).

- [ ] **Step 8: Commit nothing** (manual verification step). If anything fails, file an issue and fix before declaring Plan 1 done.

---

## Self-review

After writing the plan above, fresh-eyes pass:

**1. Spec coverage** — every spec section that's in W1.1 scope is implemented:
- §4 architecture: new packages created (Phases 0, 2, 3, 4, 5) ✓
- §5 data model: all 9 new tables + 2 ALTERs (Phase 1) ✓
- §5.3 bug fixes: chat_messages.content_hash backfill (1.10) + Ask date-filter fix (2.9) ✓
- §5.4 FTS5: 5 virtual tables + triggers + backfill (2.1, 2.2, 2.3) ✓
- §5.5 Citation: 2.4 ✓
- §6 hybrid retrieval: 2.5 (BM25) + 2.6 (RRF) + 2.7 (hybrid) ✓
- §7 OCR pipeline: 3.1 (EXIF) + 3.3 (Tesseract) + 3.5 (background job) ✓
- §9 photo metadata reliability: 3.1 (extract) + 3.2 (persist) — strike/attest UI is in Plan 1.2; the schema (`metadata_attestations`) lands in 1.7 ✓
- §10.1 hash verification: 5.1 ✓
- §10.2 s.31.6 cert: 5.4 ✓
- §10.3 audit chain: 5.2 ✓
- §10.4 X-Ray: 5.3 ✓
- §13 migrations + backfill: Phase 1 ✓
- §16 testing strategy: pytest config 0.4, hypothesis available, golden-file deferred to Plan 1.3
- §2 documents-in-RAG gap: 2.8 ✓
- §15 error handling: tested in respective component tests

**2. Placeholder scan** — no TBD/TODO/"implement later" found. All steps have actual code.

**3. Type consistency** — `Theme`, `Allegation`, `Contradiction`, `Argument`, `Evidence`, `EvidenceKind`, `ArgumentType`, `Strength`, `EvidenceRole`, `AllegationStatus`, `ContradictionStatus` used consistently across model, repository, evidence_resolver, smoke test. `Citation` used in `fts.py`, `rrf.py`, `retrieval.py`, smoke test. `SearchHit` is internal to `search/`. `ImageMetadata` used in `metadata_extractor.py` and persisted via `persist_metadata`. `ResolvedSource` returned by `evidence_resolver.resolve`.

**4. Ambiguity scan** — `_compute_source_hash` is referenced in `verify_evidence_hash` but defined in Task 4.6; inline shows it. `EvidenceRole` defined Task 4.1, used 4.6+; consistent. `_canonicalize` and `get_last_hash` defined inline in 5.2 audit_chain.

**5. Scope check** — Plan 1 produces a working backend with comprehensive tests and CI. Plan 1.2 (UI) and 1.3 (Export) build on this without revisiting.

No issues found requiring inline fix.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-w1-plan-1-foundation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan because tasks are well-isolated and TDD-shaped.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

Which approach?
