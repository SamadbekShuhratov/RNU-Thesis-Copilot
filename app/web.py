"""HTTP API + static web portal (Starlette, ASGI)."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import __version__
from .config import EXPORT_DIR, STATIC_DIR, UPLOAD_DIR, settings
from .experiments.analysis import SAMPLE_CSV, ExperimentError
from .export.docx_writer import build_paper, build_thesis, count_pages
from .export.submission import submission_markdown, submission_sheet
from .i18n import OUTPUT_LANGUAGES, UI_LANGUAGES
from .llm import create_llm
from .orchestrator.state import EMPLOYEES
from .references.sources import SourceError, crossref_by_doi, search_openalex, search_semantic_scholar
from .reports.progress import compliance_summary, progress_report
from .rules import reload_rules, rules
from .services import ConflictError, get_copilot
from .validators import render_all, validate_stage

MAX_UPLOAD = 10 * 1024 * 1024


def ok(data: Any = None, status: int = 200) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data}, status_code=status)


def err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


async def body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def lang_of(request: Request) -> str:
    lang = request.query_params.get("lang") or settings.get("ui_language", "en")
    return lang if lang in UI_LANGUAGES else "en"


def pid_of(request: Request) -> str:
    pid = request.path_params["pid"]
    if not re.fullmatch(r"[a-f0-9]{12}", pid):
        raise HTTPException(404, "project not found")
    if not get_copilot().db.get_project(pid):
        raise HTTPException(404, "project not found")
    return pid


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")[:60] or "document"


# ── meta & settings ───────────────────────────────────────────────────────
async def health(request: Request):
    return ok({"version": __version__, "time": time.time()})


async def meta(request: Request):
    r = rules()
    return ok({
        "version": __version__,
        "output_languages": OUTPUT_LANGUAGES,
        "ui_languages": UI_LANGUAGES,
        "doc_types": {k: {"label": v["label"], "stages": v["stages"]} for k, v in r["doc_types"].items()},
        "employees": EMPLOYEES,
        "science_week": r["science_week"],
        "nail_prefixes": r["nail_prefixes"],
        "citation_styles": ["apa", "ieee"],
    })


async def get_settings(request: Request):
    return ok(settings.public())


async def put_settings(request: Request):
    data = await body(request)
    try:
        settings.update(data)
    except (TypeError, ValueError) as exc:
        return err(f"invalid value: {exc}")
    return ok(settings.public())


async def llm_status(request: Request):
    llm = create_llm(settings.all())
    return ok(llm.health() | {"model": settings.get("llm_model"), "base_url": settings.get("llm_base_url")})


async def llm_test(request: Request):
    llm = create_llm(settings.all())
    t0 = time.time()
    try:
        out = llm.text("You are a helpful assistant.", "Reply with exactly: OK", task="connection_test")
    except Exception as exc:  # noqa: BLE001
        return err(str(exc), 502)
    return ok({"reply": out[:200], "seconds": round(time.time() - t0, 2)})


async def rules_reload(request: Request):
    reload_rules()
    return ok({"reloaded": True})


# ── projects ──────────────────────────────────────────────────────────────
async def projects(request: Request):
    c = get_copilot()
    if request.method == "GET":
        return ok(c.list_projects())
    data = await body(request)
    try:
        pid = c.create_project(data.get("name", "").strip() or "Untitled", data.get("doc_type", "course_work"),
                               data.get("language", "en"), data.get("setup", {}))
    except ValueError as exc:
        return err(str(exc))
    return ok({"id": pid}, 201)


async def project(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    if request.method == "DELETE":
        c.delete_project(pid)
        return ok({"deleted": pid})
    return ok(c.get_state(pid, lang_of(request)))


async def patch_state(request: Request):
    data = await body(request)
    patch = data.get("patch") or {}
    if not isinstance(patch, dict) or not patch:
        return err("patch must be a non-empty object")
    c = get_copilot()
    pid = pid_of(request)
    c.apply_patch(pid, patch, message=data.get("message") or "Manual edit saved")
    return ok(c.get_state(pid, lang_of(request)))


async def validate(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    stage = request.query_params.get("stage")
    state = c.raw_state(pid)
    stage = stage or state.get("stage")
    if stage not in EMPLOYEES:
        return ok([])
    return ok(render_all(validate_stage(stage, state), lang_of(request)))


async def run(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    c.run(pid)
    return ok(c.get_state(pid, lang_of(request)), 202)


async def decision(request: Request):
    data = await body(request)
    if data.get("action") not in ("approve", "revise", "rerun"):
        return err("action must be approve, revise or rerun")
    c = get_copilot()
    pid = pid_of(request)
    c.run(pid, {k: v for k, v in data.items() if k in ("action", "feedback", "target", "section", "refresh_refs")})
    return ok(c.get_state(pid, lang_of(request)), 202)


async def cancel(request: Request):
    return ok({"cancelled": get_copilot().cancel(pid_of(request))})


async def events(request: Request):
    since = int(request.query_params.get("since", "0") or 0)
    return ok(get_copilot().events(pid_of(request), since))


async def history(request: Request):
    return ok(get_copilot().history(pid_of(request)))


async def rollback(request: Request):
    data = await body(request)
    c = get_copilot()
    pid = pid_of(request)
    try:
        c.rollback(pid, int(data.get("seq")))
    except (TypeError, ValueError, KeyError) as exc:
        return err(f"invalid checkpoint: {exc}")
    return ok(c.get_state(pid, lang_of(request)))


# ── references ────────────────────────────────────────────────────────────
async def refs_search(request: Request):
    data = await body(request)
    query = str(data.get("query", "")).strip()
    if len(query) < 3:
        return err("query too short")
    source = data.get("source", "openalex")
    try:
        if source == "semantic_scholar":
            results = search_semantic_scholar(query, int(data.get("limit", 10)))
        else:
            results = search_openalex(query, int(data.get("limit", 10)), data.get("from_year"),
                                      settings.get("openalex_mailto", ""))
    except SourceError as exc:
        return err(str(exc), 502)
    return ok(results)


async def refs_add(request: Request):
    data = await body(request)
    c = get_copilot()
    pid = pid_of(request)
    cand = data.get("candidate")
    if not cand and data.get("doi"):
        try:
            cand = crossref_by_doi(data["doi"])
        except SourceError as exc:
            return err(str(exc), 502)
        if not cand:
            return err("DOI not found in Crossref", 404)
    if not cand or not cand.get("title"):
        return err("candidate with a title (or a DOI) is required")
    return ok(c.add_reference(pid, cand, verify=data.get("verify", True)))


async def refs_bibtex(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    form = await request.form()
    text = ""
    if "file" in form and hasattr(form["file"], "read"):
        raw = await form["file"].read()
        if len(raw) > MAX_UPLOAD:
            return err("file too large")
        text = raw.decode("utf-8", errors="replace")
    else:
        text = str(form.get("text", ""))
    if "@" not in text:
        return err("no BibTeX entries found")
    return ok(c.import_bibtex(pid, text, verify=str(form.get("verify", "true")) != "false"))


async def refs_verify(request: Request):
    data = await body(request)
    return ok(get_copilot().verify_references(pid_of(request), data.get("keys")))


async def ref_item(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    key = request.path_params["key"]
    if request.method == "DELETE":
        c.delete_reference(pid, key)
        return ok({"deleted": key})
    try:
        return ok(c.update_reference(pid, key, await body(request)))
    except KeyError:
        return err("reference not found", 404)


# ── experiments & implementation ──────────────────────────────────────────
async def experiments_upload(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return err("CSV file is required")
    raw = await upload.read()
    if len(raw) > MAX_UPLOAD:
        return err("file too large")
    try:
        exp = c.upload_experiments(pid, raw.decode("utf-8-sig", errors="replace"), getattr(upload, "filename", ""))
    except ExperimentError as exc:
        return err(str(exc))
    return ok(exp)


async def experiments_config(request: Request):
    data = await body(request)
    try:
        return ok(get_copilot().configure_experiments(pid_of(request), data.get("config", {})))
    except ExperimentError as exc:
        return err(str(exc))


async def experiments_sample(request: Request):
    return PlainTextResponse(SAMPLE_CSV, media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="measurements_format_example.csv"'})


async def implementation_check(request: Request):
    return ok(get_copilot().check_implementation(pid_of(request)))


# ── exports ───────────────────────────────────────────────────────────────
def _template_path(pid: str, kind: str) -> Path:
    return UPLOAD_DIR / pid / f"template_{kind}.docx"


async def template_upload(request: Request):
    pid = pid_of(request)
    kind = request.path_params["kind"]
    if kind not in ("paper", "thesis"):
        return err("kind must be paper or thesis")
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return err("DOCX file is required")
    raw = await upload.read()
    if len(raw) > MAX_UPLOAD or not raw.startswith(b"PK"):
        return err("please upload a .docx file (≤ 10 MB)")
    path = _template_path(pid, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    get_copilot().log(pid, "template", f"{kind} template uploaded: {getattr(upload, 'filename', '')}")
    return ok({"kind": kind, "bytes": len(raw)})


async def template_status(request: Request):
    pid = pid_of(request)
    return ok({k: _template_path(pid, k).exists() for k in ("paper", "thesis")})


async def export_docx(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    kind = request.path_params["kind"]
    state = c.raw_state(pid)
    title = (state.get("outline") or {}).get("selected_title") or state["project"]["name"]
    out_dir = EXPORT_DIR / pid
    if kind == "paper":
        path = build_paper(state, out_dir / f"{safe_name(title)}_paper.docx", _template_path(pid, "paper"))
        if request.query_params.get("measure") == "1":
            pages = count_pages(path)
            if pages:
                c.record_page_count(pid, pages)
            return ok({"pages": pages, "file": path.name, "libreoffice": pages is not None})
    elif kind == "thesis":
        path = build_thesis(state, out_dir / f"{safe_name(title)}.docx", _template_path(pid, "thesis"),
                            model=settings.get("llm_model", ""))
    else:
        return err("unknown export", 404)
    c.log(pid, "export", f"Exported {path.name}")
    return FileResponse(str(path), filename=path.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


async def export_submission(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    sheet = submission_sheet(c.raw_state(pid))
    sheet["checks"] = render_all(sheet["checks"], lang_of(request))
    if request.query_params.get("format") == "md":
        return PlainTextResponse(submission_markdown(sheet), media_type="text/markdown",
                                 headers={"Content-Disposition": 'attachment; filename="science_week_submission.md"'})
    return ok(sheet)


async def export_progress(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    days = max(1, min(90, int(request.query_params.get("days", "14") or 14)))
    lang = request.query_params.get("lang") or "en"
    return ok(progress_report(c.raw_state(pid), c.events(pid, 0), days, lang if lang in UI_LANGUAGES else "en"))


async def export_compliance(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    state = c.raw_state(pid)
    report = compliance_summary(state)
    report["findings"] = {s: render_all(validate_stage(s, state), lang_of(request))
                          for s in state.get("stages", []) if s != "final"}
    return ok(report)


async def export_json(request: Request):
    c = get_copilot()
    pid = pid_of(request)
    data = json.dumps(c.raw_state(pid), ensure_ascii=False, indent=2)
    return Response(data, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="project_{pid}.json"'})


# ── app ───────────────────────────────────────────────────────────────────
async def index(request: Request):
    return FileResponse(str(STATIC_DIR / "index.html"))


async def conflict_handler(request: Request, exc: ConflictError):
    return err(str(exc), 409)


async def value_handler(request: Request, exc: ValueError):
    return err(str(exc), 400)


async def http_handler(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/"):
        return err(exc.detail, exc.status_code)
    return PlainTextResponse(exc.detail, status_code=exc.status_code)


P = "/api/projects/{pid}"
routes = [
    Route("/", index),
    Route("/api/health", health),
    Route("/api/meta", meta),
    Route("/api/settings", get_settings, methods=["GET"]),
    Route("/api/settings", put_settings, methods=["PUT"]),
    Route("/api/llm/status", llm_status),
    Route("/api/llm/test", llm_test, methods=["POST"]),
    Route("/api/rules/reload", rules_reload, methods=["POST"]),
    Route("/api/projects", projects, methods=["GET", "POST"]),
    Route(P, project, methods=["GET", "DELETE"]),
    Route(P + "/state", patch_state, methods=["PATCH"]),
    Route(P + "/validate", validate),
    Route(P + "/run", run, methods=["POST"]),
    Route(P + "/decision", decision, methods=["POST"]),
    Route(P + "/cancel", cancel, methods=["POST"]),
    Route(P + "/events", events),
    Route(P + "/history", history),
    Route(P + "/rollback", rollback, methods=["POST"]),
    Route(P + "/refs/search", refs_search, methods=["POST"]),
    Route(P + "/refs/add", refs_add, methods=["POST"]),
    Route(P + "/refs/bibtex", refs_bibtex, methods=["POST"]),
    Route(P + "/refs/verify", refs_verify, methods=["POST"]),
    Route(P + "/refs/{key}", ref_item, methods=["PATCH", "DELETE"]),
    Route(P + "/experiments", experiments_upload, methods=["POST"]),
    Route(P + "/experiments/config", experiments_config, methods=["PUT"]),
    Route("/api/experiments/sample.csv", experiments_sample),
    Route(P + "/implementation/check", implementation_check, methods=["POST"]),
    Route(P + "/template/{kind}", template_upload, methods=["POST"]),
    Route(P + "/templates", template_status),
    Route(P + "/export/{kind}.docx", export_docx),
    Route(P + "/export/submission", export_submission),
    Route(P + "/export/progress", export_progress),
    Route(P + "/export/compliance", export_compliance),
    Route(P + "/export/project.json", export_json),
    Mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static"),
]

app = Starlette(routes=routes, exception_handlers={ConflictError: conflict_handler, ValueError: value_handler,
                                                    HTTPException: http_handler})
