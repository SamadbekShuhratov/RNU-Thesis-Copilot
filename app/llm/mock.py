"""Deterministic demo model.

Lets you explore the whole portal (and run the test-suite) without a local
LLM. It only re-uses material that is present in the prompt (facts,
reference keys, measured numbers), exactly like a well-behaved model should.
Output is English and clearly marked as demo text.
"""
from __future__ import annotations

import json
import re

from .base import LLM

DEMO = "[demo] "


class MockLLM(LLM):
    provider = "mock"

    def list_models(self) -> list[str]:
        return ["mock-demo"]

    def health(self) -> dict:
        return {"ok": True, "provider": self.provider, "models": ["mock-demo"], "model_available": True}

    # ── helpers to read the prompt ─────────────────────────────────────────
    @staticmethod
    def _user(messages) -> str:
        return "\n".join(m["content"] for m in messages if m["role"] == "user")

    @staticmethod
    def _ref_keys(text: str) -> list[str]:
        return re.findall(r"^- ([\w:\-\.]+) — ", text, flags=re.MULTILINE)

    @staticmethod
    def _facts(text: str) -> list[tuple[str, str]]:
        return re.findall(r"^FACT (\S+): (.+?) — source:", text, flags=re.MULTILINE)

    @staticmethod
    def _nails(text: str) -> list[str]:
        return [n for _, n in re.findall(r"^NAIL(\d): (.+)$", text, flags=re.MULTILINE)]

    @staticmethod
    def _field(text: str, label: str, default: str = "") -> str:
        m = re.search(rf"^-?\s*{re.escape(label)}:\s*(.+)$", text, flags=re.MULTILINE)
        return m.group(1).strip() if m and m.group(1).strip() else default

    def _chat(self, messages, *, json_schema, temperature, task) -> str:
        user = self._user(messages)
        base = task.split("#")[0]
        topic = self._field(user, "Topic / idea", "a local AI assistant for academic compliance")
        refs = self._ref_keys(user)
        cite = f" [@{refs[0]}]" if refs else ""
        cite2 = f" [@{refs[1]}]" if len(refs) > 1 else cite

        if base == "architect":
            obj_ = self._field(user, "Research object hint (enterprise / system)", "the university thesis workflow")
            subj = self._field(user, "Research subject hint (specific technical aspect)", "automated compliance validation")
            titles = [f"{subj.capitalize()} for {obj_}: a multi-agent approach",
                      f"Design of a local LLM assistant for {obj_}",
                      f"Improving {subj} in {obj_} with human-in-the-loop agents",
                      f"A verifiable reference pipeline for {obj_}",
                      f"Empirical evaluation of {subj} at {obj_}",
                      f"{topic.capitalize()}: architecture and evaluation"]
            data = {
                "titles": titles, "selected_title": titles[0], "object": obj_, "subject": subj,
                "goal": f"To develop and deploy a local multi-agent assistant for {obj_} that reduces "
                        f"RNU formatting and compliance errors by 40% within one semester.",
                "tasks": ["Analyse the current thesis compliance problems with statistics",
                          "Review existing methods for automated academic writing support",
                          "Select the theoretical and engineering frameworks for the design",
                          "Implement the multi-agent system with verified reference retrieval",
                          "Evaluate the system empirically against the manual baseline"],
                "nails": [f"Has been OFFERED a multi-agent compliance architecture for {subj} in {obj_}.",
                          "Has been MODIFIED the retrieval-augmented generation pipeline with independent "
                          "Crossref verification of every reference.",
                          "Has been SUGGESTED an implementation guideline for human-in-the-loop approval "
                          "of AI-assisted academic drafts."],
                "keywords": ["multi-agent systems", "large language models", "academic compliance",
                             "retrieval-augmented generation", "human-in-the-loop"],
                "rationale": DEMO + "The plan moves from the measured problem to existing methods and to the "
                                    "student's own practical method.",
            }
        elif base == "chapter1_core":
            facts = self._facts(user)
            if len(facts) >= 2:
                f1, f2 = facts[0], facts[1]
                topical = (f"{DEMO}{f1[1]} ({f1[0]}). {f2[1]} ({f2[0]}). "
                           "Therefore the efficiency of thesis preparation has a direct effect on graduation rates.")
                problem = (f"{f1[1]} ({f1[0]}). Manual checking of formatting rules takes supervisors "
                           f"considerable time, as reflected by the data in ({f2[0]}). "
                           "The problem is the absence of an automated, verifiable compliance check.")
            else:
                topical = "[STAT NEEDED: share of theses returned for formatting errors]. [STAT NEEDED: supervisor hours]. Third sentence."
                problem = "[STAT NEEDED: error rate]. Second sentence. Third sentence."
            data = {
                "topicality": topical, "problem_formulation": problem,
                "research_questions": ["Which compliance errors are most frequent?",
                                       "Can a local multi-agent system detect them reliably?"],
                "methods": DEMO + "Literature analysis, system design, implementation, controlled experiment "
                                  "and statistical testing are used.",
                "planned_results": [
                    {"result": "A working multi-agent compliance assistant", "metric": "compliance errors reduced by 40%",
                     "beneficiary": "RNU students preparing theses"},
                    {"result": "A verified reference pipeline", "metric": "0 hallucinated references in 100 checks",
                     "beneficiary": "RNU supervisors reviewing theses"}],
                "novelty": DEMO + "The work combines local language models with deterministic rule validation.",
                "structure": DEMO + "The work consists of an introduction, three chapters and a general conclusion.",
            }
        elif base.endswith("_plan"):
            m = re.search(r'a list of (\d+) objects', user)
            n = int(m.group(1)) if m else 2
            data = {"sections": [{"heading": f"Demo subsection {i + 1}", "focus": "Key aspects of the topic."}
                                 for i in range(n)]}
        elif base == "search_queries":
            data = {"queries": ["multi-agent LLM academic writing", "automated thesis compliance checking",
                                "retrieval augmented generation citation verification"]}
        elif base == "literature_core":
            data = {
                "comparison": [
                    {"approach": "Rule-based writing checkers", "sources": cite.strip() or "—",
                     "strengths": "Deterministic and transparent", "limitations": "Cannot judge content"},
                    {"approach": "Generic LLM writing assistants", "sources": cite2.strip() or "—",
                     "strengths": "Fluent drafts", "limitations": "Hallucinated references"}],
                "gaps": ["No existing tool combines institutional rule validation with verified references",
                         "Existing assistants do not keep the student in control of approvals"],
                "conclusion": f"{DEMO}Existing work addresses parts of the problem{cite}. "
                              "However, no solution combines rule validation, verified sources and human approval. "
                              "These gaps define the requirements for the proposed system.",
            }
        elif base == "theory_core":
            data = {
                "concepts": [{"term": "Multi-agent system", "definition": f"A set of cooperating agents{cite}."},
                             {"term": "Retrieval-augmented generation", "definition": f"Generation grounded in retrieved sources{cite2}."}],
                "frameworks": [{"name": "Design Science Research", "description": "Build-and-evaluate methodology.",
                                "how_used": "Structures the design and the empirical evaluation."}],
                "gap_to_solution": [
                    {"gap": "No combination of rule validation and verified references",
                     "solution_element": "Employee 1 gate plus Crossref verification"},
                    {"gap": "Students are not in control of approvals",
                     "solution_element": "Human-in-the-loop interrupt before every stage"}],
            }
        elif base == "practical_core":
            metrics = re.findall(r"METRIC (\S+) \((\w+) is better\): (\S+) mean=([\-\d.]+).*?; (\S+) mean=([\-\d.]+).*?change=([\-\d.]+)%",
                                 user)
            if metrics:
                parts = [f"For {m[0]} the {m[2]} mean was {m[3]} and the {m[4]} mean was {m[5]}, a change of {m[6]}%."
                         for m in metrics]
                discussion = DEMO + " ".join(parts) + " The differences were tested with Welch's t-test."
            else:
                discussion = "[DATA NEEDED: upload measurements]"
            data = {
                "architecture": DEMO + "The system consists of a web portal, an orchestration engine, eight agents, "
                                       "a validator layer and a SQLite store.",
                "components": [{"name": "Orchestrator", "responsibility": "Runs the stage graph", "technology": "Python"},
                               {"name": "Validators", "responsibility": "RNU rule checks", "technology": "Python"},
                               {"name": "Portal", "responsibility": "Human review", "technology": "HTML/JS"}],
                "data_flow": DEMO + "Drafts flow from agents to the PM gate and then to the student.",
                "deployment_steps": ["Install Python 3.11+", "pip install -r requirements.txt",
                                     "Start Ollama and pull a model", "python -m app"],
                "experiment_design": DEMO + "Baseline and proposed variants are compared with Welch's t-test "
                                            "(alpha 0.05).",
                "results_discussion": discussion,
            }
        elif base == "conclusion_core":
            nails = self._nails(user)
            body = " ".join(f"The work confirmed that {n.rstrip('.')}." for n in nails)
            filler = (" The research aim was achieved because every task was completed and the measured "
                      "results were analysed statistically. The literature review showed the gaps, the theoretical "
                      "chapter mapped them to the design, and the practical chapter proved that the system works. ") * 4
            data = {
                "general_conclusion": DEMO + body + filler,
                "nail_evidence": [{"nail": n, "evidence": "Chapter 3 experiment"} for n in nails],
                "limitations": DEMO + "The evaluation used a limited number of runs.",
                "future_work": DEMO + "Future work will extend the evaluation to more faculties.",
                "abstract": DEMO + "This paper presents a local multi-agent assistant for RNU academic compliance. "
                                   "The system validates drafts against institutional rules and verifies every "
                                   "reference. An experiment compared the proposed system with a manual baseline. "
                                   "The results support the defended thesis statements.",
            }
        elif base.startswith("judge"):
            data = {"pass": True, "note": "OK"}
        elif base.endswith("_section"):
            return (f"{DEMO}This subsection discusses the topic in the context of the research plan{cite}. "
                    f"It relates the reviewed material to the object and subject of the work{cite2}. "
                    "The discussion prepares the next step of the argument.")
        elif base.endswith("_conclusion"):
            return (f"{DEMO}This chapter summarised the main findings for its part of the work. "
                    "It established the basis for the next chapter of the 3-Arrow Logic. "
                    "The results are used directly in the following stage.")
        else:
            data = {}
        if json_schema is None:
            return json.dumps(data, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)
