"""ChromaDB vector store for email retrieval."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from casepulse.config import get_data_dir


COLLECTION_NAME = "casepulse_emails"


class VectorStore:
    """ChromaDB-backed vector store for email chunks."""

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or str(get_data_dir() / "chroma")
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]],
                   progress_cb=None) -> int:
        """Add chunks with pre-computed embeddings to the vector store.

        Args:
            chunks: List of {text, metadata} dicts
            embeddings: Corresponding embedding vectors

        Returns:
            Number of chunks added
        """
        collection = self._get_collection()

        # ChromaDB has a batch limit, process in batches
        batch_size = 500
        total_added = 0

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]

            ids = [f"chunk_{i + j}" for j in range(len(batch_chunks))]
            documents = [c["text"] for c in batch_chunks]
            metadatas = []
            for c in batch_chunks:
                meta = c.get("metadata", {})
                # ChromaDB metadata values must be str, int, float, or bool
                clean_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    else:
                        clean_meta[k] = str(v)
                metadatas.append(clean_meta)

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=batch_embeddings,
                metadatas=metadatas,
            )
            total_added += len(batch_chunks)

            if progress_cb:
                progress_cb(f"Indexed {total_added}/{len(chunks)} chunks")

        return total_added

    def query(self, query_embedding: list[float], top_k: int = 10,
              where: Optional[dict] = None) -> list[dict]:
        """Query the vector store for similar chunks.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            where: Optional metadata filter (ChromaDB where clause)

        Returns:
            List of {text, metadata, distance} dicts, ordered by relevance
        """
        collection = self._get_collection()

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        hits = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                hits.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                    "relevance_score": 1 - dist,  # Cosine distance to similarity
                })

        return hits

    def get_count(self) -> int:
        """Get total number of chunks in the store."""
        collection = self._get_collection()
        return collection.count()

    def clear(self):
        """Delete all data from the vector store."""
        if self._client:
            try:
                self._client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            self._collection = None

    def rebuild(self, chunks: list[dict], embeddings: list[list[float]],
                progress_cb=None) -> int:
        """Clear and rebuild the entire vector store."""
        self.clear()
        self._collection = None  # Force recreation
        return self.add_chunks(chunks, embeddings, progress_cb)
