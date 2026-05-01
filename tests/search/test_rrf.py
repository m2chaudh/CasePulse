"""Tests for Reciprocal Rank Fusion."""
from casepulse.search.rrf import rrf_fuse
from casepulse.search.citation import Citation
from casepulse.search.fts import SearchHit


def make_hit(table, row_id, score):
    return SearchHit(citation=Citation(table=table, row_id=row_id), score=score)


def test_rrf_merges_lists():
    a = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 4.0)]
    b = [make_hit("emails", 2, 0.9), make_hit("emails", 3, 0.8)]
    fused = rrf_fuse([a, b], k=10, c=60)
    ids = [(h.citation.table, h.citation.row_id) for h in fused]
    assert ("emails", 2) in ids  # appears in both, should rank highest
    assert ("emails", 1) in ids
    assert ("emails", 3) in ids


def test_rrf_higher_rank_in_both_wins():
    a = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 1.0)]
    b = [make_hit("emails", 1, 5.0), make_hit("emails", 2, 1.0)]
    fused = rrf_fuse([a, b], k=10)
    assert fused[0].citation.row_id == 1
    assert fused[1].citation.row_id == 2
