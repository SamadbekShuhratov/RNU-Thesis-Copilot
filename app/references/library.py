"""Reference library operations on the thesis state."""
from __future__ import annotations

from typing import Any

from .sources import make_key, normalize_doi, title_similarity, verify_reference


def find_duplicate(refs: list[dict[str, Any]], cand: dict[str, Any]) -> dict[str, Any] | None:
    doi = normalize_doi(cand.get("doi"))
    for r in refs:
        other = normalize_doi(r.get("doi"))
        if doi and other:
            if other == doi:
                return r
            continue          # two different DOIs are two different works
        if title_similarity(r.get("title", ""), cand.get("title", "")) > 0.95:
            return r
    return None


def add_reference(refs: list[dict[str, Any]], cand: dict[str, Any], *, verify: bool = True,
                  included: bool = True) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    """Return (new list, the stored reference, created?)."""
    refs = list(refs)
    dup = find_duplicate(refs, cand)
    if dup:
        return refs, dup, False
    ref = {k: cand.get(k) for k in ("title", "authors", "year", "venue", "volume", "issue", "pages", "doi",
                                     "url", "abstract", "type", "cited_by_count", "source", "source_id")}
    ref["authors"] = ref.get("authors") or []
    ref["doi"] = normalize_doi(ref.get("doi"))
    ref["key"] = make_key(ref, {r["key"] for r in refs})
    ref["included"] = included
    ref["status"] = "unverified"
    ref["notes"] = cand.get("notes", "")
    if verify:
        ref = verify_reference(ref)
    refs.append(ref)
    return refs, ref, True


def verified_included(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in refs if r.get("included", True) and r.get("status") == "verified"]
