"""Experiment: hallucinated references — plain LLM vs. the verified pipeline.

baseline : ask the local model directly for N references (title + DOI) on each topic
proposed : take N references from OpenAlex (the Employee 4 route)
Both are checked independently with Crossref (DOI exists AND title matches).

Output is a CSV in the portal's measurement format, so you can upload it on the
"Implementation & data" tab and let Employee 6 analyse it:

    python scripts/benchmark_citations.py --model qwen2.5:14b-instruct --out citations.csv \
        --topic "invoice data extraction" --topic "thesis compliance checking" --topic "warehouse demand forecasting"

Requires internet access to api.openalex.org and api.crossref.org and a running local LLM.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.llm import create_llm  # noqa: E402
from app.llm.base import S, lobj, obj  # noqa: E402
from app.references.sources import search_openalex, verify_reference  # noqa: E402

SCHEMA = obj({"references": lobj({"title": S, "doi": S, "year": S, "authors": S})})


def verified_share(refs: list[dict]) -> float:
    if not refs:
        return 0.0
    ok = 0
    for r in refs:
        res = verify_reference({"title": r.get("title", ""), "doi": r.get("doi", ""), "authors": []})
        ok += res["status"] == "verified"
    return ok / len(refs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--topic", action="append", required=True)
    ap.add_argument("--out", default="citations.csv")
    args = ap.parse_args()
    cfg = settings.all()
    if args.model:
        cfg["llm_model"] = args.model
    llm = create_llm(cfg)
    rows = ["metric,variant,value,run"]
    for i, topic in enumerate(args.topic, start=1):
        try:
            data = llm.json("You are an academic research assistant.",
                            f"List {args.n} real, peer-reviewed publications about: {topic}. Give title, DOI, year, authors.",
                            SCHEMA, task="citation_benchmark")
            baseline_refs = data.get("references", [])[: args.n]
        except Exception as exc:  # noqa: BLE001
            print(f"baseline failed for {topic}: {exc}")
            baseline_refs = []
        proposed_refs = search_openalex(topic, per_page=args.n)
        b, p = verified_share(baseline_refs), verified_share(proposed_refs)
        print(f"{topic}: LLM-only verified {b:.0%} | pipeline verified {p:.0%}")
        rows.append(f"verified_reference_share,baseline,{b:.4f},{i}")
        rows.append(f"verified_reference_share,proposed,{p:.4f},{i}")
    Path(args.out).write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {args.out} — upload it in the portal (metric direction: higher is better)")


if __name__ == "__main__":
    main()
