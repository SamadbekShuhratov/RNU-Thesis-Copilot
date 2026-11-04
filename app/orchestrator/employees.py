"""The seven drafting employees (2–8). Employee 1 lives in ``graph.py``.

Each employee is a function ``(state, ctx) -> stage output dict``. Long
chapters are produced with an *outline-then-expand* strategy so that local
models with limited context windows can still reach the RNU page targets.
"""
from __future__ import annotations

import copy
import json
import string
from pathlib import Path
from typing import Any

from ..experiments.analysis import summary_lines
from ..i18n import language_name
from ..references.formatting import bibliography
from ..references.library import add_reference, verified_included
from ..references.sources import SourceError, search_openalex, search_semantic_scholar
from ..rules import doc_type_rules, rules, words_target
from ..llm.base import LS, S, lobj, obj
from ..validators.text import flatten_text, word_count
from .engine import RunContext
from .state import EMPLOYEES

PROMPTS = Path(__file__).with_name("prompts")

CHAPTER_NAMES = {
    "chapter1": "Chapter 1 — Introduction and Problem Formulation",
    "literature": "Chapter 2 (part 1) — Literature Review of Existing Methods",
    "theory": "Chapter 2 (part 2) — Theoretical and Engineering Framework",
    "practical": "Chapter 3 — Practical Implementation and Empirical Analysis",
}
PAPER_NAMES = {
    "chapter1": "Section 1 — Introduction",
    "literature": "Section 2 — Related Work",
    "practical": "Sections 3–4 — Method, Implementation and Results",
}


def prompt(name: str, **values: Any) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return string.Template(text).safe_substitute({k: ("" if v is None else v) for k, v in values.items()})


# ── context builders ──────────────────────────────────────────────────────
def _p(state: dict) -> dict:
    return state.get("project", {})


def is_paper(state: dict) -> bool:
    return _p(state).get("doc_type") == "conference_paper"


def chapter_name(state: dict, stage: str) -> str:
    return (PAPER_NAMES if is_paper(state) else CHAPTER_NAMES).get(stage, stage)


def system_prompt(state: dict, stage: str) -> str:
    emp = EMPLOYEES[stage]
    return prompt("_system",
                  employee=f"Employee {emp['no']} ({emp['role']})",
                  doc_label=doc_type_rules(_p(state).get("doc_type", "course_work"))["label"],
                  language=language_name(_p(state).get("language", "en")))


def plan_text(state: dict) -> str:
    o = state.get("outline") or {}
    nails = o.get("nails", [])
    lines = [
        f"Title: {o.get('selected_title', '')}",
        f"Object: {o.get('object', '')}",
        f"Subject: {o.get('subject', '')}",
        f"Aim: {o.get('goal', '')}",
        "Tasks: " + "; ".join(o.get("tasks", [])),
        *[f"NAIL{i + 1}: {n}" for i, n in enumerate(nails)],
        "Keywords: " + ", ".join(o.get("keywords", [])),
    ]
    return "\n".join(lines)


def facts_text(state: dict) -> str:
    facts = state.get("facts", [])
    if not facts:
        return "(none provided)"
    return "\n".join(f"FACT {f.get('id')}: {f.get('text')} — source: {f.get('source', '')}" for f in facts)


def refs_text(state: dict, limit: int = 40, abstract_chars: int = 320) -> str:
    refs = verified_included(state.get("references", []))[:limit]
    if not refs:
        return "(no verified references yet)"
    out = []
    for r in refs:
        authors = ", ".join(a.get("family", "") for a in r.get("authors", [])[:3])
        if len(r.get("authors", [])) > 3:
            authors += " et al."
        abstract = (r.get("abstract") or "").replace("\n", " ")[:abstract_chars]
        out.append(f"- {r['key']} — {authors} ({r.get('year')}). {r.get('title')}. {abstract}")
    return "\n".join(out)


def feedback_text(state: dict) -> str:
    fb = (state.get("feedback") or "").strip()
    return f"\nREVISION REQUEST — fix these issues in this version:\n{fb}\n" if fb else ""


def _llm(ctx: RunContext):
    return ctx.services["llm"]


