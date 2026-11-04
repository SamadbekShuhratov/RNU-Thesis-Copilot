// Project workspace: header, tabs and the pipeline (8 employees + human review).
import { api, h, t, toast, modal, guard, icon, store, fmtDate } from "../core.js";
import { STAGE_KEY, stageEditor, findingsList } from "./forms.js";
import { TABS } from "./tabs.js";

const ws = { pid: null, data: null, tab: "pipeline", sel: null, draft: null, dirty: false, timer: null, lastEvent: 0, log: [], root: null };

export function leaveWorkspace() {
  clearTimeout(ws.timer);
  ws.timer = null;
  ws.pid = null;
}

export function workspaceDirty() { return ws.dirty; }

export async function renderWorkspace(root, pid, tab) {
  const switching = ws.pid !== pid;
  if (switching) { leaveWorkspace(); Object.assign(ws, { pid, sel: null, draft: null, dirty: false, lastEvent: 0, log: [] }); }
  ws.tab = tab || "pipeline";
  ws.root = root;
  await reload();
}

async function reload(keepDraft = false) {
  if (!ws.pid) return;
  const data = await api.get(`/api/projects/${ws.pid}`);
  ws.data = data;
  if (!ws.sel || !data.state.stages.includes(ws.sel)) ws.sel = data.state.stage === "done" ? data.state.stages.at(-1) : data.state.stage;
  if (!keepDraft || !ws.draft) { ws.draft = structuredClone(data.state[STAGE_KEY[ws.sel]] || {}); ws.dirty = false; }
  await pullEvents();
  draw();
  schedule();
}

function schedule() {
  clearTimeout(ws.timer);
  if (!ws.pid) return;
  const running = ws.data?.status === "running";
  ws.timer = setTimeout(async () => {
    try {
      if (running) {
        const before = ws.data.status;
        const data = await api.get(`/api/projects/${ws.pid}`);
        await pullEvents();
        if (data.status !== "running") {
          ws.data = data;
          ws.sel = data.state.stage === "done" ? data.state.stages.at(-1) : data.state.stage;
          ws.draft = structuredClone(data.state[STAGE_KEY[ws.sel]] || {});
          ws.dirty = false;
          if (before === "running") toast(data.status === "error" ? t("run_failed") : t("run_finished"), data.status === "error");
          draw();
        } else { ws.data = data; drawLogOnly(); drawStepsOnly(); }
      }
    } catch (_) { /* transient */ }
    schedule();
  }, running ? 1800 : 15000);
}

async function pullEvents() {
  const evs = await api.get(`/api/projects/${ws.pid}/events?since=${ws.lastEvent}`);
  if (evs.length) { ws.lastEvent = evs.at(-1).id; ws.log.push(...evs); ws.log = ws.log.slice(-400); }
}

// ── drawing ─────────────────────────────────────────────────────────────
function statusBadge(status) {
  const map = { running: "run", review: "warn", done: "ok", error: "block", ready: "accent" };
  return h("span", { class: `badge ${map[status] || ""}` }, status === "running" ? h("span", { class: "spin" }) : null, t(`st_${status}`));
}

