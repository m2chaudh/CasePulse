"""Local embedding generation using sentence-transformers."""
from __future__ import annotations

from typing import Optional


class LocalEmbedder:
    """Generate embeddings locally using sentence-transformers.

    Runs entirely on your machine — no data sent anywhere.
    Uses Apple M-series GPU acceleration via MPS backend.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def embed_texts(self, texts: list[str], batch_size: int = 64,
                    progress_cb=None) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Process this many at a time
            progress_cb: Optional callback for progress updates

        Returns:
            List of embedding vectors (list of floats)
        """
        self._load_model()

        if progress_cb:
            progress_cb(f"Embedding {len(texts)} chunks with {self.model_name}...")

        embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        if progress_cb:
            progress_cb(f"Done. Generated {len(embeddings)} embeddings.")

        return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        self._load_model()
        embedding = self._model.encode([query], normalize_embeddings=True)
        return embedding[0].tolist()
