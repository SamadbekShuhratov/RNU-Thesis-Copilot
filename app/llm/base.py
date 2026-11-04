"""Provider-agnostic LLM interface with robust JSON handling for local models."""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable


class LLMError(RuntimeError):
    pass


@dataclass
class LLMCallRecord:
    task: str
    seconds: float
    prompt_chars: int
    response_chars: int
    ok: bool


@dataclass
class LLMOptions:
    model: str
    temperature: float = 0.4
    num_ctx: int = 16384
    timeout_s: int = 600
    json_retries: int = 2


class LLM(ABC):
    """Base class. Subclasses implement ``_chat`` and ``list_models``."""

    provider = "base"

    def __init__(self, options: LLMOptions):
        self.options = options
        self.calls: list[LLMCallRecord] = []
        self.on_call: Callable[[LLMCallRecord], None] | None = None

    # ── provider hooks ─────────────────────────────────────────────────────
    @abstractmethod
    def _chat(self, messages: list[dict[str, str]], *, json_schema: dict | None,
              temperature: float, task: str) -> str: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    def health(self) -> dict[str, Any]:
        try:
            models = self.list_models()
            return {"ok": True, "provider": self.provider, "models": models,
                    "model_available": self.options.model in models or not models}
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            return {"ok": False, "provider": self.provider, "error": str(exc)}

    # ── public API ─────────────────────────────────────────────────────────
    def text(self, system: str, user: str, *, task: str, temperature: float | None = None) -> str:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        out = self._timed(messages, None, temperature, task)
        return clean_text(out)

    def json(self, system: str, user: str, schema: dict[str, Any], *, task: str,
             temperature: float | None = None) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system + "\n\nRespond with ONE valid JSON object only. No markdown fences, no commentary."},
            {"role": "user", "content": user + "\n\nJSON schema of the answer:\n" + json.dumps(schema, ensure_ascii=False)},
        ]
        last_error = ""
        for attempt in range(self.options.json_retries + 1):
            raw = self._timed(messages, schema, temperature, task if attempt == 0 else f"{task}#retry{attempt}")
            try:
                data = extract_json(raw)
                problems = check_schema(data, schema)
                if not problems:
                    return coerce_schema(data, schema)
                last_error = "; ".join(problems)
            except ValueError as exc:
                last_error = str(exc)
            messages = messages + [
                {"role": "assistant", "content": raw[:4000]},
                {"role": "user", "content": f"Your answer was not valid ({last_error}). Return the corrected JSON object only."},
            ]
        raise LLMError(f"Model did not return valid JSON for task '{task}': {last_error}")

    def _timed(self, messages, schema, temperature, task) -> str:
        t0 = time.time()
        ok = False
        out = ""
        try:
            out = self._chat(messages, json_schema=schema,
                             temperature=self.options.temperature if temperature is None else temperature,
                             task=task)
            ok = True
            return out
        finally:
            rec = LLMCallRecord(task=task, seconds=round(time.time() - t0, 2),
                                prompt_chars=sum(len(m["content"]) for m in messages),
                                response_chars=len(out), ok=ok)
            self.calls.append(rec)
            if self.on_call:
                try:
                    self.on_call(rec)
                except Exception:  # noqa: BLE001
                    pass


# ── helpers ────────────────────────────────────────────────────────────────
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def clean_text(text: str) -> str:
    text = _THINK.sub("", text or "")
    text = _FENCE.sub("", text.strip())
    return text.strip()


def extract_json(text: str) -> dict[str, Any]:
    """Return the first balanced JSON object found in ``text``."""
    text = clean_text(text)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        value = json.loads(candidate)
                        if isinstance(value, dict):
                            return value
                    except json.JSONDecodeError:
                        # tolerate trailing commas produced by small models
                        try:
                            value = json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
                            if isinstance(value, dict):
                                return value
                        except json.JSONDecodeError:
                            pass
                    break
        start = text.find("{", start + 1)
    raise ValueError("no JSON object found in model output")


_PY_TYPES = {"string": str, "array": list, "object": dict, "integer": int, "number": (int, float), "boolean": bool}


def check_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    problems = []
    for key in schema.get("required", []):
        if key not in data or data[key] in (None, ""):
            problems.append(f"missing field '{key}'")
    return problems


def coerce_schema(data: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Coerce top-level field types (small local models often mix them up)."""
    out = dict(data)
    for key, spec in schema.get("properties", {}).items():
        if key not in out:
            continue
        want = spec.get("type")
        val = out[key]
        if want == "string" and isinstance(val, list):
            out[key] = " ".join(str(v) for v in val)
        elif want == "string" and isinstance(val, dict):
            out[key] = " ".join(str(v) for v in val.values())
        elif want == "array" and isinstance(val, str):
            parts = [p.strip(" -•\t") for p in re.split(r"\n+|;\s*", val) if p.strip(" -•\t")]
            out[key] = parts
        elif want == "array" and isinstance(val, list) and spec.get("items", {}).get("type") == "string":
            out[key] = [v if isinstance(v, str) else " ".join(str(x) for x in (v.values() if isinstance(v, dict) else [v])) for v in val]
    return out


def obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """Tiny JSON-schema builder."""
    return {"type": "object", "properties": properties, "required": required or list(properties)}


S = {"type": "string"}
LS = {"type": "array", "items": {"type": "string"}}


def lobj(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": obj(properties)}