function draw() {
  const { data } = ws;
  const st = data.state;
  const p = st.project;
  const title = st.outline?.selected_title || p.name;
  const nBlock = data.findings.filter((f) => f.severity === "block").length;
  const tabs = [
    ["pipeline", t("tab_pipeline"), nBlock ? h("span", { class: "badge block cnt" }, nBlock) : null],
    ["facts", t("tab_facts"), h("span", { class: "badge cnt" }, (st.facts || []).length)],
    ["references", t("tab_references"), h("span", { class: "badge cnt" }, (st.references || []).filter((r) => r.status === "verified").length)],
    ["implementation", t("tab_implementation")],
    ...(p.doc_type === "conference_paper" ? [["submission", t("tab_submission")]] : []),
    ["export", t("tab_export")],
    ["history", t("tab_history")],
  ];
  const head = h("div", { class: "ws-head" },
    h("div", { style: { flex: 1, minWidth: "280px" } },
      h("div", { class: "muted small" }, h("a", { href: "#/projects" }, t("nav_projects")), " / ", t(`dt_${p.doc_type}`), " · ", store.meta?.output_languages?.[p.language]?.native || p.language),
      h("h1", {}, title)),
    statusBadge(data.status));
  const body = h("div", { id: "ws-body" });
  ws.root.replaceChildren(head,
    h("nav", { class: "tabs" }, tabs.map(([k, label, extra]) => h("a", { href: `#/p/${ws.pid}/${k}`, class: ws.tab === k ? "active" : "" }, label, extra || null))),
    body);
  if (ws.tab === "pipeline") drawPipeline(body);
  else TABS[ws.tab]?.(body, ws.data, { reload: () => reload(), pid: ws.pid });
}

function stepClass(stage) {
  const st = ws.data.state;
  const cls = ["step", st.stage_status?.[stage] || "pending"];
  if (st.stage === stage) cls.push(ws.data.status === "running" ? "running" : "current");
  if (ws.sel === stage) cls.push("sel");
  return cls.join(" ");
}

function stepsEl() {
  const st = ws.data.state;
  const emps = ws.data.employees;
  return h("div", { class: "steps", id: "steps" },
    st.stages.map((s) => h("div", { class: stepClass(s), onClick: () => selectStage(s) },
      h("div", { class: "n" }, st.stage_status?.[s] === "approved" ? "✓" : emps[s].no),
      h("div", {}, h("b", {}, t(`stage_${s}`)), h("span", {}, `${t("employee")} ${emps[s].no} · ${t(`ss_${st.stage_status?.[s] || "pending"}`)}`)))),
    h("div", { class: "gatebox" }, h("b", {}, t("pm_title")), h("div", {}, t("pm_desc"))));
}

function drawStepsOnly() {
  const el = document.getElementById("steps");
  if (el) el.replaceWith(stepsEl());
}

function logEl() {
  const lines = ws.log.slice(-120).map((e) => h("div", { class: `k-${e.kind}` },
    `${new Date(e.ts * 1000).toLocaleTimeString()}  ${e.stage ? `[${e.stage}] ` : ""}${e.message}`));
  const box = h("div", { class: "log", id: "log" }, lines.length ? lines : h("div", { class: "muted" }, t("log_empty")));
  requestAnimationFrame(() => { box.scrollTop = box.scrollHeight; });
  return box;
}

function drawLogOnly() {
  const el = document.getElementById("log");
  if (el) el.replaceWith(logEl());
  const n = document.getElementById("run-notice");
  const last = ws.log.filter((e) => e.kind !== "llm").at(-1);
  if (n && last) n.textContent = `${t("working")}: ${last.message}`;
}

async function selectStage(stage) {
  if (ws.dirty && !confirm(t("discard_changes"))) return;
  ws.sel = stage;
  ws.draft = structuredClone(ws.data.state[STAGE_KEY[stage]] || {});
  ws.dirty = false;
  draw();
}

