# CasePulse Desktop Application Build Plan

## Architecture: PyWebView + PyInstaller (same as ChatVault)

### Core (Always Included — ~200MB)
- Streamlit server (runs in background thread)
- PyWebView native window (loads localhost)
- SQLite database
- Email fetchers (Microsoft Graph, Gmail API)
- OAuth flows (MSAL, Google OAuth)
- PDF/Excel/HTML export
- Chat importers (WhatsApp, AppClose, ChatVault, PDF)
- Evidence tagging, annotations, cases
- Timeline viewer
- PIN lock

### Optional Modules (Checkbox during install)

| Module | Size | What it adds |
|---|---|---|
| **AI — Ollama Integration** | ~50MB (code only, models downloaded separately) | Local LLM, auto-start/stop, model management |
| **AI — Cloud Providers** | ~5MB | Gemini, Claude, OpenAI API integration |
| **RAG Pipeline** | ~500MB | sentence-transformers, ChromaDB, vector search, Ask page |
| **Vision/OCR** | ~10MB (code only, llava model separate) | Image description, EXIF metadata extraction |
| **Contradiction Engine** | ~5MB | Multi-pass statement extraction, cross-source comparison |
| **PDF Generation** | ~20MB | fpdf2, court-ready PDFs, Bates numbering, bookmarks |
| **Excel Export** | ~15MB | openpyxl, styled timeline spreadsheets |
| **Document Import** | ~30MB | pdfplumber, python-docx, text extraction |

### Install Size Estimates
- **Minimal (core only):** ~200MB
- **Standard (core + cloud AI + exports):** ~250MB
- **Full (everything except models):** ~800MB
- **With Ollama models:** +5-17GB per model (downloaded on first use)

## Build Steps

### 1. PyWebView Wrapper
```python
# launcher.py
import threading
import webview
from streamlit.web import cli as stcli

def run_streamlit():
    stcli.main_run(["run", "app.py", "--server.port=8501",
                    "--server.headless=true", "--browser.gatherUsageStats=false"])

if __name__ == "__main__":
    t = threading.Thread(target=run_streamlit, daemon=True)
    t.start()
    webview.create_window("CasePulse", "http://localhost:8501",
                          width=1400, height=900, min_size=(800, 600))
    webview.start()
```

### 2. Module Selection (First Run)
```python
# setup_wizard.py — runs on first launch
modules = {
    "cloud_ai": {"name": "Cloud AI (Gemini, Claude, OpenAI)", "size": "5 MB", "default": True},
    "ollama": {"name": "Local AI (Ollama)", "size": "50 MB + models", "default": False},
    "rag": {"name": "RAG Pipeline (Ask page)", "size": "500 MB", "default": False},
    "vision": {"name": "Vision/OCR", "size": "10 MB", "default": False},
    "contradictions": {"name": "Contradiction Engine", "size": "5 MB", "default": True},
    "pdf_export": {"name": "PDF Export", "size": "20 MB", "default": True},
    "excel_export": {"name": "Excel Export", "size": "15 MB", "default": True},
    "doc_import": {"name": "Document Import & OCR", "size": "30 MB", "default": True},
}
```

### 3. PyInstaller Build
```bash
# macOS
pyinstaller --name CasePulse --windowed --icon=icon.icns \
  --add-data "app.py:." --add-data "pages:pages" \
  --add-data "casepulse:casepulse" --add-data "components:components" \
  --hidden-import streamlit --hidden-import pywebview \
  launcher.py

# Windows
pyinstaller --name CasePulse --windowed --icon=icon.ico \
  --add-data "app.py;." --add-data "pages;pages" \
  --add-data "casepulse;casepulse" --add-data "components;components" \
  launcher.py
```

### 4. Platform-Specific Packaging
- **macOS:** .DMG with drag-to-Applications
- **Windows:** NSIS or Inno Setup installer (.exe)
- **Linux:** AppImage or .deb

### 5. Auto-Update
- Check GitHub releases on startup
- Download and replace binary if update available
- Data (SQLite, tokens, attachments) preserved across updates

### 6. System Tray
- Minimize to tray
- Quick access menu: Open, Export, Quit
- Background fetch notifications

## Pages to Conditionally Show

```python
# In app.py — only show pages for installed modules
installed_modules = load_installed_modules()

pages = [
    ("Accounts", True),          # Always
    ("Discover Senders", True),  # Always
    ("Fetch Emails", True),      # Always
    ("Timeline", True),          # Always
    ("Ask", "rag" in installed_modules),
    ("Import Chats", True),      # Always
    ("Cases", True),             # Always
    ("Export", True),            # Always
    ("Documents", "doc_import" in installed_modules),
    ("Contradictions", "contradictions" in installed_modules),
]
```

## Development Priorities

### Phase 1: Mac Desktop App
1. PyWebView wrapper + launcher
2. PyInstaller build for macOS
3. .DMG packaging
4. Module selection on first run
5. Test on macOS

### Phase 2: Windows
1. Test PyInstaller on Windows
2. Handle path differences (backslash, AppData)
3. NSIS installer
4. Test OAuth flows on Windows

### Phase 3: Polish
1. App icon
2. System tray
3. Auto-update
4. Splash screen during startup
5. Error handling for missing modules

## Notes
- Streamlit inside PyWebView works — tested pattern
- OAuth redirect needs special handling (open system browser, not webview)
- SQLite works cross-platform out of the box
- Ollama must be installed separately — provide download link in UI
- Data directory: ~/CasePulse/ (cross-platform)
