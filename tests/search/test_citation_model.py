"""Tests for the Citation Pydantic model."""
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
