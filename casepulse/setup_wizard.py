"""First-run setup wizard — module selection for desktop installs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from casepulse.config import get_data_dir


MODULES = {
    "cloud_ai": {
        "name": "Cloud AI (Gemini, Claude, OpenAI)",
        "size": "5 MB",
        "default": True,
        "description": "Connect to cloud AI providers for analysis and queries.",
    },
    "ollama": {
        "name": "Local AI (Ollama)",
        "size": "50 MB + models",
        "default": False,
        "description": "Run AI models locally. Ollama must be installed separately.",
    },
    "rag": {
        "name": "RAG Pipeline (Ask page)",
        "size": "500 MB",
        "description": "Vector search over your emails and chats. Requires sentence-transformers.",
        "default": False,
    },
    "vision": {
        "name": "Vision / OCR",
        "size": "10 MB + model",
        "default": False,
        "description": "Image description and EXIF metadata extraction via Ollama llava.",
    },
    "contradictions": {
        "name": "Contradiction Engine",
        "size": "5 MB",
        "default": True,
        "description": "Multi-pass statement extraction and cross-source comparison.",
    },
    "pdf_export": {
        "name": "PDF Export",
        "size": "20 MB",
        "default": True,
        "description": "Court-ready PDFs with Bates numbering, bookmarks, and hyperlinked attachments.",
    },
    "excel_export": {
        "name": "Excel Export",
        "size": "15 MB",
        "default": True,
        "description": "Styled timeline spreadsheets with openpyxl.",
    },
    "doc_import": {
        "name": "Document Import & OCR",
        "size": "30 MB",
        "default": True,
        "description": "Import and extract text from PDF, DOCX, and other document formats.",
    },
}


def get_modules_path() -> Path:
    return get_data_dir() / "installed_modules.json"


def load_installed_modules() -> dict[str, bool]:
    """Load installed module selections. Returns empty dict if not configured yet."""
    path = get_modules_path()
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_installed_modules(modules: dict[str, bool]) -> None:
    """Save module selections."""
    path = get_modules_path()
    with open(path, "w") as f:
        json.dump(modules, f, indent=2)


def is_setup_complete() -> bool:
    """Check if first-run setup has been completed.

    Setup is considered complete if EITHER the modules.json was written
    via the Setup wizard, OR the user has already connected an account
    (existing users from before the Setup wizard existed shouldn't be
    forced through it).
    """
    if get_modules_path().exists():
        return True
    # Existing users: any connected account = setup is implicitly complete
    try:
        from casepulse.storage.database import Database
        db = Database()
        accounts = db.get_accounts()
        return bool(accounts)
    except Exception:
        return False


def is_module_enabled(module_key: str) -> bool:
    """Check if a specific module is enabled."""
    modules = load_installed_modules()
    if not modules:
        # Not configured yet — use defaults
        return MODULES.get(module_key, {}).get("default", False)
    return modules.get(module_key, False)


def get_default_selections() -> dict[str, bool]:
    """Get default module selections."""
    return {key: mod["default"] for key, mod in MODULES.items()}
