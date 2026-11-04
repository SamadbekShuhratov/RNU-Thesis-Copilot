"""Empirical analysis of the student's REAL measurements (Chapter 3).

CSV format (one row per measurement)::

    metric,variant,value[,run]
    response_time_ms,baseline,412
    response_time_ms,proposed,265

Statistics: mean, std, median, 95 % CI, Welch's t-test, Mann–Whitney U,
Cohen's d and relative change. Numbers produced here are the ONLY numbers
Employee 6 may use in the results discussion (enforced by the validator).
"""
from __future__ import annotations

import csv
import io
import math
from typing import Any

import numpy as np
from scipy import stats


class ExperimentError(ValueError):
    pass


def parse_csv(text: str) -> list[dict[str, Any]]:
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ExperimentError("CSV has no header row")
    fields = {f.strip().lower(): f for f in reader.fieldnames}
    for need in ("metric", "variant", "value"):
        if need not in fields:
            raise ExperimentError(f"CSV must contain columns metric, variant, value (missing '{need}')")
    rows = []
    for i, raw in enumerate(reader, start=2):
        try:
            value = float(str(raw[fields["value"]]).replace(",", ".").strip())
        except (TypeError, ValueError):
            raise ExperimentError(f"line {i}: value is not a number: {raw[fields['value']]!r}") from None
        if math.isnan(value) or math.isinf(value):
            raise ExperimentError(f"line {i}: value must be finite")
        rows.append({
            "metric": str(raw[fields["metric"]]).strip(),
            "variant": str(raw[fields["variant"]]).strip(),
            "value": value,
            "run": str(raw.get(fields.get("run", ""), "") or "").strip(),
        })
    if not rows:
        raise ExperimentError("CSV contains no measurements")
    return rows


def _describe(values: list[float]) -> dict[str, Any]:
    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if n > 1 else 0.0
    if n > 1:
        half = float(stats.t.ppf(0.975, n - 1) * std / math.sqrt(n))
    else:
        half = 0.0
    return {"n": n, "mean": round(mean, 4), "std": round(std, 4), "median": round(float(np.median(arr)), 4),
            "min": round(float(arr.min()), 4), "max": round(float(arr.max()), 4),
            "ci95_low": round(mean - half, 4), "ci95_high": round(mean + half, 4)}