def _target_words(state: dict, stage: str) -> int:
    t = words_target(_p(state).get("doc_type", "course_work"), stage)
    return int((t[0] + t[1]) / 2) if t else 1500


def _section_words(state: dict) -> int:
    return 260 if is_paper(state) else 550


def _summarize(sections: list[dict], chars: int = 220) -> str:
    return "\n".join(f"- {s.get('heading')}: {(s.get('text') or '')[:chars]}" for s in sections)


def _revise_scope(state: dict) -> dict:
    return state.get("revise_scope") or {}


def write_sections(state: dict, ctx: RunContext, stage: str, n: int, material: str,
                   context: str, previous: list[dict] | None = None) -> list[dict]:
    """Outline-then-expand. Respects a single-section revision scope."""
    llm = _llm(ctx)
    sys = system_prompt(state, stage)
    lang = language_name(_p(state).get("language", "en"))
    scope = _revise_scope(state)
    words = _section_words(state)
    if previous and scope.get("section") is not None:
        sections = copy.deepcopy(previous)
        idx = int(scope["section"])
        if 0 <= idx < len(sections):
            ctx.progress(f"Rewriting subsection {idx + 1}: {sections[idx]['heading']}", stage=stage)
            sections[idx]["text"] = llm.text(sys, prompt(
                "write_section", heading=sections[idx]["heading"], focus=sections[idx].get("focus", ""),
                chapter=chapter_name(state, stage), words=words, plan=plan_text(state), material=material,
                feedback=feedback_text(state), language=lang), task=f"{stage}_section")
        return sections
    if n <= 0:
        return []
    ctx.progress(f"Planning {n} subsection(s)", stage=stage)
    plan = llm.json(sys, prompt("plan_sections", chapter=chapter_name(state, stage), target_words=n * words,
                                plan=plan_text(state), context=context, feedback=feedback_text(state),
                                n_sections=n),
                    obj({"sections": lobj({"heading": S, "focus": S})}), task=f"{stage}_plan")
    sections = [s for s in plan.get("sections", []) if isinstance(s, dict) and s.get("heading")][:max(n, 1)]
    for i, sec in enumerate(sections):
        ctx.check_cancel()
        ctx.progress(f"Writing subsection {i + 1}/{len(sections)}: {sec['heading']}", stage=stage)
        sec["text"] = llm.text(sys, prompt(
            "write_section", heading=sec["heading"], focus=sec.get("focus", ""),
            chapter=chapter_name(state, stage), words=words, plan=plan_text(state), material=material,
            feedback=feedback_text(state), language=lang), task=f"{stage}_section")
    return sections


def write_conclusion(state: dict, ctx: RunContext, stage: str, content: str, extra: str = "") -> str:
    ctx.progress("Writing the chapter conclusion", stage=stage)
    return _llm(ctx).text(system_prompt(state, stage), prompt(
        "chapter_conclusion", chapter=chapter_name(state, stage), content=content[:6000], extra=extra,
        language=language_name(_p(state).get("language", "en"))), task=f"{stage}_conclusion")


def _keep_or_redo(state: dict, stage: str, field: str) -> bool:
    """When only one subsection is revised, keep the rest of the stage."""
    scope = _revise_scope(state)
    return scope.get("section") is not None and bool((state.get(EMPLOYEES[stage]["key"]) or {}).get(field))


# ── Employee 2 ────────────────────────────────────────────────────────────
ARCHITECT_SCHEMA = obj({"titles": LS, "selected_title": S, "object": S, "subject": S, "goal": S,
                        "tasks": LS, "nails": LS, "keywords": LS, "rationale": S})


def employee_architect(state: dict, ctx: RunContext) -> dict:
    p = _p(state)
    lang = p.get("language", "en")
    pref = rules()["nail_prefixes"]
    prefixes = pref.get(lang, pref["en"]) if lang != "en" else pref["en"]
    ctx.progress("Brainstorming titles, aim and the Three Nails", stage="architect")
    out = _llm(ctx).json(system_prompt(state, "architect"), prompt(
        "architect", topic=p.get("topic"), object_hint=p.get("object_hint"), subject_hint=p.get("subject_hint"),
        field=p.get("field"), notes=p.get("notes"), feedback=feedback_text(state),
        prefix1=prefixes[0], prefix2=prefixes[1], prefix3=prefixes[2]), ARCHITECT_SCHEMA, task="architect")
    if out.get("selected_title") and out["selected_title"] not in out.get("titles", []):
        out.setdefault("titles", []).insert(0, out["selected_title"])
    return out


