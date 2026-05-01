"""BM25 search over FTS5 contentless indices.

Returns SearchHit objects carrying a Citation + BM25 score + snippet.
"""
from dataclasses import dataclass
from typing import Iterable

from casepulse.search.citation import Citation
from casepulse.storage.database import Database


# Map FTS table -> (parent table, snippet_cols list)
# The first col in snippet_cols is primary; all are concatenated for snippet display.
FTS_TABLES = {
    "emails_fts": ("emails", ["subject", "body_text"]),
    "chat_messages_fts": ("chat_messages", ["message_text"]),
    "attachments_fts": ("attachments", ["filename", "extracted_text"]),
    "documents_fts": ("documents", ["filename", "extracted_text"]),
    "annotations_fts": ("annotations", ["note_text"]),
}


@dataclass
class SearchHit:
    citation: Citation
    score: float


def _quote_query(q: str) -> str:
    """Escape user query for FTS5 MATCH safety. Allows AND/OR/NOT
    operators if user types them; quotes literals otherwise.
    """
    # Naive approach for v1: replace double-quotes; pass through else.
    # Future: parse a small DSL.
    return q.replace('"', '""')


def bm25_search(
    db: Database,
    query: str,
    k: int = 50,
    source_types: list[str] | None = None,
) -> list[SearchHit]:
    """Run BM25 search across the FTS5 indices.

    source_types: optional list like ['emails', 'chat_messages']. If None,
    search all five FTS tables.
    """
    conn = db._get_conn()
    cur = conn.cursor()
    fts_to_search = []
    for fts_table, (parent_table, snippet_cols) in FTS_TABLES.items():
        if source_types is None or parent_table in source_types:
            fts_to_search.append((fts_table, (parent_table, snippet_cols)))

    hits: list[SearchHit] = []
    quoted = _quote_query(query)
    for fts_table, (parent_table, snippet_cols) in fts_to_search:
        # Contentless FTS5 tables don't support snippet(); fetch text from source.
        sql = f"""
            SELECT rowid,
                   bm25({fts_table}) AS score
            FROM {fts_table}
            WHERE {fts_table} MATCH ?
            ORDER BY score
            LIMIT ?
        """
        try:
            cur.execute(sql, (quoted, k))
        except Exception:
            continue
        for row_id, score in cur.fetchall():
            # Fetch snippet from source table (contentless FTS has no stored text)
            try:
                cur2 = conn.cursor()
                col_list = ", ".join(snippet_cols)
                cur2.execute(
                    f"SELECT {col_list} FROM {parent_table} WHERE id = ?",
                    (row_id,)
                )
                row = cur2.fetchone()
                if row:
                    parts = [str(v) for v in row if v]
                    snip = " | ".join(parts)[:200] if parts else None
                else:
                    snip = None
            except Exception:
                snip = None
            hits.append(SearchHit(
                citation=Citation(
                    table=parent_table,  # type: ignore[arg-type]
                    row_id=row_id,
                    snippet=snip,
                ),
                score=score,
            ))

    # Negate score: BM25 returns lower=better; flip so higher=better
    for h in hits:
        h.score = -h.score
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:k]
