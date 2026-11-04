"""Local LLM providers: Ollama and any OpenAI-compatible server
(LM Studio, llama.cpp ``llama-server``, vLLM, Jan, LocalAI ...)."""
from __future__ import annotations

from typing import Any

import requests

from .base import LLM, LLMError, LLMOptions


class OllamaLLM(LLM):
    provider = "ollama"

    def __init__(self, options: LLMOptions, base_url: str = "http://localhost:11434"):
        super().__init__(options)
        self.base_url = base_url.rstrip("/")
        self._schema_supported = True

    def list_models(self) -> list[str]:
        r = requests.get(f"{self.base_url}/api/tags", timeout=10)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))

    def _chat(self, messages, *, json_schema, temperature, task) -> str:
        payload: dict[str, Any] = {
            "model": self.options.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.options.num_ctx},
        }
        if json_schema is not None:
            payload["format"] = json_schema if self._schema_supported else "json"
        try:
            r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.options.timeout_s)
            if r.status_code >= 400 and json_schema is not None and self._schema_supported:
                # Older Ollama versions only accept format="json".
                self._schema_supported = False
                payload["format"] = "json"
                r = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.options.timeout_s)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed ({self.base_url}, model {self.options.model}): {exc}") from exc
        data = r.json()
        return data.get("message", {}).get("content", "")


class OpenAICompatibleLLM(LLM):
    provider = "openai_compatible"

    def __init__(self, options: LLMOptions, base_url: str = "http://localhost:1234", api_key: str = ""):
        super().__init__(options)
        base = base_url.rstrip("/")
        self.base_url = base if base.endswith("/v1") else base + "/v1"
        self.api_key = api_key
        self._json_mode = True

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_models(self) -> list[str]:
        r = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=10)
        r.raise_for_status()
        return sorted(m.get("id", "") for m in r.json().get("data", []))

    def _chat(self, messages, *, json_schema, temperature, task) -> str:
        payload: dict[str, Any] = {
            "model": self.options.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if json_schema is not None and self._json_mode:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": task.split("#")[0].replace("-", "_") or "answer", "schema": json_schema},
            }
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                              headers=self._headers(), timeout=self.options.timeout_s)
            if r.status_code >= 400 and "response_format" in payload:
                self._json_mode = False      # server does not support structured output
                payload.pop("response_format")
                r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                                  headers=self._headers(), timeout=self.options.timeout_s)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise LLMError(f"OpenAI-compatible request failed ({self.base_url}): {exc}") from exc
        choices = r.json().get("choices") or [{}]
        return choices[0].get("message", {}).get("content", "") or ""