def analyze(rows: list[dict[str, Any]], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """config = {"metrics": {name: {"direction": "lower"|"higher", "unit": "ms"}},
                 "baseline": "baseline", "proposed": "proposed", "alpha": 0.05}"""
    config = dict(config or {})
    variants = sorted({r["variant"] for r in rows})
    baseline = config.get("baseline") or ("baseline" if "baseline" in variants else variants[0])
    proposed = config.get("proposed") or ("proposed" if "proposed" in variants else
                                          next((v for v in variants if v != baseline), baseline))
    if baseline == proposed:
        raise ExperimentError("need two variants (e.g. baseline and proposed) to compare")
    alpha = float(config.get("alpha", 0.05))
    metric_cfg = config.get("metrics", {})
    metrics_out = []
    for metric in sorted({r["metric"] for r in rows}):
        b = [r["value"] for r in rows if r["metric"] == metric and r["variant"] == baseline]
        p = [r["value"] for r in rows if r["metric"] == metric and r["variant"] == proposed]
        if not b or not p:
            continue
        cfg = metric_cfg.get(metric, {})
        direction = cfg.get("direction") or ("higher" if any(w in metric.lower() for w in
                                              ("accuracy", "precision", "recall", "f1", "throughput", "score",
                                               "success", "satisfaction", "auc")) else "lower")
        db, dp = _describe(b), _describe(p)
        change = dp["mean"] - db["mean"]
        change_pct = (change / db["mean"] * 100.0) if db["mean"] else 0.0
        t_p = mw_p = None
        cohen_d = None
        if len(b) > 1 and len(p) > 1:
            if np.std(b) == 0 and np.std(p) == 0:
                t_p = 0.0 if db["mean"] != dp["mean"] else 1.0
            else:
                t_p = float(stats.ttest_ind(p, b, equal_var=False).pvalue)
            try:
                mw_p = float(stats.mannwhitneyu(p, b, alternative="two-sided").pvalue)
            except ValueError:
                mw_p = None
            pooled = math.sqrt(((len(b) - 1) * db["std"] ** 2 + (len(p) - 1) * dp["std"] ** 2) / (len(b) + len(p) - 2))
            cohen_d = round(change / pooled, 3) if pooled else None
        better = (change < 0) if direction == "lower" else (change > 0)
        significant = t_p is not None and t_p < alpha
        metrics_out.append({
            "metric": metric,
            "unit": cfg.get("unit", ""),
            "direction": direction,
            "baseline": db,
            "proposed": dp,
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "welch_p": None if t_p is None else float(f"{t_p:.3g}"),
            "mannwhitney_p": None if mw_p is None else float(f"{mw_p:.3g}"),
            "cohen_d": cohen_d,
            "improved": bool(better),
            "significant": bool(significant),
            "verdict": ("improved_significant" if better and significant else
                        "improved_not_significant" if better else
                        "worse_significant" if significant else "no_improvement"),
        })
    if not metrics_out:
        raise ExperimentError(f"no metric has measurements for both '{baseline}' and '{proposed}'")
    return {"baseline_name": baseline, "proposed_name": proposed, "alpha": alpha,
            "variants": variants, "metrics": metrics_out, "rows": len(rows)}


def summary_lines(analysis: dict[str, Any]) -> list[str]:
    """Compact, number-exact lines handed to Employee 6's prompt."""
    lines = []
    for m in analysis.get("metrics", []):
        unit = f" {m['unit']}" if m.get("unit") else ""
        lines.append(
            f"METRIC {m['metric']} ({m['direction']} is better): "
            f"{analysis['baseline_name']} mean={m['baseline']['mean']}{unit} (sd={m['baseline']['std']}, n={m['baseline']['n']}); "
            f"{analysis['proposed_name']} mean={m['proposed']['mean']}{unit} (sd={m['proposed']['std']}, n={m['proposed']['n']}); "
            f"change={m['change_pct']}%; Welch p={m['welch_p']}; Cohen d={m['cohen_d']}; verdict={m['verdict']}"
        )
    return lines


def chart_png(analysis: dict[str, Any]) -> bytes:
    """Bar chart (mean ± 95 % CI) per metric for the DOCX export."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metrics = analysis["metrics"]
    n = len(metrics)
    fig, axes = plt.subplots(1, n, figsize=(max(3.2 * n, 4.5), 3.2), squeeze=False)
    colors = ("#9AA5B1", "#1F6F8B")
    for ax, m in zip(axes[0], metrics):
        names = [analysis["baseline_name"], analysis["proposed_name"]]
        means = [m["baseline"]["mean"], m["proposed"]["mean"]]
        errs = [m["baseline"]["mean"] - m["baseline"]["ci95_low"], m["proposed"]["mean"] - m["proposed"]["ci95_low"]]
        ax.bar(names, means, yerr=errs, capsize=5, color=colors, edgecolor="#2D3748", linewidth=0.6)
        ax.set_title(m["metric"] + (f" ({m['unit']})" if m.get("unit") else ""), fontsize=9)
        ax.tick_params(labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    plt.close(fig)
    return buf.getvalue()


SAMPLE_CSV = """metric,variant,value,run
response_time_ms,baseline,412,1
response_time_ms,baseline,398,2
response_time_ms,baseline,430,3
response_time_ms,baseline,405,4
response_time_ms,baseline,421,5
response_time_ms,baseline,415,6
response_time_ms,proposed,268,1
response_time_ms,proposed,259,2
response_time_ms,proposed,281,3
response_time_ms,proposed,262,4
response_time_ms,proposed,270,5
response_time_ms,proposed,266,6
accuracy,baseline,0.81,1
accuracy,baseline,0.79,2
accuracy,baseline,0.82,3
accuracy,baseline,0.80,4
accuracy,baseline,0.78,5
accuracy,baseline,0.81,6
accuracy,proposed,0.88,1
accuracy,proposed,0.90,2
accuracy,proposed,0.87,3
accuracy,proposed,0.89,4
accuracy,proposed,0.91,5
accuracy,proposed,0.88,6
"""
