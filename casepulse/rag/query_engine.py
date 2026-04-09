"""RAG query engine — retrieves context and generates answers with citations."""
from __future__ import annotations

from typing import Optional

from casepulse.llm.base import LLMProvider
from casepulse.rag.embedder import LocalEmbedder
from casepulse.rag.vectorstore import VectorStore

SYSTEM_PROMPT = """You are CasePulse, a legal communication analysis assistant. Your role is to answer
questions about emails AND chat messages (WhatsApp, iMessage, etc.) from a legal case.
You MUST follow these rules strictly:

1. ONLY answer based on the provided context. Never invent, assume, or hallucinate information.
2. If the answer is not found in the provided context, say: "I could not find this information in the retrieved communications."
3. ALWAYS provide citations for every claim. Format citations as:
   - For emails: [Email from <sender>, <date>, Subject: "<subject>"]
   - For chats: [Chat: <platform> with <chat_name>, <date>, <sender>]
   - For attachments: [Attachment: <filename>, from <sender>, <date>]
4. When providing dates, use the exact dates from the communications.
5. If multiple communications discuss the same topic, present them chronologically.
6. Distinguish between what was said by whom — this is critical for a legal case.
7. When asked for a timeline, present events in chronological order with exact dates and sources.
8. If an email is forwarded, note both the forwarder and the original sender.
9. Clearly indicate whether a citation comes from an email or a chat message.
10. Be precise and factual. In legal contexts, accuracy is paramount.
11. When chat messages show a conversation, preserve the back-and-forth dialogue context."""


class QueryEngine:
    """RAG query engine with citation support."""

    def __init__(self, llm: LLMProvider, embedder: LocalEmbedder,
                 vectorstore: VectorStore):
        self.llm = llm
        self.embedder = embedder
        self.vectorstore = vectorstore

    def query(self, question: str, top_k: int = 10,
              sender_filter: Optional[str] = None,
              date_start: Optional[str] = None,
              date_end: Optional[str] = None) -> dict:
        """Answer a question using RAG with citations.

        Args:
            question: User's question
            top_k: Number of chunks to retrieve
            sender_filter: Optional filter by sender email
            date_start: Optional filter by start date
            date_end: Optional filter by end date

        Returns:
            {
                "answer": str,
                "sources": [{"text", "metadata", "relevance_score"}],
                "chunks_used": int,
            }
        """
        # Generate query embedding
        query_embedding = self.embedder.embed_query(question)

        # Build metadata filter
        where = None
        if sender_filter:
            where = {"sender": sender_filter}

        # Retrieve relevant chunks
        hits = self.vectorstore.query(
            query_embedding=query_embedding,
            top_k=top_k,
            where=where,
        )

        if not hits:
            return {
                "answer": "No relevant emails found for this query. Try broadening your search or ensure emails have been fetched and indexed.",
                "sources": [],
                "chunks_used": 0,
            }

        # Filter by date range if specified
        if date_start or date_end:
            filtered = []
            for hit in hits:
                date = hit["metadata"].get("date", "")
                if date_start and date < date_start:
                    continue
                if date_end and date > date_end:
                    continue
                filtered.append(hit)
            hits = filtered if filtered else hits  # Fall back to unfiltered if all filtered out

        # Build context from retrieved chunks
        context_chunks = [hit["text"] for hit in hits]

        # Query the LLM
        answer = self.llm.query(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=question,
            context_chunks=context_chunks,
        )

        return {
            "answer": answer,
            "sources": hits,
            "chunks_used": len(hits),
        }

    def build_timeline(self, topic: str, top_k: int = 30) -> dict:
        """Build a chronological timeline for a topic.

        Args:
            topic: What to build a timeline for (e.g., "settlement discussions")
            top_k: Number of chunks to retrieve

        Returns:
            {
                "timeline": str,
                "sources": list,
            }
        """
        timeline_prompt = (
            f"Create a detailed chronological timeline of: {topic}\n\n"
            "For each event, include:\n"
            "- Exact date\n"
            "- Who said/did what\n"
            "- Key details\n"
            "- Citation [Email from <sender>, <date>, Subject: \"<subject>\"]\n\n"
            "Present in chronological order. Only include events found in the provided emails."
        )

        return self.query(timeline_prompt, top_k=top_k)


def build_index(db, embedder: LocalEmbedder, vectorstore: VectorStore,
                chunk_size: int = 500, chunk_overlap: int = 50,
                progress_cb=None) -> int:
    """Build or rebuild the full RAG index from the database.

    Returns total chunks indexed.
    """
    from casepulse.rag.chunker import build_all_chunks

    if progress_cb:
        progress_cb("Building chunks from emails...")

    chunks = build_all_chunks(db, chunk_size, chunk_overlap, progress_cb)

    if not chunks:
        if progress_cb:
            progress_cb("No chunks to index. Fetch emails first.")
        return 0

    if progress_cb:
        progress_cb(f"Generating embeddings for {len(chunks)} chunks...")

    texts = [c["text"] for c in chunks]
    embeddings = embedder.embed_texts(texts, progress_cb=progress_cb)

    if progress_cb:
        progress_cb("Indexing in vector store...")

    total = vectorstore.rebuild(chunks, embeddings, progress_cb)

    if progress_cb:
        progress_cb(f"Index complete. {total} chunks indexed.")

    return total
