"""Shape of the shared thesis state held by Employee 1 (the "state holder")."""
from __future__ import annotations

import copy
import datetime as dt
from typing import Any

from ..rules import stages_for, rules

EMPLOYEES: dict[str, dict[str, Any]] = {
    "architect":  {"no": 2, "role": "Outline & Three Nails Architect", "key": "outline"},
    "chapter1":   {"no": 3, "role": "Chapter 1 Specialist — Introduction & Problem Formulation", "key": "chapter1"},
    "literature": {"no": 4, "role": "Literature Review Specialist", "key": "literature"},
    "theory":     {"no": 5, "role": "Theoretical Framework Specialist", "key": "theory"},
    "practical":  {"no": 6, "role": "Practical Implementation & Empirical Analysis Specialist", "key": "practical"},
    "conclusion": {"no": 7, "role": "General Conclusion Editor", "key": "conclusion"},
    "references": {"no": 8, "role": "Formatting & Reference Editor", "key": "bibliography"},
    "final":      {"no": 1, "role": "Project Manager — RNU Compliance Gatekeeper", "key": "compliance"},
}

STATE_KEYS = {e["key"] for e in EMPLOYEES.values()}

# Top-level keys a human may patch from the portal.
EDITABLE_KEYS = {
    "project", "facts", "references", "implementation", "experiments", "submission",
    "outline", "chapter1", "literature", "theory", "practical", "conclusion", "bibliography",
}


def stage_key(stage: str) -> str:
    return EMPLOYEES[stage]["key"]


def initial_state(project_id: str, name: str, doc_type: str, language: str,
                  setup: dict[str, Any] | None = None) -> dict[str, Any]:
    setup = setup or {}
    stages = stages_for(doc_type)
    project = {
        "id": project_id,
        "name": name,
        "doc_type": doc_type,
        "language": language,
        "citation_style": setup.get("citation_style") or rules()["formatting"]["default_citation_style"],
        "topic": setup.get("topic", ""),
        "object_hint": setup.get("object_hint", ""),
        "subject_hint": setup.get("subject_hint", ""),
        "field": setup.get("field", ""),
        "notes": setup.get("notes", ""),
        "student_name": setup.get("student_name", ""),
        "student_email": setup.get("student_email", ""),
        "student_group": setup.get("student_group", ""),
        "supervisor": setup.get("supervisor", ""),
        "supervisor_email": setup.get("supervisor_email", ""),
        "university": setup.get("university", "Riga Nordic University"),
        "faculty": setup.get("faculty", ""),
        "programme": setup.get("programme", ""),
        "city": setup.get("city", "Riga"),
        "year": setup.get("year") or str(dt.date.today().year),
    }
    authors = setup.get("authors") or []
    if not authors and project["student_name"]:
        first, _, last = project["student_name"].partition(" ")
        authors = [{"first_name": first, "surname": last, "affiliation": project["university"],
                    "email": project["student_email"], "corresponding": True}]
    state: dict[str, Any] = {
        "project": project,
        "facts": copy.deepcopy(setup.get("facts") or []),
        "references": [],
        "implementation": {
            "repo_url": "", "local_path": "", "stack": "", "run_command": "", "deploy_steps": "",
            "deployed_url": "", "description": "", "evidence": {},
        },
        "experiments": {"rows": [], "config": {}, "analysis": None, "source_name": ""},
        "submission": {
            "authors": authors,
            "technical_section": setup.get("technical_section", ""),
            "keywords": "",
            "presentation_type": setup.get("presentation_type", "In person"),
            "notes": "",
        },
        "stage": stages[0],
        "stages": stages,
        "stage_status": {s: "pending" for s in stages},
        "attempts": 0,
        "findings": [],
        "feedback": "",
        "notice": "",
        "ai_drafts": {},
        "_route": None,
    }
    for s in stages:
        state.setdefault(stage_key(s), {})
    return state


def next_stage(state: dict[str, Any], stage: str) -> str | None:
    stages = state["stages"]
    idx = stages.index(stage)
    return stages[idx + 1] if idx + 1 < len(stages) else None
