"""The RNU 8-employee workflow graph.

    ┌──────────────┐   draft   ┌───────────────┐  ok / retries used  ┌──────────────┐
    │ Employee N   │ ────────▶ │ Employee 1:   │ ──────────────────▶ │ human_review │
    │ (stage node) │ ◀──────── │ PM gate       │                     │  (interrupt) │
    └──────────────┘  auto-fix └───────────────┘                     └──────┬───────┘
          ▲  revise / rerun                                                 │ approve
          └─────────────────────────────────────────────────────────────────┘ → next stage

Employee 1 audits every draft against the RNU Output Constraints Matrix.
Blocking findings trigger an automatic revision (bounded by
``max_auto_revisions``); after that the student decides. A stage can only be
approved when no blocking finding remains.
"""
from __future__ import annotations

import copy
from typing import Any

from ..llm.base import LLMError, S, obj
from ..reports.progress import compliance_summary
from ..validators import blocking, render, validate_stage
from ..validators.rules import estimate_pages
from .employees import EMPLOYEE_FUNCS, prompt, system_prompt
from .engine import END, RunContext, StateGraph
from .state import EMPLOYEES, next_stage, stage_key


# ── stage (agent) nodes ───────────────────────────────────────────────────
def make_agent_node(stage: str):
    def node(state: dict, ctx: RunContext) -> dict:
        ctx.progress(f"Employee {EMPLOYEES[stage]['no']} started", stage=stage, kind="stage_start")
        out = EMPLOYEE_FUNCS[stage](state, ctx)
        extra = out.pop("_update", {}) if isinstance(out, dict) else {}
        drafts = dict(state.get("ai_drafts", {}))
        drafts[stage] = copy.deepcopy(out)
        status = dict(state.get("stage_status", {}))
        status[stage] = "draft"
        ctx.progress(f"Employee {EMPLOYEES[stage]['no']} finished the draft", stage=stage, kind="stage_draft")
        return {**extra, stage_key(stage): out, "ai_drafts": drafts, "stage_status": status, "stage": stage,
                "attempts": int(state.get("attempts", 0)) + 1, "_route": "pm_gate", "revise_scope": {},
                "notice": ""}
    node.__name__ = f"employee_{stage}"
    return node


# ── Employee 1: PM gate ───────────────────────────────────────────────────
JUDGE_SCHEMA = obj({"pass": {"type": "boolean"}, "note": S}, required=["note"])


def llm_judge(state: dict, ctx: RunContext) -> list[dict]:
    """Optional qualitative review by the local model (warnings only)."""
    stage = state["stage"]
    settings = ctx.services.get("settings", {})
    if not settings.get("llm_judge") or stage not in ("architect", "chapter1"):
        return []
    items = []
    if stage == "architect":
        items.append(("JUDGE_GOAL", "Research aim", (state.get("outline") or {}).get("goal", ""),
                      "exactly one sentence; Specific, Measurable, Achievable, Relevant, Time-bound; not vague"))
    else:
        items.append(("JUDGE_PROBLEM", "Problem formulation", (state.get("chapter1") or {}).get("problem_formulation", ""),
                      "3–4 sentences, based on facts and statistics, not an opinion-based lecture"))
    findings = []
    for code, what, text, criteria in items:
        if not text.strip():
            continue
        try:
            res = ctx.services["llm"].json(system_prompt(state, "final"),
                                           prompt("judge", what=what, text=text, criteria=criteria),
                                           JUDGE_SCHEMA, task=f"judge_{stage}", temperature=0.0)
        except LLMError:
            continue
        if res.get("pass") is False:
            findings.append({"code": code, "severity": "warn", "stage": stage, "field": "", "params": {"note": res.get("note", "")}})
    return findings


