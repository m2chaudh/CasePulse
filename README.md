# CasePulse

Legal email aggregation, timeline, and AI analysis tool. Built for managing evidence across family law and criminal defence proceedings.

## What It Does

CasePulse connects to your email accounts (Outlook, Hotmail, Gmail), downloads relevant emails based on selected contacts, imports WhatsApp and AppClose chats, and organizes everything into a chronological timeline. It extracts text from PDF/Word attachments, detects contradictions across sources, and exports court-ready documents.

## Key Features

### Email Management
- **Multi-account support** — Outlook, Hotmail, Gmail (multiple accounts each)
- **Smart contact discovery** — scan mailboxes, filter by frequency, two-way detection, domain grouping
- **Selective fetching** — only download emails from contacts you select
- **Cross-account deduplication** — same email in multiple mailboxes stored once
- **Forwarded email parsing** — extracts original sender from Outlook-style forwarded chains
- **Background fetching** — fetch runs in background, progress visible from any page

### Chat Import
- **WhatsApp** — .txt exports, .zip with media, ChatVault HTML exports
- **AppClose** — co-parenting app PDF exports (409+ pages parsed)
- **PDF chat exports** — generic chat PDFs from any platform
- **Bulk directory import** — point to a folder, auto-detects format

### Evidence Organization
- **Multi-case support** — separate Family Law and Criminal Defence cases
- **Evidence tagging** — 25+ legal categories (custody, access denial, financial, false allegations, etc.)
- **Multi-category contacts** — each contact can have multiple tags
- **Exhibit numbering** — Alphabetical (Exhibit A), Bates (SMITH_00001), Numerical, System-generated
- **Annotations** — add notes to any email or chat message
- **Collections** — group evidence into named bundles (Financial Disclosure, Access Denial Incidents)
- **Saved selection views** — save/load/merge contact selections

### Timeline
- **Unified chronological view** — emails + chats merged by date
- **Thread grouping** — RE: chains linked with thread indicators
- **Inline detail panel** — click any email to see full body, headers, attachments
- **Attachment previews** — images inline, PDF text shown, download links
- **Inline actions** — tag, annotate, flag, ask AI from the timeline
- **Month bookmarks** — visual separators for navigation
- **Filters** — by sender, mailbox, direction, date range, keywords, source type

### AI Analysis
- **RAG pipeline** — local embeddings (sentence-transformers) + ChromaDB vector store
- **Ask page** — chat interface with citation-backed answers
- **Auto-tag contacts** — AI suggests categories with confidence scores
- **AI Assistant** — natural language commands to tag/select contacts ("tag all @lawfirm.com as My Lawyer")
- **Contradiction Engine** — multi-pass analysis:
  - Pass 1: Extract statements from emails, chats, attachments, documents
  - Pass 2: Find within-person contradictions
  - Pass 3: Compare email statements vs chat statements
  - Pass 4: Compare document claims (affidavits) vs actual evidence
- **Per-email AI** — ask questions about a specific email from the timeline

### Export
- **AI Analysis Package** — MEGA_FILE.md for Claude's 1M context window (body-trimmed to fit)
- **Timeline PDF — Full Detail** — every email with body, attachments, bookmarks (100+ pages)
- **Timeline PDF — Court Ready** — trimmed bodies for manageable file size (~500-800 pages)
- **Timeline PDF — Summary/Index** — compact one-row-per-email table (30-40 pages)
- **Timeline Excel** — with annotations, exhibit labels, filterable columns
- **Chat Timeline HTML** — WhatsApp + AppClose with inline images, printable
- **Exhibit Bundle PDF** — cover page, TOC, Bates-numbered exhibits
- **For My Lawyer** — PDF + Excel in one click
- **Full Data JSON/Markdown** — complete data export
- **PDF bookmarks** — navigable sidebar (month → date → email)
- **Hyperlinked attachments** — click attachment names in PDF to open files
- **Export manifest** — SHA-256 checksums for document integrity
- **Export log** — tracks what was exported and when

### Security
- **PIN lock** — app-wide PIN on every page
- **Local processing** — Ollama runs on your machine, data never leaves
- **Audit log** — all actions tracked
- **Case-segregated exports** — family and criminal evidence separated

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit (10 pages) |
| Database | SQLite with WAL mode |
| Email APIs | Microsoft Graph API, Gmail API |
| Auth | MSAL (Microsoft OAuth), Google OAuth |
| PDF generation | fpdf2 |
| Excel | openpyxl |
| Text extraction | pdfplumber, python-docx |
| Embeddings | sentence-transformers (local) |
| Vector store | ChromaDB (local) |
| LLM | Ollama (default), Gemini, Claude, OpenAI, custom |
| Vision | llava:7b via Ollama |

## Setup

### Requirements
- macOS (tested on M5 Pro, 24GB RAM)
- Python 3.11+
- Ollama (for local AI)

### Install
```bash
cd CasePulse
./run.sh
```

This creates a virtual environment, installs dependencies, and launches the app at `http://localhost:8501`.

### First-Time Setup
1. **Accounts** — connect Outlook/Hotmail/Gmail (guided setup wizard)
2. **Discover Senders** — scan mailboxes, select relevant contacts
3. **Fetch Emails** — download emails from selected contacts
4. **Timeline** — browse chronologically
5. **Ask** — build RAG index, query with AI

### Ollama Models
```bash
brew install ollama
ollama pull gemma3:27b     # Main model (17GB, best quality for 24GB RAM)
ollama pull llama3.1:8b    # Lighter alternative (4.9GB)
ollama pull llava:7b       # Vision model for image OCR (4.7GB)
```

CasePulse auto-starts/stops Ollama — no persistent resource usage.

## Pages

| # | Page | Purpose |
|---|---|---|
| 1 | Accounts | Connect email accounts with OAuth |
| 2 | Discover Senders | Scan, filter, categorize, AI-tag contacts |
| 3 | Fetch Emails | Download emails with background jobs |
| 4 | Timeline | Browse, annotate, tag, ask AI |
| 5 | Ask | RAG-powered Q&A with citations |
| 6 | Import Chats | WhatsApp, AppClose, PDF chats |
| 7 | Cases | Evidence tagging, exhibits, annotations |
| 8 | Export | PDF, Excel, CSV, JSON, HTML, AI Package |
| 9 | Documents | Import PDFs, OCR images, timeline events |
| 10 | Contradictions | AI-powered statement extraction and comparison |

## Data Storage

All data is local in `data/`:
```
data/
├── db/casepulse.db      # SQLite database (emails, chats, tags, annotations)
├── tokens/              # OAuth tokens (encrypted)
├── attachments/         # Downloaded email attachments
├── chroma/              # RAG vector database
└── documents/           # Imported documents
```

Everything persists across restarts. The database is the single source of truth.

## Privacy

- All data stored locally on your machine
- Ollama runs locally — no data sent to cloud (unless you choose a cloud AI provider)
- OAuth tokens stored locally
- No telemetry, no analytics, no cloud sync
- PIN lock for physical security

## License

Private — not for distribution.
