"""Base LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        """Send a query to the LLM and return the response.

        Args:
            system_prompt: System/instruction prompt
            user_prompt: User's question
            context_chunks: Retrieved context chunks for RAG

        Returns:
            LLM response text
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available and configured."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Return a human-readable name for this provider."""
        ...
