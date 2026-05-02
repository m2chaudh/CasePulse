"""Built-in filter chip definitions for the Case Binder."""

from __future__ import annotations
from typing import Optional
from casepulse.binder.models import ChipFilter

BUILTIN_CHIPS = [
    {"id": "all",        "label": "All",        "emoji": "",   "categories": []},
    {"id": "court",      "label": "Court",      "emoji": "📅", "categories": ["court_appearance"]},
    {"id": "disclosure", "label": "Disclosure", "emoji": "📥", "categories": ["disclosure"]},
    {"id": "counsel",    "label": "Counsel",    "emoji": "📨", "categories": ["counsel_correspondence"]},
    {"id": "personal",   "label": "Personal",   "emoji": "🗓", "categories": ["personal_event"]},
    {"id": "emails",     "label": "Emails",     "emoji": "📧", "categories": ["email"]},
    {"id": "chats",      "label": "Chats",      "emoji": "💬", "categories": ["chat"]},
    {"id": "photos",     "label": "Photos",     "emoji": "📷", "categories": ["photo"]},
    {"id": "docs",       "label": "Docs",       "emoji": "📄", "categories": ["document", "attachment"]},
]


def chip_to_filter(chip_id: str) -> Optional[ChipFilter]:
    """Translate a chip id into a ChipFilter. None for 'all' (no filter)."""
    if chip_id == "all":
        return None
    for c in BUILTIN_CHIPS:
        if c["id"] == chip_id:
            return ChipFilter(chip_id=chip_id, categories=list(c["categories"]))
    raise ValueError(f"unknown chip id: {chip_id}")
