"""Loader for the editable RNU rules file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RULES_PATH = Path(__file__).with_name("rnu_rules.yaml")


@lru_cache(maxsize=1)
def rules() -> dict[str, Any]:
    with RULES_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def reload_rules() -> dict[str, Any]:
    rules.cache_clear()
    return rules()


def doc_type_rules(doc_type: str) -> dict[str, Any]:
    types = rules()["doc_types"]
    return types.get(doc_type, types["course_work"])


def stages_for(doc_type: str) -> list[str]:
    return list(doc_type_rules(doc_type)["stages"])


def page_target(doc_type: str, stage: str) -> tuple[float, float] | None:
    pages = doc_type_rules(doc_type).get("pages", {})
    value = pages.get(stage)
    return (float(value[0]), float(value[1])) if value else None


def words_target(doc_type: str, stage: str) -> tuple[int, int] | None:
    target = page_target(doc_type, stage)
    if not target:
        return None
    wpp = doc_type_rules(doc_type)["words_per_page"]
    return int(target[0] * wpp), int(target[1] * wpp)
