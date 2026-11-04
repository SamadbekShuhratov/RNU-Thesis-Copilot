"""Application service layer used by the web API (and by tests / CLI)."""
from __future__ import annotations

import copy
import hashlib
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable

from .config import settings
from .db import Database, get_db
from .experiments.analysis import SAMPLE_CSV, analyze, parse_csv
from .llm import create_llm
from .orchestrator.engine import RunContext, Runner
from .orchestrator.graph import build_graph
from .orchestrator.state import EDITABLE_KEYS, EMPLOYEES, initial_state
from .references.library import add_reference
from .references.sources import parse_bibtex, verify_reference
from .reports.progress import authorship
from .rules import stages_for
from .validators import render_all, validate_stage
from .validators.rules import implementation_evidence

SAMPLE_HASH = hashlib.sha256(SAMPLE_CSV.strip().encode()).hexdigest()


class ConflictError(RuntimeError):
    """Operation not possible in the current state (e.g. a job is running)."""


@dataclass
class Job:
    project_id: str
    kind: str
    thread: threading.Thread | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    status: str = "running"         # running | finished | error | cancelled
    error: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None


class Copilot:
    def __init__(self, db: Database | None = None,
                 services_override: dict[str, Any] | None = None):
        self.db = db or get_db()
        self.jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self.services_override = services_override or {}

    # ── helpers ────────────────────────────────────────────────────────────
    def _runner(self, doc_type: str) -> Runner:
        return Runner(build_graph(stages_for(doc_type)), self.db)

    def _project(self, pid: str) -> dict[str, Any]:
        p = self.db.get_project(pid)
        if not p:
            raise KeyError(pid)
        return p

    def _is_running(self, pid: str) -> bool:
        job = self.jobs.get(pid)
        return bool(job and job.status == "running")

    def _require_idle(self, pid: str) -> None:
        if self._is_running(pid):
            raise ConflictError("an agent is currently working on this project — wait or cancel it")

    def log(self, pid: str, kind: str, message: str, stage: str | None = None, **data: Any) -> None:
        self.db.add_event(pid, kind, message, stage, data)

    # ── projects ───────────────────────────────────────────────────────────
    def create_project(self, name: str, doc_type: str, language: str, setup: dict[str, Any]) -> str:
        if doc_type not in ("thesis", "course_work", "conference_paper"):
            raise ValueError("doc_type must be thesis, course_work or conference_paper")
        pid = self.db.create_project(name or "Untitled", doc_type, language)
        state = initial_state(pid, name, doc_type, language, setup)
        self._runner(doc_type).create(pid, state)
        self.log(pid, "project", f"Project created ({doc_type}, {language})")
        return pid

    def list_projects(self) -> list[dict[str, Any]]:
        out = []
        for p in self.db.list_projects():
            cp = self.db.latest_checkpoint(p["id"])
            st = cp["state"] if cp else {}
            out.append({**p, "stage": st.get("stage"), "stage_status": st.get("stage_status", {}),
                        "title": (st.get("outline") or {}).get("selected_title", ""),
                        "status": self._status(p["id"], cp)})
        return out

    def delete_project(self, pid: str) -> None:
        self._require_idle(pid)
        self.db.delete_project(pid)

    def _status(self, pid: str, cp: dict[str, Any] | None) -> str:
        job = self.jobs.get(pid)
        if job and job.status == "running":
            return "running"
        if not cp:
            return "missing"
        if cp["next_node"] is None:
            return "done"
        if cp["pending"] is not None:
            return "review"
        if job and job.status == "error":
            return "error"
        return "ready"

    def get_state(self, pid: str, lang: str = "en") -> dict[str, Any]:
        project = self._project(pid)
        cp = self.db.latest_checkpoint(pid)
        state = cp["state"]
        job = self.jobs.get(pid)
        stage = state.get("stage")
        live_findings = []
        if stage in EMPLOYEES and stage != "done":
            live_findings = validate_stage(stage, state)
        return {
            "project": project,
            "status": self._status(pid, cp),
            "checkpoint": {"seq": cp["seq"], "node": cp["node"], "next": cp["next_node"],
                           "waiting": cp["pending"] is not None, "at": cp["created_at"]},
            "job": None if not job else {"kind": job.kind, "status": job.status, "error": job.error,
                                         "started_at": job.started_at, "finished_at": job.finished_at},
            "state": {k: v for k, v in state.items() if k != "ai_drafts"},
            "findings": render_all(live_findings, lang),
            "authorship": authorship(state),
            "employees": EMPLOYEES,
        }

    def raw_state(self, pid: str) -> dict[str, Any]:
        cp = self.db.latest_checkpoint(pid)
        if not cp:
            raise KeyError(pid)
        return cp["state"]

    # ── editing ────────────────────────────────────────────────────────────
    def apply_patch(self, pid: str, patch: dict[str, Any], *, message: str = "Manual edit saved",
                    kind: str = "edit") -> dict[str, Any]:
        self._require_idle(pid)
        project = self._project(pid)
        bad = set(patch) - EDITABLE_KEYS
        if bad:
            raise ValueError(f"fields not editable: {', '.join(sorted(bad))}")
        current = self.raw_state(pid)
        merged: dict[str, Any] = {}
        for key, value in patch.items():
            if key == "project" and isinstance(value, dict):
                protected = {"id", "doc_type"}
                merged[key] = {**current.get("project", {}), **{k: v for k, v in value.items() if k not in protected}}
            else:
                merged[key] = value
        content_keys = {"outline", "chapter1", "literature", "theory", "practical", "conclusion", "references",
                        "submission", "experiments"}
        if content_keys & set(patch) and (current.get("compliance") or {}).get("page_count_exact"):
            comp = dict(current["compliance"])
            comp.pop("page_count_exact", None)       # the exact count is stale after a content change
            merged["compliance"] = comp
        state = self._runner(project["doc_type"]).update_state(pid, merged)
        if "project" in merged:
            p = merged["project"]
            self.db.update_project(pid, name=p.get("name", project["name"]), language=p.get("language", project["language"]))
        else:
            self.db.touch_project(pid)
        self.log(pid, kind, message, state.get("stage"), fields=sorted(patch))
        return state

    def record_page_count(self, pid: str, pages: int) -> None:
        """Store the exact page count measured with LibreOffice (Employee 1)."""
        self._require_idle(pid)
        project = self._project(pid)
        comp = dict(self.raw_state(pid).get("compliance") or {})
        comp.update(page_count_exact=pages, page_count_at=time.time())
        self._runner(project["doc_type"]).update_state(pid, {"compliance": comp}, node="measure")
        self.log(pid, "export", f"Paper measured with LibreOffice: {pages} pages")

    def history(self, pid: str) -> list[dict[str, Any]]:
        return self.db.checkpoint_history(pid)

    def rollback(self, pid: str, seq: int) -> None:
        self._require_idle(pid)
        project = self._project(pid)
        self._runner(project["doc_type"]).rollback(pid, seq)
        self.log(pid, "rollback", f"Restored checkpoint #{seq}")

    # ── running the graph ──────────────────────────────────────────────────
    def run(self, pid: str, decision: dict[str, Any] | None = None, *, wait: bool = False) -> Job:
        project = self._project(pid)
        with self._lock:
            if self._is_running(pid):
                raise ConflictError("already running")
            cp = self.db.latest_checkpoint(pid)
            if cp["next_node"] is None:
                raise ConflictError("the workflow is complete — re-run a stage from the review panel")
            if cp["pending"] is not None and decision is None:
                raise ConflictError("waiting for your review decision")
            if cp["pending"] is None and decision is not None:
                raise ConflictError("no review is pending")
            job = Job(pid, "resume" if decision else "run")
            self.jobs[pid] = job
        runner = self._runner(project["doc_type"])

        def progress(message: str, data: dict[str, Any]) -> None:
            kind = data.pop("kind", "progress")
            stage = data.pop("stage", None)
            self.log(pid, kind, message, stage, **data)

        def target() -> None:
            llm = self.services_override.get("llm") or create_llm(settings.all())

            def on_call(rec):
                self.log(pid, "llm", f"{rec.task}: {rec.seconds}s", None, seconds=rec.seconds,
                         prompt_chars=rec.prompt_chars, response_chars=rec.response_chars, ok=rec.ok)
            llm.on_call = on_call
            services = {"llm": llm, "settings": settings.all(), **{k: v for k, v in self.services_override.items() if k != "llm"}}
            ctx = RunContext(thread_id=pid, cancel_event=job.cancel, progress_cb=progress, services=services)
            try:
                result = runner.run(ctx, resume=decision, has_resume=decision is not None)
                job.status = "cancelled" if result.status == "cancelled" else "finished"
                if result.status == "cancelled":
                    self.log(pid, "cancelled", "Run cancelled by the student")
                elif result.status == "done":
                    self.log(pid, "done", "Workflow complete — all stages approved")
            except Exception as exc:  # noqa: BLE001 - reported to the UI
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                self.log(pid, "error", job.error, None, trace=traceback.format_exc()[-2000:])
            finally:
                job.finished_at = time.time()
                self.db.touch_project(pid)

        if decision:
            self.log(pid, "decision", f"Decision: {decision.get('action')}", None,
                     **{k: v for k, v in decision.items() if k != "action"})
        if wait:
            target()
        else:
            job.thread = threading.Thread(target=target, name=f"job-{pid}", daemon=True)
            job.thread.start()
        return job

    def cancel(self, pid: str) -> bool:
        job = self.jobs.get(pid)
        if job and job.status == "running":
            job.cancel.set()
            return True
        return False

    def events(self, pid: str, since: int = 0) -> list[dict[str, Any]]:
        return self.db.events(pid, since)

    # ── references ─────────────────────────────────────────────────────────
    def add_reference(self, pid: str, candidate: dict[str, Any], verify: bool = True) -> dict[str, Any]:
        refs = list(self.raw_state(pid).get("references", []))
        refs, ref, created = add_reference(refs, candidate, verify=verify)
        if created:
            self.apply_patch(pid, {"references": refs}, message=f"Reference added: {ref['key']} ({ref['status']})",
                             kind="refs")
        return {"reference": ref, "created": created}

    def import_bibtex(self, pid: str, text: str, verify: bool = True) -> dict[str, Any]:
        refs = list(self.raw_state(pid).get("references", []))
        added = []
        for entry in parse_bibtex(text):
            refs, ref, created = add_reference(refs, entry, verify=verify)
            if created:
                added.append(ref["key"])
        self.apply_patch(pid, {"references": refs}, message=f"BibTeX import: {len(added)} new reference(s)", kind="refs")
        return {"added": added, "total": len(refs)}

    def verify_references(self, pid: str, keys: list[str] | None = None) -> dict[str, Any]:
        refs = copy.deepcopy(self.raw_state(pid).get("references", []))
        counts: dict[str, int] = {}
        for i, r in enumerate(refs):
            if keys and r["key"] not in keys:
                continue
            refs[i] = verify_reference(r)
            counts[refs[i]["status"]] = counts.get(refs[i]["status"], 0) + 1
        self.apply_patch(pid, {"references": refs}, message=f"References verified: {counts}", kind="refs")
        return counts

    def update_reference(self, pid: str, key: str, values: dict[str, Any]) -> dict[str, Any]:
        refs = copy.deepcopy(self.raw_state(pid).get("references", []))
        for r in refs:
            if r["key"] == key:
                for k in ("included", "notes", "title", "year", "venue", "doi", "url", "authors", "volume", "issue", "pages"):
                    if k in values:
                        r[k] = values[k]
                if any(k in values for k in ("title", "doi", "authors", "year")):
                    r["status"] = "unverified"
                self.apply_patch(pid, {"references": refs}, message=f"Reference {key} updated", kind="refs")
                return r
        raise KeyError(key)

    def delete_reference(self, pid: str, key: str) -> None:
        refs = [r for r in self.raw_state(pid).get("references", []) if r["key"] != key]
        self.apply_patch(pid, {"references": refs}, message=f"Reference {key} removed", kind="refs")

    # ── experiments & implementation ───────────────────────────────────────
    def upload_experiments(self, pid: str, csv_text: str, source_name: str = "",
                           config: dict[str, Any] | None = None) -> dict[str, Any]:
        rows = parse_csv(csv_text)
        state = self.raw_state(pid)
        cfg = config if config is not None else (state.get("experiments") or {}).get("config", {})
        analysis = analyze(rows, cfg)
        experiments = {"rows": rows, "config": cfg, "analysis": analysis, "source_name": source_name,
                       "uploaded_at": time.time(),
                       "is_sample": hashlib.sha256(csv_text.strip().encode()).hexdigest() == SAMPLE_HASH}
        self.apply_patch(pid, {"experiments": experiments},
                         message=f"Measurements uploaded: {len(rows)} rows, {len(analysis['metrics'])} metric(s)",
                         kind="experiments")
        return experiments

    def configure_experiments(self, pid: str, config: dict[str, Any]) -> dict[str, Any]:
        exp = copy.deepcopy(self.raw_state(pid).get("experiments") or {})
        exp["config"] = config
        if exp.get("rows"):
            exp["analysis"] = analyze(exp["rows"], config)
        self.apply_patch(pid, {"experiments": exp}, message="Experiment configuration updated", kind="experiments")
        return exp

    def check_implementation(self, pid: str, http_get: Callable[[str], int] | None = None) -> dict[str, Any]:
        impl = copy.deepcopy(self.raw_state(pid).get("implementation") or {})
        ev = implementation_evidence(impl)
        url = str(impl.get("deployed_url", "")).strip()
        if url:
            try:
                if http_get:
                    code = http_get(url)
                else:
                    import requests
                    code = requests.get(url, timeout=10).status_code
                ev["deployed_status"] = code
            except Exception as exc:  # noqa: BLE001
                ev["deployed_status"] = f"error: {exc}"
        ev["checked_at"] = time.time()
        impl["evidence"] = ev
        self.apply_patch(pid, {"implementation": impl}, message="Implementation evidence checked", kind="evidence")
        return ev


_copilot: Copilot | None = None


def get_copilot() -> Copilot:
    global _copilot
    if _copilot is None:
        _copilot = Copilot()
    return _copilot


def set_copilot(c: Copilot) -> None:
    global _copilot
    _copilot = c
