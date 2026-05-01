"""Reciprocal Rank Fusion across multiple ranked lists.

score_total(d) = sum_over_lists 1 / (c + rank_in_list(d))

Original paper (Cormack et al. 2009) uses c=60.
"""
from typing import Iterable

from casepulse.search.fts import SearchHit


def _key(hit: SearchHit) -> tuple[str, int]:
    return (hit.citation.table, hit.citation.row_id)


def rrf_fuse(lists: Iterable[list[SearchHit]], k: int = 50,
              c: int = 60) -> list[SearchHit]:
    """Fuse multiple ranked lists into one. Higher score = better."""
    scored: dict[tuple[str, int], SearchHit] = {}
    score_sums: dict[tuple[str, int], float] = {}
    for ranked_list in lists:
        for rank, hit in enumerate(ranked_list, start=1):
            key = _key(hit)
            score_sums[key] = score_sums.get(key, 0.0) + 1.0 / (c + rank)
            if key not in scored or hit.score > scored[key].score:
                scored[key] = hit

    fused: list[SearchHit] = []
    for key, hit in scored.items():
        new_hit = SearchHit(citation=hit.citation, score=score_sums[key])
        fused.append(new_hit)

    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:k]
