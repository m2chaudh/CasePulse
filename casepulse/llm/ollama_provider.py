"""Ollama LLM provider — fully local, fully private.

Ollama is started on-demand and stopped when no longer needed.
Zero resource usage when CasePulse is not actively querying.
"""
from __future__ import annotations

import atexit
import subprocess
import time
from typing import Optional

from casepulse.llm.base import LLMProvider

# Module-level tracker so we only manage one process
_ollama_process: Optional[subprocess.Popen] = None


def _cleanup_ollama():
    """Shut down Ollama if we started it."""
    global _ollama_process
    if _ollama_process and _ollama_process.poll() is None:
        _ollama_process.terminate()
        try:
            _ollama_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _ollama_process.kill()
        _ollama_process = None


atexit.register(_cleanup_ollama)


class OllamaProvider(LLMProvider):
    """Local LLM via Ollama. No data leaves your machine.

    Automatically starts `ollama serve` if it isn't running,
    and shuts it down when the Python process exits.
    """

    def __init__(self, model: str = "llama3.1:8b",
                 base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _ensure_running(self):
        """Start Ollama if it isn't already running."""
        if self.is_available():
            return  # Already running (user started it, or we did earlier)

        global _ollama_process
        if _ollama_process and _ollama_process.poll() is None:
            return  # Our process is still alive, just slow to respond

        _ollama_process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait up to 10 seconds for it to be ready
        for _ in range(20):
            time.sleep(0.5)
            if self.is_available():
                return

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        self._ensure_running()

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
        self._ensure_running()
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
        self._ensure_running()
        try:
            import ollama
            for progress in ollama.pull(model, stream=True):
                if progress_cb and isinstance(progress, dict):
                    status = progress.get("status", "")
                    progress_cb(status)
            return True
        except Exception:
            return False

    def describe_image(self, image_path: str, prompt: str = "",
                       vision_model: str = "llava:7b") -> str:
        """Use a vision model to describe an image.

        Args:
            image_path: Path to the image file
            prompt: What to look for (default: general description)
            vision_model: Ollama vision model to use

        Returns:
            Text description of the image
        """
        self._ensure_running()

        import base64
        from pathlib import Path

        img_bytes = Path(image_path).read_bytes()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        if not prompt:
            prompt = (
                "Describe this image in detail. If it contains text, transcribe it exactly. "
                "If it's a screenshot of a conversation, extract all messages with senders and timestamps. "
                "If it's a document, extract the key content. "
                "Note any details that could be relevant to a legal case."
            )

        import ollama
        response = ollama.chat(
            model=vision_model,
            messages=[{
                "role": "user",
                "content": prompt,
                "images": [img_b64],
            }],
        )
        return response["message"]["content"]

    @staticmethod
    def stop():
        """Manually stop Ollama if CasePulse started it."""
        _cleanup_ollama()
