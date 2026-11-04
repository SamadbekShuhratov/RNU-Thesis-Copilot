"""RNU Science Week submission sheet — mirrors the online form (sections 01–05)
so every field can be copied into the portal exactly."""
from __future__ import annotations

from typing import Any

from ..rules import rules
from ..validators.rules import check_submission
from ..validators.text import word_count


def submission_sheet(state: dict[str, Any]) -> dict[str, Any]:
    o = state.get("outline") or {}
    sub = state.get("submission") or {}
    con = state.get("conclusion") or {}
    cfg = rules()["science_week"]
    abstract = con.get("abstract", "")
    return {
        "01_authors": [{"first_name": a.get("first_name", ""), "surname": a.get("surname", ""),
                        "affiliation": a.get("affiliation", ""), "email": a.get("email", ""),
                        "corresponding_author_presenter": bool(a.get("corresponding"))}
                       for a in sub.get("authors", [])],
        "02_paper_details": {"paper_title": o.get("selected_title", ""), "abstract": abstract,
                             "abstract_words": word_count(abstract), "abstract_limit": cfg["abstract_max_words"]},
        "03_technical_section_and_keywords": {"technical_section": sub.get("technical_section", ""),
                                              "keywords": sub.get("keywords") or "; ".join(o.get("keywords", []))},
        "04_paper_file": {"format": "DOCX", "pages_required": cfg["pages"], "max_mb": cfg["max_file_mb"],
                          "template": cfg["template_url"],
                          "page_count": (state.get("compliance") or {}).get("page_count_exact"),
                          "page_estimate": (state.get("compliance") or {}).get("page_estimate")},
        "05_additional_information": {"presentation_type": sub.get("presentation_type", ""),
                                      "notes": sub.get("notes", "")},
        "checks": check_submission(state, "final"),
    }


def submission_markdown(sheet: dict[str, Any]) -> str:
    lines = ["# RNU Science Week 2027 — submission sheet", "", "## 01 Authors", "",
             "| # | First name | Surname | Affiliation | Email | Corresponding / presenter |",
             "|---|---|---|---|---|---|"]
    for i, a in enumerate(sheet["01_authors"], start=1):
        lines.append(f"| {i} | {a['first_name']} | {a['surname']} | {a['affiliation']} | {a['email']} | "
                     f"{'✔' if a['corresponding_author_presenter'] else ''} |")
    d = sheet["02_paper_details"]
    lines += ["", "## 02 Paper details", "", f"**Paper title:** {d['paper_title']}", "",
              f"**Abstract** ({d['abstract_words']} / {d['abstract_limit']} words):", "", d["abstract"], "",
              "## 03 Technical section and keywords", "",
              f"**Technical section:** {sheet['03_technical_section_and_keywords']['technical_section']}", "",
              f"**Keywords:** {sheet['03_technical_section_and_keywords']['keywords']}", "",
              "## 04 Paper file", "",
              f"DOCX, {sheet['04_paper_file']['pages_required'][0]}–{sheet['04_paper_file']['pages_required'][1]} "
              f"A4 pages, ≤ {sheet['04_paper_file']['max_mb']} MB. Pages: "
              f"{sheet['04_paper_file']['page_count'] or '≈' + str(sheet['04_paper_file']['page_estimate'])}", "",
              "## 05 Additional information", "",
              f"**Presentation type:** {sheet['05_additional_information']['presentation_type']}", "",
              f"**Notes:** {sheet['05_additional_information']['notes']}", ""]
    if sheet["checks"]:
        lines += ["## Open issues", ""] + [f"- {c['code']}" for c in sheet["checks"]]
    return "\n".join(lines)
