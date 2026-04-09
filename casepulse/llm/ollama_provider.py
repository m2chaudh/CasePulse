"""Ollama LLM provider — fully local, fully private."""
from __future__ import annotations

from typing import Optional

from casepulse.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama. No data leaves your machine."""

    def __init__(self, model: str = "llama3.1:8b",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        import ollama

        messages = [{"role": "system", "content": system_prompt}]

        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
            messages.append({
                "role": "user",
                "content": (
                    f"Here is the relevant email context:\n\n{context_text}\n\n"
                    f"---\n\nQuestion: {user_prompt}"
                ),
            })
        else:
            messages.append({"role": "user", "content": user_prompt})

        response = ollama.chat(
            model=self.model,
            messages=messages,
        )
        return response["message"]["content"]

    def is_available(self) -> bool:
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return resp.ok
        except Exception:
            return False

    def get_name(self) -> str:
        return f"Ollama ({self.model})"

    def list_models(self) -> list[str]:
        """List locally available Ollama models."""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.ok:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def pull_model(self, model: str, progress_cb=None) -> bool:
        """Pull/download a model."""
        try:
            import ollama
            for progress in ollama.pull(model, stream=True):
                if progress_cb and isinstance(progress, dict):
                    status = progress.get("status", "")
                    progress_cb(status)
            return True
        except Exception:
            return False
