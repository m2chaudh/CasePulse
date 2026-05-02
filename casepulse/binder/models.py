"""Pydantic models for Case Binder timeline_events.metadata_json shapes
and aggregator value types."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class BinderCategory(str, Enum):
    COURT_APPEARANCE = "court_appearance"
    DISCLOSURE = "disclosure"
    COUNSEL_CORRESPONDENCE = "counsel_correspondence"
    PERSONAL_EVENT = "personal_event"


class Forum(str, Enum):
    CRIMINAL = "criminal"
    FAMILY = "family"
    CIVIL = "civil"


class DelayAttribution(BaseModel):
    category: Literal["defence", "crown", "inherent", "exceptional"]
    days: int = Field(ge=0)
    note: str = ""


class CourtAppearanceMetadata(BaseModel):
    forum: Forum
    court_name: str = ""
    judge: str = ""
    own_counsel: str = ""
    opposing_counsel: str = ""
    purpose: Literal[
        "first_appearance", "set_date", "trial", "motion",
        "case_conference", "settlement_conference", "sentencing", "other",
    ] = "other"
    outcome: str = ""
    delay_attribution: Optional[DelayAttribution] = None


class DisclosureKind(str, Enum):
    CROWN = "crown"
    FINANCIAL = "financial"
    DISCOVERY = "discovery"
    OTHER = "other"


class DisclosureMetadata(BaseModel):
    kind: DisclosureKind
    direction: Literal["received", "requested"]
    page_count: int = 0
    items: str = ""
    completion_status: Literal["expecting_more", "complete"] = "complete"
    expected_completion_date: Optional[str] = None
    follow_up_email_id: Optional[int] = None
    outstanding_flag: bool = False


class CounselParty(str, Enum):
    CROWN = "crown"
    OPPOSING_COUNSEL = "opposing_counsel"
    OWN_COUNSEL = "own_counsel"
    OCL = "OCL"
    OTHER = "other"


class CounselCorrespondenceMetadata(BaseModel):
    party: CounselParty
    linked_email_id: Optional[int] = None
    summary: str = ""
    response_required: bool = False
    response_due_date: Optional[str] = None
    response_sent_email_id: Optional[int] = None


class PersonalEventMetadata(BaseModel):
    """No *_ids arrays — related items live in `item_links`."""
    time_end: Optional[str] = None
    location: str = ""
    evidence_relevance: Literal[
        "alibi", "corroboration", "contradiction", "context",
    ] = "context"
    is_day_anchor: bool = False  # set true for day-anchor events created by "+ Attach"


# ---------------------------------------------------------------------------
# Aggregator value types
# ---------------------------------------------------------------------------

class CrossRef(BaseModel):
    target_type: str
    target_id: int
    relationship: str
    label: str = ""


class AggregatedItem(BaseModel):
    when: datetime
    source: Literal["timeline_event", "email", "chat", "document", "photo", "attachment"]
    source_id: int
    category: str
    title: str
    summary: str = ""
    metadata: dict = Field(default_factory=dict)
    has_attachment: bool = False
    cross_refs: list[CrossRef] = Field(default_factory=list)


class ChipFilter(BaseModel):
    """Decoded filter for the aggregator. Either a built-in chip id or a
    custom-chip filter_json payload."""
    chip_id: str = "all"
    categories: list[str] = Field(default_factory=list)
    sender_addresses: list[str] = Field(default_factory=list)
    keyword: str = ""
    witness_id: Optional[int] = None
    party: Optional[CounselParty] = None