# ── Employee 3 ────────────────────────────────────────────────────────────
CH1_SCHEMA = obj({"topicality": S, "problem_formulation": S, "research_questions": LS, "methods": S,
                  "planned_results": lobj({"result": S, "metric": S, "beneficiary": S}),
                  "novelty": S, "structure": S})


def employee_chapter1(state: dict, ctx: RunContext) -> dict:
    stage = "chapter1"
    previous = state.get("chapter1") or {}
    if _keep_or_redo(state, stage, "sections"):
        out = copy.deepcopy(previous)
    else:
        ctx.progress("Drafting topicality, problem formulation and planned results", stage=stage)
        out = _llm(ctx).json(system_prompt(state, stage), prompt(
            "chapter1_core", plan=plan_text(state), facts=facts_text(state), references=refs_text(state, 25, 200),
            feedback=feedback_text(state)), CH1_SCHEMA, task="chapter1_core")
    core_words = word_count(flatten_text({k: v for k, v in out.items() if k not in ("sections", "conclusion")}))
    n = max(0, min(12, round((_target_words(state, stage) - core_words) / _section_words(state))))
    out["sections"] = write_sections(
        state, ctx, stage, n,
        material="FACTS:\n" + facts_text(state) + "\n\nREFERENCES:\n" + refs_text(state, 25, 200),
        context="Already written: topicality, problem formulation, research questions, methods, planned results, novelty. "
                "Plan subsections that deepen the description of the object, the current situation and the problem.",
        previous=previous.get("sections"))
    out["conclusion"] = write_conclusion(state, ctx, stage, flatten_text(out))
    return out


# ── Employee 4 ────────────────────────────────────────────────────────────
def discover_references(state: dict, ctx: RunContext) -> list[dict]:
    settings = ctx.services.get("settings", {})
    refs = list(state.get("references", []))
    ctx.progress("Generating search queries for OpenAlex", stage="literature")
    q = _llm(ctx).json(system_prompt(state, "literature"), prompt("search_queries", plan=plan_text(state)),
                       obj({"queries": LS}), task="search_queries")
    queries = [x for x in q.get("queries", []) if str(x).strip()][:6]
    searcher = ctx.services.get("search", search_openalex)
    for query in queries:
        ctx.check_cancel()
        ctx.progress(f"Searching OpenAlex: {query}", stage="literature")
        try:
            results = searcher(query, per_page=int(settings.get("references_per_query", 8)),
                               from_year=settings.get("references_from_year"),
                               mailto=settings.get("openalex_mailto", ""))
        except SourceError as exc:
            ctx.progress(f"OpenAlex unavailable ({exc}); trying Semantic Scholar", stage="literature")
            try:
                results = search_semantic_scholar(query, limit=int(settings.get("references_per_query", 8)))
            except SourceError as exc2:
                ctx.progress(f"Reference search failed: {exc2}", stage="literature", level="error")
                continue
        for cand in results:
            if not cand.get("title"):
                continue
            refs, ref, created = add_reference(refs, cand, verify=ctx.services.get("verify_refs", True))
            if created:
                ctx.progress(f"[{ref['status']}] {ref['key']}: {ref['title'][:80]}", stage="literature")
    return refs


LIT_SCHEMA = obj({"comparison": lobj({"approach": S, "sources": S, "strengths": S, "limitations": S}),
                  "gaps": LS, "conclusion": S})


