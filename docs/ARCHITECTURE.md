# Architecture

## Layers

```
┌──────────────────────────── Web portal (static/, ES modules, no build) ─────────────────────────────┐
│ Projects · Pipeline (stepper, editors, PM audit, live log) · Facts · References · Implementation &  │
│ data · Science Week form · Export & reports · History            UI: uz / en / ru / lv              │
└──────────────────────────────────────────────┬──────────────────────────────────────────────────────┘
                                               │ JSON over HTTP (app/web.py, Starlette + uvicorn)
┌──────────────────────────────────────────────▼──────────────────────────────────────────────────────┐
│ Service layer (app/services.py): projects, background jobs, patches, references, experiments,       │
│ implementation evidence, exports                                                                    │
├──────────────────────────────┬───────────────────────────────┬──────────────────────────────────────┤
│ Orchestrator                 │ Validators (Employee 1)        │ Grounding sources                    │
│ engine.py  state graph,      │ rules.py   RNU matrix          │ references/  OpenAlex, S2, Crossref, │
│            SQLite checkpoints│ text.py    sentences, stats,   │              BibTeX, APA / IEEE      │
│            interrupt/resume  │            key-term overlap    │ experiments/ Welch, Mann–Whitney,    │
│ graph.py   8 employees,      │ messages.py 4 UI languages     │              Cohen d, CI, chart      │
│            PM gate, review   │ rnu_rules.yaml (editable)      │ implementation evidence (code files) │
│ employees.py + prompts/*.md  │                                │                                      │
├──────────────────────────────┴───────────────────────────────┴──────────────────────────────────────┤
│ LLM providers (app/llm): Ollama · OpenAI-compatible (LM Studio, llama.cpp, vLLM, Jan) · demo        │
├─────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ SQLite (data/copilot.sqlite3): projects · events (activity log) · checkpoints (full state per step) │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Workflow graph

```
 [stage node: Employee 2…8] ──► [pm_gate: Employee 1] ──blocking & retries left──► back to stage (auto-fix)
                                         │
                                         └──otherwise──► [human_review: interrupt]
                                                              │ approve → validate again → next stage / END
                                                              │ revise  → stage (whole stage or one subsection)
                                                              └ rerun   → any earlier stage
```

* **Interrupt / resume** — `ctx.interrupt(payload)` raises inside `human_review`; the engine stores the pre-node state
  with `pending=payload`. On resume the node re-runs and `interrupt` returns the student's decision (same semantics
  as `langgraph.types.interrupt`; see `langgraph_adapter.py`).
* **Edits while paused** — `Runner.update_state` merges a patch into the latest checkpoint without touching the
  pending interrupt, so the student can edit any section, facts, references or data before deciding.
* **Approval gate** — `approve` re-runs the validators; blocking findings keep the graph in `human_review`.
* **Auto-revision** — only for issues the model can fix itself; missing human data (facts, evidence, measurements,
  unverified sources, placeholders) always goes to the student.

## Anti-fabrication design

| Risk | Mechanism |
|---|---|
| invented statistics | facts table with sources; prompts allow only `(F#)` facts; `[STAT NEEDED]` placeholders block |
| hallucinated references | sources only from APIs/BibTeX; Crossref verification; unknown/unverified/excluded keys block |
| invented results | every number in the results discussion must occur in the analysis of the uploaded CSV; sample data blocks |
| "mockup-only" Chapter 3 | local folder must contain source code files; run/deploy steps required; URL check |
| drifting thesis statements | key terms of each Nail must reappear in the general conclusion (stem overlap ≥ 50 %) |
| fake progress | the bi-weekly e-mail is rendered from the event log only |
| undisclosed AI use | AI draft vs final text diff per stage → appendix A of the DOCX |

## Long chapters with local models

Chapters are generated *outline → subsections → conclusion*. The number of subsections is derived from the page target in
`rnu_rules.yaml` (words per page × pages), so 8k–16k-token models can still reach 20–50 pages. A revision can target a
single subsection.
