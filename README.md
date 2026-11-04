# RNU Thesis Copilot

A local, human-in-the-loop, multi-agent writing assistant for **Riga Nordic University (RNU)** students.
It guides course works, bachelor/master theses and **RNU Science Week 2027** conference papers through a
staged workflow that enforces RNU's institutional rules at every step.

> **A co-pilot, not a ghostwriter.** Agents draft and audit; the student edits and approves every stage.
> Statistics, references and measurements must be real: the system **blocks** fabricated figures and unverified
> citations, and discloses in an appendix how much of each AI draft the student changed.

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![LLM](https://img.shields.io/badge/LLM-local%20(Ollama%20%7C%20OpenAI--compatible)-green)
![Tests](https://img.shields.io/badge/tests-pytest-informational)

---

## Table of Contents

- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Running with Docker](#running-with-docker)
- [Configuration](#configuration)
- [User Workflow](#user-workflow)
- [Agent Architecture](#agent-architecture)
- [Supported Document Types](#supported-document-types)
- [Anti-Fabrication Safeguards](#anti-fabrication-safeguards)
- [RNU Rules](#rnu-rules)
- [Measurement Data Format](#measurement-data-format)
- [HTTP API](#http-api)
- [LangGraph Runtime](#langgraph-runtime)
- [Testing and Benchmarks](#testing-and-benchmarks)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Academic Integrity](#academic-integrity)

---

## Key Features

| Feature | Description |
|---|---|
| **Eight-agent workflow** | Architect (title, object/subject, SMART aim, three thesis statements) → Chapter 1 → literature review → theoretical framework → practical implementation and experiments → general conclusion → bibliography → final compliance audit |
| **Compliance gatekeeper** | Employee 1 (Project Manager) audits every draft against the RNU *Output Constraints Matrix*, requests automatic revisions where possible, and blocks approval while any rule is violated |
| **Fully local LLM** | Ollama or any OpenAI-compatible server (LM Studio, llama.cpp, vLLM, Jan). No text leaves the machine. A built-in demo model allows evaluation without an LLM |
| **Verified references** | Retrieval from OpenAlex and Semantic Scholar, independent verification via Crossref (DOI + title match), BibTeX import. Agents may cite only verified `[@key]` entries |
| **Real experimental evidence** | Measurement CSV → Welch's t-test, Mann–Whitney U, Cohen's d, 95% confidence intervals and charts. Every number in Chapter 3 must originate from the measurements |
| **Proof of working code** | Source files and tests in the project folder are counted and deployment URLs are checked; mock-up-only implementations are rejected |
| **Science Week submission** | Authors (≤ 10, one corresponding), title, abstract (≤ 400 words), technical track, keywords (3–8), official DOCX template, 4–6 pages (exact page count via LibreOffice) |
| **Export** | Thesis / course work DOCX (title page, table of contents, tables, figures, APA/IEEE, AI-use appendix), paper DOCX, submission sheet, compliance report, JSON backup |
| **Bi-weekly progress report** | Supervisor e-mail generated strictly from the real activity log, in Uzbek, English, Russian or Latvian |
| **Multilingual** | UI: Uzbek, English, Russian, Latvian. Writing languages: 15 (en, lv, ru, uz, uk, lt, et, pl, de, fr, es, it, pt, tr, kk) |
| **Full history** | Every step is stored as a checkpoint; any earlier state can be restored |

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** (<https://ollama.com>) or another OpenAI-compatible local inference server
- *(optional)* **LibreOffice** — for exact page counting of Science Week papers

### 1. Pull a model

```bash
ollama pull qwen2.5:14b-instruct     # recommended for ~16 GB RAM
# on more powerful hardware: ollama pull qwen2.5:32b-instruct
```

### 2. Launch

| Platform | Command |
|---|---|
| Windows | Double-click `start.bat` |
| macOS / Linux | `./start.sh` |

On first launch the script creates a `.venv` virtual environment and installs `requirements.txt`.
The portal then opens automatically at **<http://localhost:8765>**.

To evaluate the system without an LLM, use the built-in demo model:

```bash
./start.sh --demo        # Windows: start.bat --demo
```

### Manual installation

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app [--host 127.0.0.1] [--port 8765] [--demo] [--no-browser]
```

## Running with Docker

The provided `docker-compose.yml` starts both Ollama and the portal:

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:14b-instruct
```

The portal is available at <http://localhost:8765> (bound to `127.0.0.1` only). Application data is persisted in the
`copilot-data` volume, mounted at `/data`.

- **NVIDIA GPU:** uncomment the `deploy:` line in `docker-compose.yml`.
- **Smaller image:** LibreOffice (~400 MB) is included by default; build without it using
  `docker compose build --build-arg WITH_LIBREOFFICE=0`.

## Configuration

Environment variables provide the defaults for the first launch (see `.env.example`). After that, values saved in
the portal under **Settings** (`data/settings.json`) take precedence and apply without a server restart.

| Variable | Default | Description |
|---|---|---|
| `RNU_HOST` | `127.0.0.1` | Bind address |
| `RNU_PORT` | `8765` | HTTP port |
| `RNU_LLM_PROVIDER` | `ollama` | `ollama` \| `openai_compatible` \| `mock` |
| `RNU_LLM_BASE_URL` | `http://localhost:11434` | LLM server URL (for LM Studio: `http://localhost:1234`; `/v1` is appended automatically) |
| `RNU_LLM_MODEL` | `qwen2.5:14b-instruct` | Model identifier |
| `RNU_LLM_API_KEY` | — | API key, if required by the OpenAI-compatible server |
| `RNU_OPENALEX_MAILTO` | — | Contact e-mail for the OpenAlex "polite pool" (optional) |
| `RNU_DATA_DIR` | `./data` | Location of the SQLite database, uploads and exports |

Additional runtime settings available in the portal: temperature (`0.4`), context window (`16384`), request timeout
(`600 s`), JSON retries, maximum automatic revisions per stage, optional LLM judge, references per search query and
earliest publication year (`2015`).

## User Workflow

1. **New project** — choose the document type (course work, thesis or Science Week paper), writing language, topic, and student/supervisor details.
2. **Project & facts** — enter real statistics with their sources (F1, F2, …). Chapter 1 may use only these facts.
3. **Pipeline** — run the next agent, edit the draft, then *Approve* or *Request revision* (for the whole stage or a single subsection).
4. **References** — Employee 4 retrieves candidates from OpenAlex; references can also be added manually, by DOI or via BibTeX. Exclude irrelevant entries.
5. **Implementation & data** — provide the project folder or repository, run command, deployment URL and the measurement CSV.
6. **Science Week form** *(papers only)* — authors, technical track, keywords, official template upload and page measurement.
7. **Export & reports** — DOCX, submission sheet, compliance report, bi-weekly e-mail and JSON backup.
8. **History** — roll back to any previous checkpoint.

## Agent Architecture

| # | Agent | Responsibility |
|---|---|---|
| 2 | Outline & Three Nails Architect | Title, research object and subject, one-sentence SMART aim, objectives, three thesis statements |
| 3 | Chapter 1 Specialist | Introduction, topicality (3–4 fact-backed sentences), problem formulation |
| 4 | Literature Review Specialist | Literature review based solely on verified sources |
| 5 | Theoretical Framework Specialist | Theoretical foundation |
| 6 | Practical Implementation & Empirical Analysis Specialist | Implementation, code evidence, experimental results |
| 7 | General Conclusion Editor | General conclusion preserving the key terms of each thesis statement |
| 8 | Formatting & Reference Editor | Bibliography (APA / IEEE) |
| 1 | Project Manager — RNU Compliance Gatekeeper | Audit after every stage and final compliance check |

```
 [Agent N] ──draft──► [Employee 1: PM gate] ──blocking issues & retries left──► [Agent N] (auto-revision)
                               │
                               └──otherwise──► [human_review: interrupt]
                                                 ├ approve  → re-validate → next stage / END
                                                 ├ revise   → whole stage or a single subsection
                                                 └ rerun    → any earlier stage
```

Automatic revision is attempted only for issues the model can resolve on its own. Missing human input — facts,
implementation evidence, measurements, unverified sources or placeholders such as `[STAT NEEDED]` — is always
escalated to the student.

To support local models with limited context, long chapters are generated as *outline → subsections → chapter
conclusion*. The number of subsections is derived from the page targets in `rnu_rules.yaml`, which allows 8k–16k-token
models to produce 20–50-page documents. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details.

## Supported Document Types

| Type | Stages | Min. references | Page targets (Ch. 1 / Literature / Theory / Practical / Conclusion) |
|---|---|---|---|
| `thesis` — Bachelor / Master thesis | 8 | 20 | 5–20 / 12–30 / 8–20 / 25–35 / 1–2 |
| `course_work` — Course work | 8 | 10 | 3–8 / 5–12 / 3–8 / 10–20 / 1–2 |
| `conference_paper` — RNU Science Week paper | 7 (no theory stage) | 8 | 4–6 pages in total |

## Anti-Fabrication Safeguards

| Risk | Mitigation |
|---|---|
| Invented statistics | Sourced facts table; prompts permit only `(F#)` facts; `[STAT NEEDED]` placeholders block approval |
| Hallucinated references | Sources come only from APIs or BibTeX; Crossref verification; unknown, unverified or excluded keys block approval |
| Invented results | Every number in the results discussion must appear in the analysis of the uploaded CSV; sample data blocks approval |
| Mock-up-only Chapter 3 | Project folder must contain source code; run/deployment steps are required; URL is checked |
| Drifting thesis statements | Key terms of each statement must reappear in the general conclusion (≥ 50% stem overlap) |
| Fabricated progress | Bi-weekly e-mail is rendered exclusively from the event log |
| Undisclosed AI use | Per-stage diff between AI draft and final text is included as Appendix A of the DOCX |

## RNU Rules

All institutional rules are defined in a single file, [`app/rules/rnu_rules.yaml`](app/rules/rnu_rules.yaml):
thesis-statement prefixes per language, sentence limits for the aim and topicality, vague-aim patterns, SMART action
verbs, page targets, Science Week constraints, formatting (Times New Roman 12 pt, 1.5 line spacing, margins) and
recognised source-code file extensions.

Align the file with the official *Common Mistakes Checklist* and *RNU Thesis Example*, then select
**Settings → Reload RNU rules** in the portal (or call `POST /api/rules/reload`).

> Localised thesis-statement prefixes (lv, ru, uz, …) are provided as suggestions — confirm the official wording with
> your supervisor. The English prefixes (`Has been OFFERED / MODIFIED / SUGGESTED`) are always accepted.

## Measurement Data Format

```csv
metric,variant,value,run
latency_ms,baseline,412,1
latency_ms,proposed,288,1
latency_ms,baseline,398,2
latency_ms,proposed,301,2
```

The `variant` column identifies the groups being compared (e.g. `baseline` vs. `proposed`). An example file can be
downloaded from the portal or via `GET /api/experiments/sample.csv`; note that Chapter 3 cannot be approved with
sample data.

## HTTP API

All responses use the envelope `{"ok": true, "data": ...}` or `{"ok": false, "error": "..."}`.
In the table below, `P` denotes `/api/projects/{id}`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/meta` | Health check; languages and document types |
| GET / PUT | `/api/settings` | Read / update settings |
| GET / POST | `/api/llm/status`, `/api/llm/test` | Check LLM connectivity |
| POST | `/api/rules/reload` | Reload `rnu_rules.yaml` |
| GET / POST | `/api/projects` | List / create projects |
| GET / DELETE | `P` | Retrieve / delete a project |
| PATCH | `P/state` | Apply a manual edit to the project state |
| GET | `P/validate` | Run the Employee 1 audit |
| POST | `P/run`, `P/decision`, `P/cancel` | Run a stage; submit a decision (approve / revise / rerun); cancel |
| GET | `P/events`, `P/history` | Activity log; checkpoints |
| POST | `P/rollback` | Restore a checkpoint |
| POST | `P/refs/search`, `P/refs/add`, `P/refs/bibtex`, `P/refs/verify` | Search, add, import and verify references |
| PATCH / DELETE | `P/refs/{key}` | Update / remove a reference |
| POST / PUT | `P/experiments`, `P/experiments/config` | Upload measurements; configure analysis |
| POST | `P/implementation/check` | Verify code and deployment evidence |
| POST / GET | `P/template/{kind}`, `P/templates` | Upload official DOCX template; template status |
| GET | `P/export/{kind}.docx` | Export DOCX (thesis or paper) |
| GET | `P/export/submission`, `P/export/progress`, `P/export/compliance`, `P/export/project.json` | Submission sheet, bi-weekly e-mail, compliance report, JSON backup |

## LangGraph Runtime

The portal uses a lightweight built-in graph engine (`app/orchestrator/engine.py`) whose interrupt/resume semantics
mirror `langgraph.types.interrupt`. The same agent nodes can also be executed on **LangGraph** from the command line:

```bash
pip install -r requirements-langgraph.txt
python scripts/langgraph_demo.py --demo
python scripts/langgraph_demo.py --model qwen2.5:14b-instruct --doc-type thesis --language en
```

At each interrupt, enter `a` to approve, `r` to request a revision with feedback, or `q` to quit. State is
checkpointed to `data/langgraph.sqlite`, so a session can be resumed later with the same `--thread`.

## Testing and Benchmarks

```bash
python -m pytest                          # 21 tests: validators, full workflow, export, HTTP API
python scripts/benchmark_validators.py    # Employee 1 precision / recall / F1 and latency
python scripts/benchmark_citations.py --topic "..." --out citations.csv   # Direct LLM vs. pipeline: fabricated-citation rate
```

`benchmark_validators.py` uses `tests/data/validator_benchmark.jsonl` by default. With `--csv`, it writes results in
the measurement CSV format, which can be uploaded directly to the portal.

## Project Structure

```
app/
├── __main__.py      CLI entry point (python -m app)
├── config.py        Environment variables and data/settings.json
├── web.py           HTTP API (Starlette)
├── services.py      Service layer: projects, background jobs, exports
├── db.py            SQLite: projects · events · checkpoints
├── orchestrator/    engine.py (checkpoints + interrupts), graph.py (8 agents, PM gate),
│                    employees.py, state.py, prompts/*.md, langgraph_adapter.py
├── validators/      rules.py (RNU matrix), text.py (sentences / words / statistics), messages.py (uz/en/ru/lv)
├── rules/           rnu_rules.yaml — editable RNU rules
├── references/      sources.py (OpenAlex, Crossref, Semantic Scholar, BibTeX), formatting.py (APA / IEEE), library.py
├── experiments/     analysis.py (statistical tests, charts)
├── export/          docx_writer.py (thesis + paper), submission.py (Science Week sheet), labels.py
├── reports/         progress.py + templates/ (bi-weekly e-mail in four languages)
├── llm/             Ollama, OpenAI-compatible and demo (mock) providers
└── i18n/            Backend translations
static/              Web portal (build-free ES modules, works offline)
scripts/             Benchmarks and LangGraph demo
tests/               pytest suite and benchmark data
docs/                ARCHITECTURE.md, COURSE_WORK.md
data/                (created at runtime) SQLite database, uploads, exports, settings.json
```

## Troubleshooting

| Symptom | Resolution |
|---|---|
| LLM connection fails | Ensure `ollama serve` is running and the model is pulled (`ollama list`); use **Settings → Test LLM** |
| JSON errors or empty drafts | Use a larger model, increase `llm_json_retries`, or adjust `llm_num_ctx` to the model's context size |
| Slow generation | Use a smaller model (7–8B) or a GPU; increase `llm_timeout_s` |
| Page count is approximate | Install LibreOffice to enable exact page measurement for Science Week papers |
| Approval is blocked | Resolve the blocking findings in the Employee 1 audit — typically missing facts, references, measurements or code evidence |
| Port already in use | Run `python -m app --port 8800` or set `RNU_PORT=8800` |

## Academic Integrity

RNU Thesis Copilot accelerates the writing process, but the student remains the author and is fully responsible for
the content, thesis statements and conclusions. Disclose the use of AI in accordance with RNU and supervisor
requirements; the AI-use appendix in the exported DOCX is designed for this purpose.

Guidance on presenting this project itself as a course work is available in
[`docs/COURSE_WORK.md`](docs/COURSE_WORK.md) (in Uzbek).
