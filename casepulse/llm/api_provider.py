"""API-based LLM providers — Claude, OpenAI, or any OpenAI-compatible endpoint."""
from __future__ import annotations

from typing import Optional

from casepulse.llm.base import LLMProvider
from casepulse.llm.ollama_provider import OllamaProvider


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)

        content = user_prompt
        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
            content = (
                f"Here is the relevant email context:\n\n{context_text}\n\n"
                f"---\n\nQuestion: {user_prompt}"
            )

        message = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return message.content[0].text

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_name(self) -> str:
        return f"Claude ({self.model})"


class OpenAIProvider(LLMProvider):
    """OpenAI or any OpenAI-compatible API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o",
                 base_url: Optional[str] = None,
                 display_name: str = "OpenAI"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.display_name = display_name

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        from openai import OpenAI

        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        client = OpenAI(**kwargs)

        messages = [{"role": "system", "content": system_prompt}]

        content = user_prompt
        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
            content = (
                f"Here is the relevant email context:\n\n{context_text}\n\n"
                f"---\n\nQuestion: {user_prompt}"
            )

        messages.append({"role": "user", "content": content})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_name(self) -> str:
        return f"{self.display_name} ({self.model})"


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def query(self, system_prompt: str, user_prompt: str,
              context_chunks: list[str] = None) -> str:
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            system_instruction=system_prompt,
        )

        content = user_prompt
        if context_chunks:
            context_text = "\n\n---\n\n".join(context_chunks)
            content = (
                f"Here is the relevant email context:\n\n{context_text}\n\n"
                f"---\n\nQuestion: {user_prompt}"
            )

        response = model.generate_content(content)
        return response.text

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_name(self) -> str:
        return f"Gemini ({self.model})"


# All supported providers and their default models
PROVIDERS = {
    "ollama": {"label": "Ollama (Local)", "default_model": "llama3.1:8b", "needs_key": False},
    "gemini": {"label": "Google Gemini", "default_model": "gemini-2.5-flash", "needs_key": True},
    "claude": {"label": "Anthropic Claude", "default_model": "claude-sonnet-4-6", "needs_key": True},
    "openai": {"label": "OpenAI", "default_model": "gpt-4o", "needs_key": True},
    "custom": {"label": "Custom (OpenAI-compatible)", "default_model": "", "needs_key": True},
}


def create_provider(provider_type: str, **kwargs) -> LLMProvider:
    """Factory function to create the right LLM provider.

    Args:
        provider_type: One of 'ollama', 'gemini', 'claude', 'openai', 'custom'
        **kwargs: Provider-specific arguments (api_key, model, base_url)
    """
    if provider_type == "ollama":
        return OllamaProvider(
            model=kwargs.get("model", "llama3.1:8b"),
            base_url=kwargs.get("base_url", "http://localhost:11434"),
        )
    elif provider_type == "gemini":
        return GeminiProvider(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "gemini-2.5-flash"),
        )
    elif provider_type == "claude":
        return ClaudeProvider(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "claude-sonnet-4-6"),
        )
    elif provider_type == "openai":
        return OpenAIProvider(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", "gpt-4o"),
        )
    elif provider_type == "custom":
        return OpenAIProvider(
            api_key=kwargs.get("api_key", ""),
            model=kwargs.get("model", ""),
            base_url=kwargs.get("base_url"),
            display_name="Custom API",
        )
    else:
        raise ValueError(f"Unknown provider: {provider_type}")
