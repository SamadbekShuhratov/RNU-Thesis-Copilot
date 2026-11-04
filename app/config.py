"""Application configuration.

Static paths come from environment variables; user-editable runtime settings
(LLM provider, model, temperature ...) are persisted in ``data/settings.json``
and can be changed from the web portal without restarting the server.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RNU_DATA_DIR", BASE_DIR / "data")).resolve()
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "copilot.sqlite3"
UPLOAD_DIR = DATA_DIR / "uploads"
EXPORT_DIR = DATA_DIR / "exports"

HOST = os.environ.get("RNU_HOST", "127.0.0.1")
PORT = int(os.environ.get("RNU_PORT", "8765"))

DEFAULT_SETTINGS: dict[str, Any] = {
    # "ollama" | "openai_compatible" (LM Studio, llama.cpp server, vLLM, Jan) | "mock"
    "llm_provider": os.environ.get("RNU_LLM_PROVIDER", "ollama"),
    "llm_base_url": os.environ.get("RNU_LLM_BASE_URL", "http://localhost:11434"),
    "llm_model": os.environ.get("RNU_LLM_MODEL", "qwen2.5:14b-instruct"),
    "llm_api_key": os.environ.get("RNU_LLM_API_KEY", ""),
    "llm_temperature": 0.4,
    "llm_num_ctx": 16384,
    "llm_timeout_s": 600,
    "llm_json_retries": 2,
    # Employee 1 (PM) behaviour
    "max_auto_revisions": 1,
    "llm_judge": True,
    # Reference APIs (OpenAlex "polite pool" e-mail is optional)
    "openalex_mailto": os.environ.get("RNU_OPENALEX_MAILTO", ""),
    "references_per_query": 8,
    "references_from_year": 2015,
    # UI
    "ui_language": "uz",
}


class SettingsStore:
    """Thread-safe JSON-backed settings."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    self._data.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
            except (OSError, json.JSONDecodeError):
                pass

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def public(self) -> dict[str, Any]:
        data = self.all()
        if data.get("llm_api_key"):
            data["llm_api_key"] = "••••••"
        return data

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def override(self, values: dict[str, Any]) -> None:
        """Change settings for this process only (e.g. ``--demo``), without saving."""
        with self._lock:
            self._data.update({k: v for k, v in values.items() if k in DEFAULT_SETTINGS})
            self._transient = set(getattr(self, "_transient", set())) | set(values)

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key, value in values.items():
                if key not in DEFAULT_SETTINGS:
                    continue
                if key == "llm_api_key" and value == "••••••":
                    continue
                default = DEFAULT_SETTINGS[key]
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, int) and not isinstance(default, bool):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
                self._data[key] = value
            self._transient = set(getattr(self, "_transient", set())) - set(values)
            stored = {k: v for k, v in self._data.items() if k not in self._transient}
            if self.path.exists():
                try:
                    old = json.loads(self.path.read_text(encoding="utf-8"))
                    stored = {**{k: old[k] for k in self._transient if k in old}, **stored}
                except (OSError, json.JSONDecodeError):
                    pass
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")
            return dict(self._data)


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()
settings = SettingsStore(DATA_DIR / "settings.json")
