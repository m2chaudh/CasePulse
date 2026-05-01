"""Hybrid retrieval: BM25 + ChromaDB embedding + RRF fusion."""
from dataclasses import dataclass

from casepulse.search.citation import Citation
from casepulse.search.fts import SearchHit, bm25_search
from casepulse.search.rrf import rrf_fuse
from casepulse.storage.database import Database


@dataclass
class SearchFacets:
    source_types: list[str] | None = None      # emails, chat_messages, ...
    date_from: str | None = None                # ISO8601
    date_to: str | None = None
    sender: str | None = None
    has_attachment: bool | None = None
    case_id: int | None = None


def _embedding_search(db: Database, query: str,
                       facets: SearchFacets, k: int) -> list[SearchHit]:
    """Wrap existing ChromaDB query into SearchHit objects.

    NOTE: VectorStore.query takes a pre-computed embedding vector, not a
    plain text query. For hybrid search we need an embedder. When no embedder
    is available (e.g. tests or before indexing), this returns an empty list.
    """
    try:
        from casepulse.rag.vectorstore import VectorStore
        from casepulse.rag.embedder import LocalEmbedder
        embedder = LocalEmbedder()
        vs = VectorStore()
        query_embedding = embedder.embed_query(query)
        where: dict = {}
        if facets.sender:
            where["sender"] = facets.sender
        raw = vs.query(query_embedding, top_k=k, where=where or None)
    except Exception:
        return []

    hits: list[SearchHit] = []
    for entry in raw:
        meta = entry["metadata"]
        kind = meta.get("type", "email")
        # Map chunk types to source tables
        table_map = {
            "email": "emails",
            "chat": "chat_messages",
            "attachment": "attachments",
            "document": "documents",
        }
        table = table_map.get(kind, "emails")
        row_id = (
            meta.get("email_id")
            or meta.get("attachment_id")
            or meta.get("document_id")
            or 0
        )
        hits.append(SearchHit(
            citation=Citation(
                table=table,  # type: ignore[arg-type]
                row_id=row_id,
                snippet=entry["text"][:200],
            ),
            score=entry["relevance_score"],
        ))
    return hits


def hybrid_search(
    db: Database,
    query: str,
    facets: SearchFacets | None = None,
    k: int = 50,
) -> list[SearchHit]:
    """Run BM25 + embedding retrieval and fuse via RRF."""
    facets = facets or SearchFacets()
    bm25_hits = bm25_search(db, query, k=k, source_types=facets.source_types)
    embed_hits = _embedding_search(db, query, facets, k=k)
    return rrf_fuse([bm25_hits, embed_hits], k=k)