def pm_gate(state: dict, ctx: RunContext) -> dict:
    stage = state["stage"]
    findings = validate_stage(stage, state)
    blocks = blocking(findings)
    max_auto = int(ctx.services.get("settings", {}).get("max_auto_revisions", 1))
    ctx.progress(f"PM audit: {len(blocks)} blocking, {len(findings) - len(blocks)} warnings", stage=stage,
                 kind="gate", blocking=len(blocks))
    if blocks and int(state.get("attempts", 0)) <= max_auto and stage not in ("references", "final"):
        # Only auto-fix issues the model can fix itself (not missing human data).
        human_data_codes = {"FACT_UNSOURCED", "FACTS_NONE", "REFS_NONE", "IMPL_EVIDENCE_MISSING", "IMPL_PATH_NOT_FOUND",
                            "IMPL_NO_CODE", "IMPL_RUN_MISSING", "EXPERIMENTS_MISSING", "CITATION_UNVERIFIED",
                            "CITATION_EXCLUDED", "EXPERIMENT_SAMPLE_DATA"}
        fixable = [f for f in blocks if f["code"] not in human_data_codes]
        if fixable and not any(f["code"] == "PLACEHOLDER" for f in blocks):
            feedback = "\n".join(f"- [{f['code']}] {render(f, 'en')}" for f in fixable)
            ctx.progress("PM requests an automatic revision", stage=stage, kind="auto_revise")
            return {"findings": findings, "feedback": feedback, "_route": stage}
    findings += llm_judge(state, ctx)
    return {"findings": findings, "_route": "human_review"}


# ── Employee 1: final compliance node ─────────────────────────────────────
def pm_final(state: dict, ctx: RunContext) -> dict:
    ctx.progress("Employee 1 compiles the final compliance report", stage="final", kind="stage_start")
    status = dict(state.get("stage_status", {}))
    status["final"] = "draft"
    compliance = dict(state.get("compliance") or {})
    compliance.update(compliance_summary(state))
    compliance["page_estimate"] = estimate_pages(state)
    return {"compliance": compliance, "stage": "final", "stage_status": status, "attempts": 1,
            "_route": "pm_gate", "notice": ""}


# ── human review (interrupt) ──────────────────────────────────────────────
def human_review(state: dict, ctx: RunContext) -> dict:
    stage = state["stage"]
    decision = ctx.interrupt({"stage": stage, "findings": state.get("findings", [])}) or {}
    action = decision.get("action", "approve")
    if action == "approve":
        findings = validate_stage(stage, state)
        blocks = blocking(findings)
        if blocks:
            ctx.progress("Approval refused: blocking findings remain", stage=stage, kind="blocked")
            return {"findings": findings, "_route": "human_review", "notice": "approval_blocked"}
        status = dict(state.get("stage_status", {}))
        status[stage] = "approved"
        nxt = next_stage(state, stage)
        ctx.progress("Stage approved by the student", stage=stage, kind="approved")
        if nxt is None:
            return {"stage_status": status, "findings": findings, "stage": "done", "_route": END, "notice": ""}
        return {"stage_status": status, "findings": [], "stage": nxt, "attempts": 0, "feedback": "",
                "_route": "pm_final" if nxt == "final" else nxt, "notice": ""}
    if action == "revise":
        ctx.progress("Student requested a revision", stage=stage, kind="revise",
                     feedback=decision.get("feedback", ""))
        scope = {k: decision[k] for k in ("section", "refresh_refs") if decision.get(k) is not None}
        return {"feedback": decision.get("feedback", ""), "attempts": 0, "revise_scope": scope,
                "_route": "pm_final" if stage == "final" else stage}
    if action == "rerun":
        target = decision.get("target") or stage
        if target not in state["stages"]:
            raise ValueError(f"unknown stage {target}")
        status = dict(state.get("stage_status", {}))
        idx = state["stages"].index(target)
        for s in state["stages"][idx:]:
            status[s] = "pending" if s != target else status.get(s, "pending")
        ctx.progress(f"Student re-runs stage {target}", stage=target, kind="rerun")
        return {"stage": target, "stage_status": status, "attempts": 0, "feedback": decision.get("feedback", ""),
                "revise_scope": {}, "findings": [], "_route": "pm_final" if target == "final" else target}
    raise ValueError(f"unknown action {action}")


def route(state: dict) -> str:
    return state.get("_route") or END


def build_graph(stages: list[str]) -> StateGraph:
    g = StateGraph()
    for s in stages:
        if s == "final":
            g.add_node("pm_final", pm_final)
            g.add_conditional_edges("pm_final", route)
        else:
            g.add_node(s, make_agent_node(s))
            g.add_conditional_edges(s, route)
    g.add_node("pm_gate", pm_gate)
    g.add_conditional_edges("pm_gate", route)
    g.add_node("human_review", human_review)
    g.add_conditional_edges("human_review", route)
    g.set_entry_point(stages[0])
    return g


ALL_STAGES = ["architect", "chapter1", "literature", "theory", "practical", "conclusion", "references", "final"]
