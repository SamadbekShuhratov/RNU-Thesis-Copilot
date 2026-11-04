"""LLM factory."""
from __future__ import annotations

from typing import Any

from .base import LLM, LLMError, LLMOptions  # noqa: F401
from .mock import MockLLM
from .providers import OllamaLLM, OpenAICompatibleLLM


def create_llm(settings: dict[str, Any]) -> LLM:
    opts = LLMOptions(
        model=settings.get("llm_model", ""),
        temperature=float(settings.get("llm_temperature", 0.4)),
        num_ctx=int(settings.get("llm_num_ctx", 16384)),
        timeout_s=int(settings.get("llm_timeout_s", 600)),
        json_retries=int(settings.get("llm_json_retries", 2)),
    )
    provider = settings.get("llm_provider", "ollama")
    if provider == "mock":
        return MockLLM(opts)
    if provider == "openai_compatible":
        return OpenAICompatibleLLM(opts, settings.get("llm_base_url", "http://localhost:1234"),
                                   settings.get("llm_api_key", ""))
    return OllamaLLM(opts, settings.get("llm_base_url", "http://localhost:11434"))
