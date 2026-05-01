"""Citation model — structured pointer from a search result to its source row."""
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
