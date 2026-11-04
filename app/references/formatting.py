"""Citation styles (APA 7 and IEEE) and in-text citation rendering."""
from __future__ import annotations

import re
from typing import Any

from ..validators.text import CITATION_RE, citation_keys

Segment = tuple[str, bool]   # (text, italic)


def _initials(given: str) -> str:
    parts = [p for p in re.split(r"[\s\-]+", given or "") if p]
    return " ".join(p[0].upper() + "." for p in parts)


def _apa_author(a: dict[str, str]) -> str:
    fam, ini = a.get("family", "").strip(), _initials(a.get("given", ""))
    return f"{fam}, {ini}" if ini else fam


def _apa_authors(authors: list[dict[str, str]]) -> str:
    names = [_apa_author(a) for a in authors if a.get("family") or a.get("given")]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", … " + names[-1]


def _doi_url(ref: dict[str, Any]) -> str:
    if ref.get("doi"):
        return f"https://doi.org/{ref['doi']}"
    return ref.get("url", "")


def apa(ref: dict[str, Any]) -> list[Segment]:
    authors = _apa_authors(ref.get("authors", []))
    year = ref.get("year") or "n.d."
    title = (ref.get("title") or "").rstrip(".")
    segs: list[Segment] = []
    lead = f"{authors} ({year}). " if authors else f"{title}. ({year}). "
    segs.append((lead, False))
    if authors:
        segs.append((f"{title}. ", False))
    if ref.get("venue"):
        segs.append((ref["venue"], True))
        if ref.get("volume"):
            segs.append((", ", False))
            segs.append((str(ref["volume"]), True))
            if ref.get("issue"):
                segs.append((f"({ref['issue']})", False))
        if ref.get("pages"):
            segs.append((f", {ref['pages']}", False))
        segs.append((". ", False))
    link = _doi_url(ref)
    if link:
        segs.append((link, False))
    return segs


def _ieee_author(a: dict[str, str]) -> str:
    ini = _initials(a.get("given", ""))
    return f"{ini} {a.get('family', '')}".strip()


def ieee(ref: dict[str, Any], number: int) -> list[Segment]:
    names = [_ieee_author(a) for a in ref.get("authors", []) if a.get("family") or a.get("given")]
    if len(names) > 6:
        authors = names[0] + " et al."
    elif len(names) > 1:
        authors = ", ".join(names[:-1]) + ", and " + names[-1]
    else:
        authors = names[0] if names else ""
    segs: list[Segment] = [(f"[{number}] ", False)]
    if authors:
        segs.append((f"{authors}, ", False))
    segs.append((f"“{(ref.get('title') or '').rstrip('.')},” ", False))
    if ref.get("venue"):
        segs.append((ref["venue"], True))
        segs.append((", ", False))
    if ref.get("volume"):
        segs.append((f"vol. {ref['volume']}, ", False))
    if ref.get("issue"):
        segs.append((f"no. {ref['issue']}, ", False))
    if ref.get("pages"):
        segs.append((f"pp. {ref['pages']}, ", False))
    segs.append((f"{ref.get('year') or 'n.d.'}", False))
    if ref.get("doi"):
        segs.append((f", doi: {ref['doi']}.", False))
    elif ref.get("url"):
        segs.append((f". [Online]. Available: {ref['url']}", False))
    else:
        segs.append((".", False))
    return segs


def plain(segments: list[Segment]) -> str:
    return "".join(t for t, _ in segments)


def order_references(refs: list[dict[str, Any]], style: str, texts_in_order: list[str]) -> list[dict[str, Any]]:
    cited_order: list[str] = []
    for t in texts_in_order:
        for k in citation_keys(t):
            if k not in cited_order:
                cited_order.append(k)
    index = {r["key"]: r for r in refs}
    cited = [index[k] for k in cited_order if k in index]
    if style == "ieee":
        return cited
    return sorted(cited, key=lambda r: ((r.get("authors") or [{}])[0].get("family", "") or r.get("title", "")).lower())


def bibliography(refs: list[dict[str, Any]], style: str, texts_in_order: list[str]) -> list[dict[str, Any]]:
    ordered = order_references(refs, style, texts_in_order)
    out = []
    for i, r in enumerate(ordered, start=1):
        segs = ieee(r, i) if style == "ieee" else apa(r)
        out.append({"key": r["key"], "number": i, "segments": segs, "text": plain(segs)})
    return out


def in_text(keys: list[str], refs: dict[str, dict[str, Any]], style: str, numbers: dict[str, int]) -> str:
    if style == "ieee":
        nums = sorted({numbers[k] for k in keys if k in numbers})
        return "[" + ", ".join(str(n) for n in nums) + "]" if nums else ""
    parts = []
    for k in keys:
        r = refs.get(k)
        if not r:
            continue
        fams = [a.get("family", "") for a in r.get("authors", []) if a.get("family")]
        if not fams:
            who = (r.get("title") or k)[:40]
        elif len(fams) == 1:
            who = fams[0]
        elif len(fams) == 2:
            who = f"{fams[0]} & {fams[1]}"
        else:
            who = f"{fams[0]} et al."
        parts.append(f"{who}, {r.get('year') or 'n.d.'}")
    return "(" + "; ".join(parts) + ")" if parts else ""


def render_citations(text: str, refs: dict[str, dict[str, Any]], style: str, numbers: dict[str, int]) -> str:
    def repl(m: re.Match) -> str:
        keys = citation_keys(m.group(0))
        return in_text(keys, refs, style, numbers) or m.group(0)
    return CITATION_RE.sub(repl, text or "")