def employee_literature(state: dict, ctx: RunContext) -> dict:
    stage = "literature"
    previous = state.get("literature") or {}
    update: dict[str, Any] = {}
    if not verified_included(state.get("references", [])) or _revise_scope(state).get("refresh_refs"):
        refs = discover_references(state, ctx)
        state["references"] = refs
        update["references"] = refs
    if not verified_included(state.get("references", [])):
        ctx.progress("No verified references — add or import sources, then request a revision.", stage=stage, level="warn")
        out = {"sections": [], "comparison": [], "gaps": [], "conclusion": "", "_update": update}
        return out
    n = max(1, min(14, round(_target_words(state, stage) / _section_words(state))))
    sections = write_sections(
        state, ctx, stage, n,
        material="VERIFIED REFERENCES (cite only these keys):\n" + refs_text(state),
        context="Group the literature by approach / school of thought; each subsection compares how other researchers "
                "tried to solve the problem.",
        previous=previous.get("sections"))
    ctx.progress("Comparing existing methods and extracting research gaps", stage=stage)
    core = _llm(ctx).json(system_prompt(state, stage), prompt(
        "literature_core", plan=plan_text(state), references=refs_text(state, 40, 160),
        content=_summarize(sections), feedback=feedback_text(state)), LIT_SCHEMA, task="literature_core")
    out = {"sections": sections, "comparison": core.get("comparison", []), "gaps": core.get("gaps", []),
           "conclusion": core.get("conclusion", ""), "_update": update}
    return out


# ── Employee 5 ────────────────────────────────────────────────────────────
THEORY_SCHEMA = obj({"concepts": lobj({"term": S, "definition": S}),
                     "frameworks": lobj({"name": S, "description": S, "how_used": S}),
                     "gap_to_solution": lobj({"gap": S, "solution_element": S})})


def employee_theory(state: dict, ctx: RunContext) -> dict:
    stage = "theory"
    previous = state.get("theory") or {}
    gaps = (state.get("literature") or {}).get("gaps", [])
    if _keep_or_redo(state, stage, "sections"):
        out = copy.deepcopy(previous)
    else:
        ctx.progress("Selecting concepts and engineering frameworks", stage=stage)
        out = _llm(ctx).json(system_prompt(state, stage), prompt(
            "theory_core", plan=plan_text(state), gaps="\n".join(f"- {g}" for g in gaps) or "(none)",
            references=refs_text(state, 40, 160), feedback=feedback_text(state)), THEORY_SCHEMA, task="theory_core")
    core_words = word_count(flatten_text({k: v for k, v in out.items() if k not in ("sections", "conclusion")}))
    n = max(0, min(10, round((_target_words(state, stage) - core_words) / _section_words(state))))
    out["sections"] = write_sections(
        state, ctx, stage, n,
        material="CONCEPTS & FRAMEWORKS:\n" + json.dumps({k: out.get(k) for k in ("concepts", "frameworks")},
                                                          ensure_ascii=False)[:3000]
                 + "\n\nVERIFIED REFERENCES (cite only these keys):\n" + refs_text(state, 30, 200),
        context="Explain the foundational concepts and frameworks in depth and how they back the student's own design.",
        previous=previous.get("sections"))
    mapping = "\n".join(f"- gap: {m.get('gap')} → solution: {m.get('solution_element')}"
                        for m in out.get("gap_to_solution", []))
    out["conclusion"] = write_conclusion(
        state, ctx, stage, flatten_text(out),
        extra="This is the conclusion of the whole Chapter 2. It MUST map each discovered gap directly to an element "
              "of the upcoming solution:\n" + mapping)
    return out


# ── Employee 6 ────────────────────────────────────────────────────────────
PRACTICAL_SCHEMA = obj({"architecture": S, "components": lobj({"name": S, "responsibility": S, "technology": S}),
                        "data_flow": S, "deployment_steps": LS, "experiment_design": S, "results_discussion": S})


def implementation_text(state: dict) -> str:
    impl = state.get("implementation") or {}
    ev = impl.get("evidence") or {}
    keys = ("description", "stack", "repo_url", "local_path", "run_command", "deploy_steps", "deployed_url")
    lines = [f"{k}: {impl.get(k)}" for k in keys if str(impl.get(k, "")).strip()]
    if ev:
        lines.append(f"evidence: {ev.get('code_files', 0)} code files, tests={ev.get('has_tests')}, "
                     f"languages={ev.get('languages')}")
    return "\n".join(lines) or "(no implementation details provided)"


