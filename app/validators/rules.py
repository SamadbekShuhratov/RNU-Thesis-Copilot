"""Employee 1's audit: the RNU Common Mistakes Checklist / Output Constraints Matrix.

Every check returns *findings*: ``{"code", "severity", "stage", "field", "params"}``.
``severity`` is ``block`` (the stage cannot be approved) or ``warn``.
Human-readable messages are rendered by :mod:`app.validators.messages`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Callable

from ..rules import rules, doc_type_rules, words_target
from .text import (
    citation_keys, count_sentences, flatten_text, has_statistic, key_terms, numbers_in,
    split_sentences, term_overlap, word_count,
)

Finding = dict[str, Any]


def F(code: str, severity: str, stage: str, field: str = "", **params: Any) -> Finding:
    return {"code": code, "severity": severity, "stage": stage, "field": field, "params": params}


def _lang(state: dict) -> str:
    return state.get("project", {}).get("language", "en")


def _doc_type(state: dict) -> str:
    return state.get("project", {}).get("doc_type", "course_work")


def _placeholders(stage: str, value: Any) -> list[Finding]:
    pattern = re.compile(rules()["placeholder_pattern"], re.IGNORECASE)
    found = pattern.findall(flatten_text(value))
    hits = pattern.finditer(flatten_text(value))
    examples = [m.group(0) for m in hits][:3]
    return [F("PLACEHOLDER", "block", stage, "", count=len(found), examples=examples)] if found else []


def _conclusion(stage: str, text: str) -> list[Finding]:
    need = rules()["chapter_conclusion"]["min_sentences"]
    n = count_sentences(text or "")
    if n < need:
        return [F("CONCLUSION_MISSING", "block", stage, "conclusion", sentences=n, required=need)]
    return []


def _length(state: dict, stage: str, text: str) -> list[Finding]:
    target = words_target(_doc_type(state), stage)
    if not target:
        return []
    n = word_count(text)
    lo, hi = target
    if n < lo or n > hi:
        return [F("LENGTH_OUT_OF_RANGE", "warn", stage, "", words=n, min=lo, max=hi,
                  pages=round(n / doc_type_rules(_doc_type(state))["words_per_page"], 1))]
    return []


def _sections_text(section: dict) -> str:
    parts = [flatten_text(v) for k, v in section.items() if k not in {"conclusion", "titles"}]
    return "\n".join(parts)


def _refs_index(state: dict) -> dict[str, dict]:
    return {r["key"]: r for r in state.get("references", [])}


def _citations(state: dict, stage: str, value: Any, require: bool = False) -> list[Finding]:
    out: list[Finding] = []
    refs = _refs_index(state)
    keys = citation_keys(flatten_text(value))
    if require and not keys:
        out.append(F("NO_CITATIONS", "block", stage))
    unknown = sorted({k for k in keys if k not in refs})
    if unknown:
        out.append(F("CITATION_UNKNOWN", "block", stage, "", keys=unknown))
    unverified = sorted({k for k in keys if k in refs and refs[k].get("status") != "verified"})
    if unverified:
        out.append(F("CITATION_UNVERIFIED", "block", stage, "", keys=unverified))
    excluded = sorted({k for k in keys if k in refs and not refs[k].get("included", True)})
    if excluded:
        out.append(F("CITATION_EXCLUDED", "block", stage, "", keys=excluded))
    return out


# ── stage checks ──────────────────────────────────────────────────────────
def check_goal(goal: str, language: str, stage: str = "architect") -> list[Finding]:
    cfg = rules()["goal"]
    out: list[Finding] = []
    if not (goal or "").strip():
        return [F("GOAL_MISSING", "block", stage, "goal")]
    n = count_sentences(goal)
    if n != cfg["sentences"]:
        out.append(F("GOAL_SENTENCES", "block", stage, "goal", sentences=n))
    wc = word_count(goal)
    low = goal.lower()
    vague = wc < cfg["min_words"] or any(re.search(p, goal, re.IGNORECASE) for p in rules()["vague_goal_patterns"])
    if vague:
        out.append(F("GOAL_VAGUE", "block", stage, "goal", words=wc, min=cfg["min_words"]))
    if wc > cfg["max_words"]:
        out.append(F("GOAL_TOO_LONG", "warn", stage, "goal", words=wc, max=cfg["max_words"]))
    verbs = rules()["smart_action_verbs"]
    stems = verbs.get(language, []) + verbs["en"]
    if not any(s in low for s in stems):
        out.append(F("GOAL_NO_ACTION", "warn", stage, "goal"))
    if not has_statistic(goal) and not re.search(r"\b(by|until|до|līdz|gacha)\b", low):
        out.append(F("GOAL_NOT_MEASURABLE", "warn", stage, "goal"))
    return out


def check_nails(nails: list[str], language: str, stage: str = "architect") -> list[Finding]:
    out: list[Finding] = []
    nails = [n for n in (nails or []) if isinstance(n, str) and n.strip()]
    if len(nails) != 3:
        out.append(F("NAILS_COUNT", "block", stage, "nails", count=len(nails)))
    prefixes = rules()["nail_prefixes"]
    for i, nail in enumerate(nails[:3]):
        accepted = [prefixes["en"][i]]
        if language in prefixes:
            accepted.append(prefixes[language][i])
        text = nail.strip().lstrip("0123456789.)-• ").strip()
        if not any(text.lower().startswith(p.lower()) for p in accepted):
            out.append(F("NAIL_PREFIX", "block", stage, f"nails.{i}", index=i + 1, expected=accepted))
        if word_count(text) < 8:
            out.append(F("NAIL_TOO_SHORT", "warn", stage, f"nails.{i}", index=i + 1))
    return out


def check_architect(state: dict) -> list[Finding]:
    s = "architect"
    o = state.get("outline") or {}
    lang = _lang(state)
    out: list[Finding] = []
    cfg = rules()["titles"]
    titles = [t for t in o.get("titles", []) if str(t).strip()]
    if not cfg["min"] <= len(titles) <= cfg["max"]:
        out.append(F("TITLES_COUNT", "block", s, "titles", count=len(titles), min=cfg["min"], max=cfg["max"]))
    if not str(o.get("selected_title", "")).strip():
        out.append(F("TITLE_NOT_SELECTED", "block", s, "selected_title"))
    for fld, code in (("object", "OBJECT_MISSING"), ("subject", "SUBJECT_MISSING")):
        if not str(o.get(fld, "")).strip():
            out.append(F(code, "block", s, fld))
    out += check_goal(o.get("goal", ""), lang, s)
    out += check_nails(o.get("nails", []), lang, s)
    if len(o.get("tasks", [])) < 3:
        out.append(F("TASKS_FEW", "warn", s, "tasks", count=len(o.get("tasks", []))))
    kws = o.get("keywords", [])
    if not 3 <= len(kws) <= 8:
        out.append(F("KEYWORDS_COUNT", "warn", s, "keywords", count=len(kws)))
    out += _placeholders(s, o)
    return out


def check_bounded(text: str, cfg_key: str, stage: str, field: str) -> list[Finding]:
    cfg = rules()[cfg_key]
    n = count_sentences(text or "")
    out: list[Finding] = []
    if not cfg["min_sentences"] <= n <= cfg["max_sentences"]:
        out.append(F("SENTENCE_BOUNDS", "block", stage, field, sentences=n,
                     min=cfg["min_sentences"], max=cfg["max_sentences"]))
    if not has_statistic(text or ""):
        out.append(F("NO_STATISTICS", "block", stage, field))
    return out


def check_opinion(text: str, language: str, stage: str, field: str) -> list[Finding]:
    markers = rules()["opinion_markers"]
    low = (text or "").lower()
    hits = [m for m in markers.get(language, []) + markers["en"] if m in low]
    return [F("OPINION_LANGUAGE", "block", stage, field, markers=sorted(set(hits)))] if hits else []


def check_facts(state: dict, stage: str) -> list[Finding]:
    out: list[Finding] = []
    facts = state.get("facts", [])
    if not facts:
        out.append(F("FACTS_NONE", "warn", stage, "facts"))
    unsourced = [f.get("id", "?") for f in facts if not str(f.get("source", "")).strip()]
    if unsourced:
        out.append(F("FACT_UNSOURCED", "block", stage, "facts", ids=unsourced))
    return out


def check_chapter1(state: dict) -> list[Finding]:
    s = "chapter1"
    c = state.get("chapter1") or {}
    lang = _lang(state)
    out: list[Finding] = []
    out += check_bounded(c.get("topicality", ""), "topicality", s, "topicality")
    out += check_bounded(c.get("problem_formulation", ""), "problem_formulation", s, "problem_formulation")
    out += check_opinion(c.get("topicality", "") + " " + c.get("problem_formulation", ""), lang, s, "problem_formulation")
    results = c.get("planned_results", []) or []
    if len(results) < 2:
        out.append(F("PLANNED_RESULTS_FEW", "block", s, "planned_results", count=len(results)))
    for i, r in enumerate(results):
        if not isinstance(r, dict):
            continue
        if not str(r.get("beneficiary", "")).strip():
            out.append(F("RESULT_NO_BENEFICIARY", "block", s, f"planned_results.{i}", index=i + 1))
        if not str(r.get("metric", "")).strip():
            out.append(F("RESULT_NO_METRIC", "block", s, f"planned_results.{i}", index=i + 1))
    out += check_facts(state, s)
    out += _citations(state, s, c)
    out += _conclusion(s, c.get("conclusion", ""))
    out += _length(state, s, _sections_text(c) + "\n" + c.get("conclusion", ""))
    out += _placeholders(s, c)
    return out


def check_literature(state: dict) -> list[Finding]:
    s = "literature"
    c = state.get("literature") or {}
    out: list[Finding] = []
    refs = [r for r in state.get("references", []) if r.get("included", True) and r.get("status") == "verified"]
    minimum = doc_type_rules(_doc_type(state)).get("min_references", 8)
    if not refs:
        out.append(F("REFS_NONE", "block", s, "references"))
    elif len(refs) < minimum:
        out.append(F("REFS_FEW", "warn", s, "references", count=len(refs), min=minimum))
    out += _citations(state, s, c, require=True)
    if not [g for g in c.get("gaps", []) if str(g).strip()]:
        out.append(F("GAPS_MISSING", "block", s, "gaps"))
    if not c.get("comparison"):
        out.append(F("COMPARISON_MISSING", "warn", s, "comparison"))
    if _doc_type(state) == "conference_paper":
        out += _conclusion(s, c.get("conclusion", ""))
    elif not str(c.get("conclusion", "")).strip():
        out.append(F("SECTION_SUMMARY_MISSING", "warn", s, "conclusion"))
    out += _length(state, s, _sections_text(c))
    out += _placeholders(s, c)
    return out


def check_theory(state: dict) -> list[Finding]:
    s = "theory"
    c = state.get("theory") or {}
    out: list[Finding] = []
    if len(c.get("concepts", [])) < 2:
        out.append(F("CONCEPTS_FEW", "block", s, "concepts", count=len(c.get("concepts", []))))
    if len(c.get("frameworks", [])) < 1:
        out.append(F("FRAMEWORKS_MISSING", "block", s, "frameworks"))
    gaps = [g for g in (state.get("literature") or {}).get("gaps", []) if str(g).strip()]
    mapping = [m for m in c.get("gap_to_solution", []) if isinstance(m, dict) and m.get("gap") and m.get("solution_element")]
    if not mapping or len(mapping) < min(len(gaps), 2):
        out.append(F("GAP_MAPPING_MISSING", "block", s, "gap_to_solution", mapped=len(mapping), gaps=len(gaps)))
    out += _citations(state, s, c)
    out += _conclusion(s, c.get("conclusion", ""))
    out += _length(state, s, _sections_text(c) + "\n" + c.get("conclusion", ""))
    out += _placeholders(s, c)
    return out


def implementation_evidence(impl: dict) -> dict[str, Any]:
    """Inspect the local implementation folder (if any): count real code files."""
    ev: dict[str, Any] = {"code_files": 0, "has_readme": False, "has_git": False, "has_tests": False,
                          "path_exists": False, "languages": {}}
    path = str(impl.get("local_path", "")).strip()
    if not path:
        return ev
    root = Path(os.path.expanduser(path))
    if not root.is_dir():
        return ev
    ev["path_exists"] = True
    exts = set(rules()["code_extensions"])
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".next"}
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        rel = Path(dirpath).relative_to(root)
        if ".git" in rel.parts:
            continue
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in exts:
                count += 1
                ev["languages"][ext] = ev["languages"].get(ext, 0) + 1
                if "test" in fn.lower() or "tests" in rel.parts:
                    ev["has_tests"] = True
            if fn.lower().startswith("readme"):
                ev["has_readme"] = True
        if count > 20000:
            break
    ev["code_files"] = count
    ev["has_git"] = (root / ".git").exists()
    return ev


def allowed_result_numbers(state: dict) -> set[str]:
    analysis = (state.get("experiments") or {}).get("analysis") or {}
    allowed: set[str] = set()

    def add(v: Any) -> None:
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            for fmt in ("{:.0f}", "{:.1f}", "{:.2f}", "{:.3f}", "{:.4f}"):
                s = fmt.format(abs(v))
                allowed.add(s)
                allowed.add(s.rstrip("0").rstrip(".") if "." in s else s)
            g = f"{abs(v):.3g}"
            mant, _, exp = g.partition("e")
            allowed.add(mant)
            if exp:
                allowed.add(exp.lstrip("+-").lstrip("0") or "0")
                allowed.add(exp.lstrip("+"))
        elif isinstance(v, dict):
            for x in v.values():
                add(x)
        elif isinstance(v, list):
            for x in v:
                add(x)

    add(analysis)
    for i in range(0, 11):          # small counts / list numbering are always fine
        allowed.add(str(i))
    allowed.update({"95", "0.05", "100"})   # CI level, alpha, percent base
    return allowed


def _normalize_number(n: str) -> str:
    n = n.replace("−", "-").replace(",", ".")
    n = re.sub(r"[^\d.]", "", n)
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def check_practical(state: dict) -> list[Finding]:
    s = "practical"
    c = state.get("practical") or {}
    impl = state.get("implementation") or {}
    out: list[Finding] = []
    if not (str(impl.get("repo_url", "")).strip() or str(impl.get("local_path", "")).strip()):
        out.append(F("IMPL_EVIDENCE_MISSING", "block", s, "implementation"))
    ev = implementation_evidence(impl)
    if str(impl.get("local_path", "")).strip():
        if not ev["path_exists"]:
            out.append(F("IMPL_PATH_NOT_FOUND", "block", s, "implementation.local_path", path=impl["local_path"]))
        elif ev["code_files"] == 0:
            out.append(F("IMPL_NO_CODE", "block", s, "implementation.local_path"))
        elif not ev["has_tests"]:
            out.append(F("IMPL_NO_TESTS", "warn", s, "implementation.local_path"))
    if not (str(impl.get("run_command", "")).strip() or str(impl.get("deploy_steps", "")).strip()):
        out.append(F("IMPL_RUN_MISSING", "block", s, "implementation.run_command"))
    analysis = (state.get("experiments") or {}).get("analysis")
    if (state.get("experiments") or {}).get("is_sample"):
        out.append(F("EXPERIMENT_SAMPLE_DATA", "block", s, "experiments"))
    if not analysis or not analysis.get("metrics"):
        out.append(F("EXPERIMENTS_MISSING", "block", s, "experiments"))
    else:
        for m in analysis["metrics"]:
            if min(m["baseline"]["n"], m["proposed"]["n"]) < 5:
                out.append(F("EXPERIMENT_SMALL_SAMPLE", "warn", s, "experiments", metric=m["metric"]))
        allowed = allowed_result_numbers(state)
        unbacked = []
        for n in numbers_in(c.get("results_discussion", "")):
            norm = _normalize_number(n)
            if norm and norm not in allowed and not re.fullmatch(r"(19|20)\d\d", norm):
                unbacked.append(n.strip())
        if unbacked:
            out.append(F("RESULT_NUMBER_UNBACKED", "block", s, "results_discussion", numbers=sorted(set(unbacked))[:8]))
    if not c.get("deployment_steps"):
        out.append(F("DEPLOYMENT_STEPS_MISSING", "block", s, "deployment_steps"))
    if not str(c.get("architecture", "")).strip():
        out.append(F("ARCHITECTURE_MISSING", "block", s, "architecture"))
    out += _citations(state, s, c)
    out += _conclusion(s, c.get("conclusion", ""))
    out += _length(state, s, _sections_text(c) + "\n" + c.get("conclusion", ""))
    out += _placeholders(s, c)
    return out


def check_conclusion(state: dict) -> list[Finding]:
    s = "conclusion"
    c = state.get("conclusion") or {}
    out: list[Finding] = []
    text = c.get("general_conclusion", "")
    evidence = flatten_text(c.get("nail_evidence", []))
    combined = text + "\n" + evidence
    nails = (state.get("outline") or {}).get("nails", [])
    prefixes = [p for ps in rules()["nail_prefixes"].values() for p in ps]
    threshold = rules()["nail_term_overlap"]
    prefix_words = {w.lower() for p in prefixes for w in p.split()}
    for i, nail in enumerate(nails[:3]):
        terms = key_terms(nail, skip=prefix_words)
        ratio, missing = term_overlap(terms, combined)
        if ratio < threshold:
            out.append(F("NAIL_TERMS_CHANGED", "block", s, "general_conclusion", index=i + 1,
                         missing=missing, ratio=round(ratio, 2)))
    cfg = rules()["general_conclusion"]
    wc = word_count(text)
    if _doc_type(state) != "conference_paper" and not cfg["min_words"] <= wc <= cfg["max_words"]:
        out.append(F("CONCLUSION_LENGTH", "warn", s, "general_conclusion", words=wc,
                     min=cfg["min_words"], max=cfg["max_words"]))
    if count_sentences(text) < 2:
        out.append(F("CONCLUSION_MISSING", "block", s, "general_conclusion", sentences=count_sentences(text), required=2))
    abstract = c.get("abstract", "")
    limit = rules()["science_week"]["abstract_max_words"]
    if _doc_type(state) == "conference_paper":
        if not abstract.strip():
            out.append(F("ABSTRACT_MISSING", "block", s, "abstract"))
        elif word_count(abstract) > limit:
            out.append(F("ABSTRACT_TOO_LONG", "block", s, "abstract", words=word_count(abstract), max=limit))
    out += _citations(state, s, c)
    out += _placeholders(s, c)
    return out


def check_references(state: dict) -> list[Finding]:
    s = "references"
    out: list[Finding] = []
    all_text = "\n".join(flatten_text(state.get(k)) for k in
                         ("chapter1", "literature", "theory", "practical", "conclusion"))
    out += _citations(state, s, all_text)
    cited = set(citation_keys(all_text))
    included = [r for r in state.get("references", []) if r.get("included", True)]
    uncited = sorted(r["key"] for r in included if r["key"] not in cited)
    if uncited:
        out.append(F("REF_UNCITED", "warn", s, "references", keys=uncited[:12], count=len(uncited)))
    no_link = sorted(r["key"] for r in included if r["key"] in cited and not (r.get("doi") or r.get("url")))
    if no_link:
        out.append(F("REF_NO_LINK", "warn", s, "references", keys=no_link))
    return out


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def check_submission(state: dict, stage: str = "final") -> list[Finding]:
    cfg = rules()["science_week"]
    sub = state.get("submission") or {}
    out: list[Finding] = []
    authors = sub.get("authors") or []
    if not 1 <= len(authors) <= cfg["max_authors"]:
        out.append(F("AUTHORS_COUNT", "block", stage, "submission.authors", count=len(authors), max=cfg["max_authors"]))
    corresponding = [a for a in authors if a.get("corresponding")]
    if len(corresponding) != 1:
        out.append(F("CORRESPONDING_AUTHOR", "block", stage, "submission.authors", count=len(corresponding)))
    for i, a in enumerate(authors):
        missing = [k for k in ("first_name", "surname", "affiliation", "email") if not str(a.get(k, "")).strip()]
        if missing:
            out.append(F("AUTHOR_FIELDS", "block", stage, f"submission.authors.{i}", index=i + 1, missing=missing))
        elif not EMAIL_RE.match(a["email"].strip()):
            out.append(F("AUTHOR_EMAIL", "block", stage, f"submission.authors.{i}", index=i + 1))
    if sub.get("technical_section") not in cfg["technical_sections"]:
        out.append(F("TECHNICAL_SECTION", "block", stage, "submission.technical_section"))
    kws = [k.strip() for k in re.split(r";", sub.get("keywords", "")) if k.strip()]
    if not cfg["keywords_min"] <= len(kws) <= cfg["keywords_max"]:
        out.append(F("SUBMISSION_KEYWORDS", "block", stage, "submission.keywords", count=len(kws),
                     min=cfg["keywords_min"], max=cfg["keywords_max"]))
    if sub.get("presentation_type") not in cfg["presentation_types"]:
        out.append(F("PRESENTATION_TYPE", "block", stage, "submission.presentation_type"))
    title = (state.get("outline") or {}).get("selected_title", "")
    if not title.strip():
        out.append(F("TITLE_NOT_SELECTED", "block", stage, "outline.selected_title"))
    return out


def estimate_pages(state: dict) -> float:
    dt_rules = doc_type_rules(_doc_type(state))
    text = "\n".join(flatten_text(state.get(k)) for k in
                     ("chapter1", "literature", "theory", "practical", "conclusion"))
    refs = len([r for r in state.get("references", []) if r.get("included", True)])
    return round(word_count(text) / dt_rules["words_per_page"] + refs * 0.06 + 0.4, 1)


def check_final(state: dict) -> list[Finding]:
    out: list[Finding] = []
    for stage in state.get("stages", []):
        if stage == "final":
            continue
        for f in CHECKS[stage](state):
            if f["severity"] == "block":
                out.append(f)
    if _doc_type(state) == "conference_paper":
        out += check_submission(state)
        pages = state.get("compliance", {}).get("page_count_exact") or estimate_pages(state)
        lo, hi = rules()["science_week"]["pages"]
        exact = bool(state.get("compliance", {}).get("page_count_exact"))
        if not lo <= pages <= hi:
            out.append(F("PAPER_PAGES", "block" if exact else "warn", "final", "", pages=pages, min=lo, max=hi,
                         exact=exact))
    pending = [s for s, st in state.get("stage_status", {}).items() if s != "final" and st != "approved"]
    if pending:
        out.append(F("STAGES_NOT_APPROVED", "block", "final", "", stages=pending))
    return out


CHECKS: dict[str, Callable[[dict], list[Finding]]] = {
    "architect": check_architect,
    "chapter1": check_chapter1,
    "literature": check_literature,
    "theory": check_theory,
    "practical": check_practical,
    "conclusion": check_conclusion,
    "references": check_references,
    "final": check_final,
}


def validate_stage(stage: str, state: dict) -> list[Finding]:
    return CHECKS[stage](state)


def blocking(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f["severity"] == "block"]


__all__ = ["validate_stage", "blocking", "CHECKS", "check_goal", "check_nails", "check_bounded",
           "implementation_evidence", "estimate_pages", "check_submission", "split_sentences"]
