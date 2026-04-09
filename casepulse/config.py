"""Configuration management for CasePulse."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


def get_project_root() -> Path:
    """Get the CasePulse project root directory."""
    return Path(__file__).parent.parent


def get_data_dir() -> Path:
    """Get the data directory, creating it if needed."""
    data_dir = get_project_root() / "data"
    data_dir.mkdir(exist_ok=True)
    for sub in ["tokens", "attachments", "db", "chroma"]:
        (data_dir / sub).mkdir(exist_ok=True)
    return data_dir


def get_config_path() -> Path:
    return get_project_root() / "config.json"


DEFAULT_CONFIG = {
    "date_range": {
        "start": "2024-08-01",
        "end": "2026-02-28",
    },
    "llm": {
        "provider": "ollama",
        "model": "llama3.1:8b",
        "api_key": "",
        "base_url": "http://localhost:11434",
    },
    "embedding": {
        "model": "all-MiniLM-L6-v2",
    },
    "rag": {
        "chunk_size": 500,
        "chunk_overlap": 50,
        "top_k": 10,
    },
    "microsoft_accounts": [],
    "google_accounts": [],
}


class Config:
    """Manages CasePulse configuration."""

    def __init__(self):
        self._path = get_config_path()
        self._data: dict[str, Any] = {}
        self.load()

    def load(self):
        if self._path.exists():
            with open(self._path, "r") as f:
                self._data = json.load(f)
        else:
            self._data = DEFAULT_CONFIG.copy()
            self.save()

    def save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation: 'llm.provider'"""
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, key: str, value: Any):
        """Set a config value using dot notation: 'llm.provider'"""
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self.save()

    @property
    def data(self) -> dict:
        return self._data

    # Convenience accessors
    @property
    def date_start(self) -> str:
        return self.get("date_range.start", "2024-08-01")

    @property
    def date_end(self) -> str:
        return self.get("date_range.end", "2026-02-28")

    @property
    def llm_provider(self) -> str:
        return self.get("llm.provider", "ollama")

    @property
    def llm_model(self) -> str:
        return self.get("llm.model", "llama3.1:8b")

    @property
    def llm_api_key(self) -> str:
        return self.get("llm.api_key", "")

    @property
    def llm_base_url(self) -> str:
        return self.get("llm.base_url", "http://localhost:11434")

    def add_microsoft_account(self, email: str, client_id: str):
        accounts = self.get("microsoft_accounts", [])
        if not any(a["email"] == email for a in accounts):
            accounts.append({"email": email, "client_id": client_id})
            self.set("microsoft_accounts", accounts)

    def add_google_account(self, email: str, credentials_file: str):
        accounts = self.get("google_accounts", [])
        if not any(a["email"] == email for a in accounts):
            accounts.append({"email": email, "credentials_file": credentials_file})
            self.set("google_accounts", accounts)

    def remove_account(self, provider: str, email: str):
        key = f"{provider}_accounts"
        accounts = self.get(key, [])
        accounts = [a for a in accounts if a["email"] != email]
        self.set(key, accounts)
