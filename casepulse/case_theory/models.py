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


class WitnessType(str, Enum):
    CHARACTER = "character"
    FACT = "fact"
    BOTH = "both"


class WitnessStatus(str, Enum):
    INITIAL = "initial"
    CONTACTED = "contacted"
    WILLING = "willing"
    HOSTILE = "hostile"
    SUBPOENAED = "subpoenaed"
    UNAVAILABLE = "unavailable"


class WitnessStatementStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    LOCKED = "locked"


class Witness(BaseModel):
    id: Optional[int] = None
    case_id: int
    name: str
    relationship: Optional[str] = None
    witness_type: Optional[WitnessType] = None
    contact_info: Optional[str] = None
    status: WitnessStatus = WitnessStatus.INITIAL
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WitnessStatement(BaseModel):
    id: Optional[int] = None
    witness_id: int
    statement_text: str
    statement_date: Optional[str] = None
    contradiction_id: Optional[int] = None
    argument_id: Optional[int] = None
    status: WitnessStatementStatus = WitnessStatementStatus.DRAFT
    created_at: Optional[datetime] = None
