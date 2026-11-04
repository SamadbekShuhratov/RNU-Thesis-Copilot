"""Empirical evaluation of Employee 1 (the RNU rule validator).

Measures precision / recall / F1 / accuracy of the "block" decision on a
labelled dataset of compliant and non-compliant fragments, plus the average
validation latency. Use it as one of the experiments in Chapter 3 of your own
course work (extend tests/data/validator_benchmark.jsonl with real examples
from your supervisor's "Common Mistakes Checklist").

    python scripts/benchmark_validators.py [--data tests/data/validator_benchmark.jsonl] [--csv out.csv]

The --csv output is in the portal's measurement format (metric,variant,value,run),
e.g. to compare the rule validator against a manual checklist baseline.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.validators.rules import check_bounded, check_goal, check_nails  # noqa: E402

CHECKERS = {
    "goal": lambda item: check_goal(item["text"], item.get("language", "en")),
    "nails": lambda item: check_nails(item["nails"], item.get("language", "en")),
    "problem": lambda item: check_bounded(item["text"], "problem_formulation", "chapter1", "p"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "tests/data/validator_benchmark.jsonl"))
    ap.add_argument("--csv", help="write per-item latency in the measurement CSV format")
    args = ap.parse_args()

    items = [json.loads(line) for line in Path(args.data).read_text(encoding="utf-8").splitlines() if line.strip()]
    tp = fp = tn = fn = 0
    latencies = []
    errors = []
    for item in items:
        t0 = time.perf_counter()
        findings = CHECKERS[item["kind"]](item)
        latencies.append((time.perf_counter() - t0) * 1000)
        predicted = any(f["severity"] == "block" for f in findings)
        expected = item["expected_block"]
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
            errors.append(("false positive", item, findings))
        elif not predicted and not expected:
            tn += 1
        else:
            fn += 1
            errors.append(("false negative", item, findings))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(items)
    print(f"items={len(items)}  TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"precision={precision:.3f}  recall={recall:.3f}  F1={f1:.3f}  accuracy={accuracy:.3f}")
    print(f"latency: mean={statistics.mean(latencies):.3f} ms  max={max(latencies):.3f} ms")
    for kind, item, findings in errors:
        print(f"- {kind}: {item.get('id')} {[f['code'] for f in findings]}")
    if args.csv:
        with open(args.csv, "w", encoding="utf-8") as fh:
            fh.write("metric,variant,value,run\n")
            for i, ms in enumerate(latencies, start=1):
                fh.write(f"check_latency_ms,proposed,{ms:.4f},{i}\n")
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