def results_text(state: dict) -> str:
    analysis = (state.get("experiments") or {}).get("analysis")
    return "\n".join(summary_lines(analysis)) if analysis else "(no measurements uploaded)"


def employee_practical(state: dict, ctx: RunContext) -> dict:
    stage = "practical"
    previous = state.get("practical") or {}
    mapping = "\n".join(f"- {m.get('gap')} → {m.get('solution_element')}"
                        for m in (state.get("theory") or {}).get("gap_to_solution", [])) or \
        "\n".join(f"- {g}" for g in (state.get("literature") or {}).get("gaps", []))
    if _keep_or_redo(state, stage, "sections"):
        out = copy.deepcopy(previous)
    else:
        ctx.progress("Documenting architecture, deployment and experiments", stage=stage)
        out = _llm(ctx).json(system_prompt(state, stage), prompt(
            "practical_core", plan=plan_text(state), implementation=implementation_text(state), mapping=mapping,
            results=results_text(state), feedback=feedback_text(state)), PRACTICAL_SCHEMA, task="practical_core")
    core_words = word_count(flatten_text({k: v for k, v in out.items() if k not in ("sections", "conclusion")}))
    n = max(0, min(12, round((_target_words(state, stage) - core_words) / _section_words(state))))
    out["sections"] = write_sections(
        state, ctx, stage, n,
        material="IMPLEMENTATION:\n" + implementation_text(state) + "\n\nMEASURED RESULTS (copy exactly):\n"
                 + results_text(state),
        context="Describe the real implementation in depth (modules, algorithms, data model, interfaces, testing, "
                "validation). Do not invent features or numbers.",
        previous=previous.get("sections"))
    out["conclusion"] = write_conclusion(state, ctx, stage, flatten_text(out),
                                         extra="Mention whether the measured results support the aim.")
    return out


# ── Employee 7 ────────────────────────────────────────────────────────────
CONCLUSION_SCHEMA = obj({"general_conclusion": S, "nail_evidence": lobj({"nail": S, "evidence": S}),
                         "limitations": S, "future_work": S, "abstract": S})


def employee_conclusion(state: dict, ctx: RunContext) -> dict:
    o = state.get("outline") or {}
    chapters = "\n".join(f"- {chapter_name(state, s)}: {(state.get(EMPLOYEES[s]['key']) or {}).get('conclusion', '')}"
                         for s in ("chapter1", "literature", "theory", "practical") if s in state.get("stages", []))
    ctx.progress("Writing the General Conclusion tied to the Three Nails", stage="conclusion")
    words = 230 if is_paper(state) else 400
    return _llm(ctx).json(system_prompt(state, "conclusion"), prompt(
        "conclusion_core", nails="\n".join(f"NAIL{i + 1}: {n}" for i, n in enumerate(o.get("nails", []))),
        goal=o.get("goal", ""), tasks="\n".join(f"- {t}" for t in o.get("tasks", [])), chapters=chapters,
        results=results_text(state), feedback=feedback_text(state), words=words,
        abstract_words=min(380, rules()["science_week"]["abstract_max_words"] - 20) if is_paper(state) else 250),
        CONCLUSION_SCHEMA, task="conclusion_core")


# ── Employee 8 ────────────────────────────────────────────────────────────
def document_texts(state: dict) -> list[str]:
    return [flatten_text(state.get(k)) for k in ("chapter1", "literature", "theory", "practical", "conclusion")]


def employee_references(state: dict, ctx: RunContext) -> dict:
    style = _p(state).get("citation_style", "apa")
    ctx.progress(f"Compiling the bibliography ({style.upper()})", stage="references")
    entries = bibliography([r for r in state.get("references", []) if r.get("included", True)], style,
                           document_texts(state))
    return {"style": style, "entries": [{"key": e["key"], "number": e["number"], "text": e["text"]} for e in entries],
            "cited_count": len(entries)}


EMPLOYEE_FUNCS = {
    "architect": employee_architect,
    "chapter1": employee_chapter1,
    "literature": employee_literature,
    "theory": employee_theory,
    "practical": employee_practical,
    "conclusion": employee_conclusion,
    "references": employee_references,
}