function drawPipeline(body) {
  const { data } = ws;
  const st = data.state;
  const stage = ws.sel;
  const isCurrent = st.stage === stage;
  const running = data.status === "running";
  const emp = data.employees[stage];

  const findingsBox = h("div", {});
  const loadFindings = async () => {
    let f = isCurrent ? data.findings : await api.get(`/api/projects/${ws.pid}/validate?stage=${stage}`);
    findingsBox.replaceChildren(findingsList(f));
    return f;
  };

  const notice = [];
  if (running) notice.push(h("div", { class: "notice run", id: "run-notice" }, h("span", { class: "spin" }), " ", t("working")));
  else if (data.status === "error") notice.push(h("div", { class: "notice bad" }, t("err_run"), " ", data.job?.error || ""));
  else if (isCurrent && data.status === "ready") notice.push(h("div", { class: "notice" }, t("ready_hint", { n: emp.no })));
  else if (isCurrent && data.status === "review") notice.push(h("div", { class: `notice${st.notice === "approval_blocked" ? " bad" : ""}` }, st.notice === "approval_blocked" ? t("approval_blocked") : t("review_hint")));
  else if (data.status === "done") notice.push(h("div", { class: "notice" }, t("done_hint")));
  if (!isCurrent && st.stage_status?.[stage] === "pending") notice.push(h("div", { class: "notice" }, t("pending_hint")));

  const actions = h("div", { class: "actions" });
  const canEdit = !running && !["references", "final"].includes(stage);
  if (running) actions.append(h("button", { class: "danger", onClick: () => guard(() => api.post(`/api/projects/${ws.pid}/cancel`), t("cancel_requested")) }, icon("stop"), t("cancel_run")));
  if (!running && isCurrent && data.status === "ready") actions.append(h("button", { class: "primary", onClick: runNow }, icon("play"), t("run_employee", { n: emp.no })));
  if (!running && data.status === "error") actions.append(h("button", { class: "primary", onClick: runNow }, icon("redo"), t("retry")));
  if (canEdit && st.stage_status?.[stage] !== "pending") actions.append(h("button", { onClick: () => save() }, icon("save"), t("save")));
  if (!running && isCurrent && data.status === "review") {
    actions.append(
      h("button", { onClick: () => reviseDialog() }, icon("redo"), t("request_revision")),
      h("button", { class: "primary", onClick: approve }, icon("check"), stage === "final" ? t("approve_final") : t("approve")));
  }
  if (!running && !isCurrent && data.status === "review" && st.stage_status?.[stage] !== "pending")
    actions.append(h("button", { onClick: () => rerunDialog(stage) }, icon("redo"), t("rerun_from_here")));

  let editor;
  if (stage === "references") editor = bibliographyView(st);
  else if (stage === "final") editor = complianceView(st, data);
  else if (st.stage_status?.[stage] === "pending" && !Object.keys(ws.draft || {}).length) editor = h("div", { class: "empty" }, t("not_started_yet"));
  else editor = stageEditor(stage, ws.draft, {
    findings: isCurrent ? data.findings : [],
    prefixes: (store.meta?.nail_prefixes?.[st.project.language] || store.meta?.nail_prefixes?.en),
    onDirty: () => { ws.dirty = true; },
    onReviseSection: isCurrent && data.status === "review" ? (i, heading) => reviseDialog(i, heading) : null,
  });

  const auth = data.authorship?.[stage];
  body.replaceChildren(h("div", { class: "pipe" }, stepsEl(),
    h("div", {},
      h("div", { class: "card" },
        h("div", { class: "card-head" },
          h("div", {}, h("div", { class: "muted small" }, `${t("employee")} ${emp.no} — ${t(`role_${stage}`)}`), h("h2", {}, t(`stage_${stage}`))),
          h("div", { class: "spacer" }),
          auth ? h("span", { class: "badge", title: t("authorship_tip") }, t("authorship_badge", { p: auth.changed_pct })) : null,
          h("span", { class: `badge ${st.stage_status?.[stage] === "approved" ? "ok" : st.stage_status?.[stage] === "draft" ? "warn" : ""}` }, t(`ss_${st.stage_status?.[stage] || "pending"}`))),
        notice, actions),
      h("div", { class: "card" }, h("h3", {}, t("pm_audit")), findingsBox),
      h("div", { class: "card" }, editor),
      h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", {}, t("activity")), h("div", { class: "spacer" }), h("span", { class: "muted small" }, t("llm_calls", { n: ws.log.filter((e) => e.kind === "llm").length }))), logEl()))));
  loadFindings();
}

function bibliographyView(st) {
  const entries = st.bibliography?.entries || [];
  if (!entries.length) return h("div", { class: "empty" }, t("not_started_yet"));
  return h("div", {}, h("p", { class: "muted small" }, t("bib_hint", { style: (st.bibliography.style || "apa").toUpperCase() })),
    h("ol", { style: { paddingLeft: "18px" } }, entries.map((e) => h("li", { class: "ref-title", style: { marginBottom: "6px" } }, e.text))));
}

function complianceView(st, data) {
  const c = st.compliance || {};
  if (!c.per_stage) return h("div", { class: "empty" }, t("not_started_yet"));
  return h("div", {},
    h("table", { class: "data" }, h("thead", {}, h("tr", {}, h("th", {}, t("stage")), h("th", {}, t("status")), h("th", {}, t("blocking")), h("th", {}, t("warnings")), h("th", {}, t("changed_by_you")))),
      h("tbody", {}, Object.entries(c.per_stage).map(([s, v]) => h("tr", {}, h("td", {}, t(`stage_${s}`)), h("td", {}, t(`ss_${v.status}`)),
        h("td", {}, v.blocking ? h("span", { class: "badge block" }, v.blocking) : "0"), h("td", {}, v.warnings),
        h("td", {}, data.authorship?.[s] ? `${data.authorship[s].changed_pct}%` : "—"))))),
    h("dl", { class: "kv", style: { marginTop: "14px" } },
      h("dt", {}, t("total_words")), h("dd", {}, c.total_words),
      h("dt", {}, t("page_estimate")), h("dd", {}, c.page_count_exact ? `${c.page_count_exact} (LibreOffice)` : `≈ ${c.page_estimate}`),
      h("dt", {}, t("refs_verified")), h("dd", {}, `${c.references_verified} / ${c.references_total}`)));
}

// ── actions ─────────────────────────────────────────────────────────────
async function save(silent = false) {
  if (!ws.dirty) { if (!silent) toast(t("nothing_to_save")); return; }
  const key = STAGE_KEY[ws.sel];
  await guard(() => api.patch(`/api/projects/${ws.pid}/state`, { patch: { [key]: ws.draft }, message: `Edited ${ws.sel}` }), silent ? null : t("saved"));
  ws.dirty = false;
  await reload();
}

async function runNow() {
  await guard(() => api.post(`/api/projects/${ws.pid}/run`));
  await reload();
}

async function approve() {
  if (ws.dirty) await save(true);
  await guard(() => api.post(`/api/projects/${ws.pid}/decision`, { action: "approve" }));
  await reload();
}

function reviseDialog(section = null, heading = "") {
  const ta = h("textarea", { rows: 6, placeholder: t("feedback_ph") });
  const refresh = h("input", { type: "checkbox" });
  const content = h("div", {},
    section !== null ? h("p", { class: "muted" }, t("revise_only_section", { n: section + 1, h: heading })) : h("p", { class: "muted" }, t("revise_hint")),
    h("label", { class: "f" }, h("span", { class: "l" }, t("feedback")), ta),
    ws.sel === "literature" && section === null ? h("label", { class: "check" }, refresh, t("refresh_refs")) : null);
  modal(t("request_revision"), content, [{
    label: t("send_to_employee"), primary: true, onClick: async () => {
      if (ws.dirty) await save(true);
      const body = { action: "revise", feedback: ta.value };
      if (section !== null) body.section = section;
      if (refresh.checked) body.refresh_refs = true;
      await api.post(`/api/projects/${ws.pid}/decision`, body);
      await reload();
    },
  }]);
  setTimeout(() => ta.focus(), 50);
}

function rerunDialog(stage) {
  const ta = h("textarea", { rows: 4, placeholder: t("feedback_ph") });
  modal(t("rerun_from_here"), h("div", {}, h("p", { class: "muted" }, t("rerun_warning", { s: t(`stage_${stage}`) })), ta), [{
    label: t("rerun_from_here"), primary: true, onClick: async () => {
      await api.post(`/api/projects/${ws.pid}/decision`, { action: "rerun", target: stage, feedback: ta.value });
      ws.sel = stage;
      await reload();
    },
  }]);
}

export function wsReload() { return reload(); }
export { fmtDate };
