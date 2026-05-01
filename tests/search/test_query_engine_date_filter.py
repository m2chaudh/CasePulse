"""Tests for Ask page date-filter bug fix."""
import pytest
from unittest.mock import MagicMock


def test_date_filter_no_results_returns_empty(tmp_db_with_case, monkeypatch):
    """When date filter excludes all hits, return empty (don't silently widen)."""
    from casepulse.rag.query_engine import QueryEngine

    # Create mock dependencies — QueryEngine requires llm, embedder, vectorstore
    mock_llm = MagicMock()
    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.0] * 384

    mock_vs = MagicMock()
    # Stub vectorstore to return one hit dated outside the requested range
    mock_vs.query.return_value = [
        {"text": "irrelevant", "metadata": {"date": "2020-01-01"},
         "relevance_score": 0.9}
    ]

    qe = QueryEngine(mock_llm, mock_embedder, mock_vs)
    results = qe.query("test", date_start="2024-01-01", date_end="2024-12-31")
    # Should return empty answer / no sources, not silently broaden
    assert results["sources"] == []
    assert results["chunks_used"] == 0
