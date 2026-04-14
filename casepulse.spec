# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for CasePulse desktop application."""

import os
import platform
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None
IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"
ICON_FILE = "icon.icns" if IS_MAC else "icon.ico"

# Collect streamlit's data files (static assets, config, etc.)
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")

# Collect other packages that need data files
altair_datas = collect_data_files("altair")
pydeck_datas = collect_data_files("pydeck", include_py_files=True)

# Additional hidden imports
hidden_imports = [
    # Streamlit internals
    *streamlit_hiddenimports,
    *collect_submodules("streamlit"),
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner",
    # PyWebView
    "webview",
    # Core app
    "casepulse",
    "casepulse.storage.database",
    "casepulse.config",
    "casepulse.setup_wizard",
    "casepulse.legal.pin_lock",
    "casepulse.legal.exhibits",
    "casepulse.auth.microsoft",
    "casepulse.auth.google_auth",
    "casepulse.email_engine.microsoft_fetcher",
    "casepulse.email_engine.gmail_fetcher",
    "casepulse.email_engine.parser",
    "casepulse.email_engine.dedup",
    "casepulse.chat_engine.importer",
    "casepulse.chat_engine.whatsapp_parser",
    "casepulse.chat_engine.appclose_parser",
    "casepulse.chat_engine.chatvault_parser",
    "casepulse.chat_engine.pdf_chat_parser",
    "casepulse.llm.api_provider",
    "casepulse.llm.ollama_provider",
    "casepulse.llm.base",
    "casepulse.analysis.contradictions",
    "casepulse.attachments.extractor",
    "casepulse.attachments.image_metadata",
    "casepulse.export.pdf_builder",
    "casepulse.export.ai_package",
    "casepulse.export.timeline_export",
    "casepulse.export.interactive_timeline",
    "casepulse.export.chat_timeline_html",
    "casepulse.export.document_import",
    "casepulse.export.manifest",
    "casepulse.rag.query_engine",
    "casepulse.rag.chunker",
    "casepulse.rag.embedder",
    "casepulse.rag.vectorstore",
    "casepulse.jobs",
    "casepulse.desktop",
    "casepulse.desktop.splash",
    "casepulse.desktop.tray",
    # Auth libraries
    "msal",
    "google.auth",
    "google.oauth2",
    "google_auth_oauthlib",
    "googleapiclient",
    # Data/ML
    "sqlite3",
    "pdfplumber",
    "docx",
    "openpyxl",
    "fpdf",
    "lxml",
    "bs4",
    "dateutil",
    "cryptography",
    # LLM providers
    "ollama",
    "anthropic",
    "openai",
    "google.generativeai",
    # RAG
    "chromadb",
    "sentence_transformers",
    # Visualization
    "plotly",
    "altair",
    "pydeck",
    # Tray (optional)
    "pystray",
    "PIL",
    # tkinter for splash
    "tkinter",
]

# Data files — app source that Streamlit needs at runtime
app_datas = [
    ("app.py", "."),
    ("pages", "pages"),
    ("casepulse", "casepulse"),
    ("components", "components"),
    ("icon.png", "."),
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=streamlit_binaries,
    datas=app_datas + streamlit_datas + altair_datas + pydeck_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "torch",  # sentence-transformers pulls this — too large for bundle
        "tensorflow",
        "keras",
        "IPython",
        "jupyter",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CasePulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    icon=ICON_FILE,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CasePulse",
)

# macOS .app bundle (skipped on Windows)
if IS_MAC:
    app = BUNDLE(
        coll,
        name="CasePulse.app",
        icon="icon.icns",
        bundle_identifier="com.casepulse.app",
        info_plist={
            "CFBundleName": "CasePulse",
            "CFBundleDisplayName": "CasePulse",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "10.15.0",
        },
    )
