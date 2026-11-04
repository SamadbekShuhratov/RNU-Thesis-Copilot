// Router, navigation, projects dashboard, new-project wizard, settings and guide.
import { api, h, t, toast, modal, guard, icon, store, setLang, fmtDate } from "./core.js";
import { renderWorkspace, leaveWorkspace, workspaceDirty } from "./views/workspace.js";

const view = document.getElementById("view");

function nav(active) {
  const items = [["projects", "#/projects", "nav_projects"], ["guide", "#/guide", "nav_guide"], ["settings", "#/settings", "nav_settings"]];
  document.getElementById("nav").replaceChildren(...items.map(([k, href, label]) =>
    h("a", { href, class: active === k ? "active" : "" }, icon(k === "projects" ? "projects" : k), t(label))));
}

async function refreshLlmPill() {
  const pill = document.getElementById("llm-pill");
  try {
    const s = await api.get("/api/llm/status");
    const okModel = s.ok && (s.model_available !== false);
    pill.replaceChildren(h("span", { class: `dot ${okModel ? "ok" : "bad"}` }),
      h("span", {}, s.provider === "mock" ? t("demo_mode") : `${s.model || "—"}`, h("br"), h("span", { class: "muted" }, s.ok ? (okModel ? t("llm_ok") : t("llm_model_missing")) : t("llm_offline"))));
    pill.title = s.error || s.base_url || "";
  } catch (_) {
    pill.replaceChildren(h("span", { class: "dot bad" }), h("span", {}, t("llm_offline")));
  }
}

// ── projects dashboard ──────────────────────────────────────────────────
async function projectsView() {
  nav("projects");
  const list = await api.get("/api/projects");
  const grid = h("div", { class: "plist" }, list.map((p) => {
    const stages = store.meta.doc_types[p.doc_type]?.stages || [];
    return h("div", { class: "card pcard", onClick: () => { location.hash = `#/p/${p.id}/pipeline`; } },
      h("div", { class: "actions" }, h("span", { class: "badge accent" }, t(`dt_${p.doc_type}`)), h("span", { class: "badge" }, p.language.toUpperCase()),
        h("div", { class: "spacer" }), h("span", { class: `badge ${p.status === "done" ? "ok" : p.status === "review" ? "warn" : p.status === "running" ? "run" : ""}` }, t(`st_${p.status}`))),
      h("h3", {}, p.title || p.name),
      h("div", { class: "muted small" }, p.stage && p.stage !== "done" ? `${t("now")}: ${t(`stage_${p.stage}`)}` : t("st_done"), " · ", fmtDate(p.updated_at)),
      h("div", { class: "mini-steps" }, stages.map((s) => h("i", { class: p.stage_status?.[s] || "", title: t(`stage_${s}`) }))));
  }));
  view.replaceChildren(
    h("div", { class: "topbar" }, h("div", {}, h("h1", {}, t("projects_title")), h("div", { class: "muted" }, t("projects_sub"))), h("div", { class: "spacer" }),
      h("button", { class: "primary", onClick: newProjectDialog }, icon("plus"), t("new_project"))),
    h("div", { class: "integrity" }, t("integrity_banner")),
    list.length ? grid : h("div", { class: "card empty" }, h("h2", {}, t("no_projects")), h("p", {}, t("no_projects_hint")),
      h("button", { class: "primary", onClick: newProjectDialog }, icon("plus"), t("new_project"))));
}

function newProjectDialog() {
  const m = store.meta;
  const d = { name: "", doc_type: "course_work", language: store.lang === "uz" ? "en" : store.lang, setup: { citation_style: "apa", university: "Riga Nordic University", city: "Riga", technical_section: "" } };
  const s = d.setup;
  const inp = (obj, key, attrs = {}) => h(attrs.rows ? "textarea" : "input", { ...attrs, value: obj[key] || "", onInput: (e) => { obj[key] = e.target.value; } });
  const lab = (label, el, hint) => h("label", { class: "f" }, h("span", { class: "l" }, h("span", {}, label)), hint ? h("div", { class: "muted small", style: { marginBottom: "4px" } }, hint) : null, el);
  const secSel = h("select", { onChange: (e) => { s.technical_section = e.target.value; } }, h("option", { value: "" }, "—"), m.science_week.technical_sections.map((x) => h("option", { value: x }, x)));
  const content = h("div", {},
    h("div", { class: "grid2" },
      lab(t("f_name") + " *", inp(d, "name", { placeholder: t("name_ph") })),
      lab(t("f_doc_type"), h("select", { onChange: (e) => { d.doc_type = e.target.value; } },
        Object.keys(m.doc_types).map((k) => h("option", { value: k, selected: k === d.doc_type }, t(`dt_${k}`))))),
      lab(t("f_language"), h("select", { onChange: (e) => { d.language = e.target.value; } },
        Object.entries(m.output_languages).map(([k, v]) => h("option", { value: k, selected: k === d.language }, `${v.native} (${v.name})`))), t("h_language")),
      lab(t("f_citation_style"), h("select", { onChange: (e) => { s.citation_style = e.target.value; } }, ["apa", "ieee"].map((x) => h("option", { value: x }, x.toUpperCase()))))),
    lab(t("f_topic") + " *", inp(s, "topic", { rows: 2, placeholder: t("topic_ph") })),
    h("div", { class: "grid2" },
      lab(t("f_object_hint"), inp(s, "object_hint", { placeholder: t("object_ph") }), t("h_object")),
      lab(t("f_subject_hint"), inp(s, "subject_hint", { placeholder: t("subject_ph") }), t("h_subject")),
      lab(t("f_student"), inp(s, "student_name")),
      lab(t("f_student_email"), inp(s, "student_email", { type: "email" })),
      lab(t("f_supervisor"), inp(s, "supervisor")),
      lab(t("f_supervisor_email"), inp(s, "supervisor_email", { type: "email" })),
      lab(t("sw_tech_section"), secSel),
      lab(t("f_field"), inp(s, "field"))),
    lab(t("f_notes"), inp(s, "notes", { rows: 2, placeholder: t("notes_ph") })));
  modal(t("new_project"), content, [{
    label: t("create"), primary: true, onClick: async () => {
      if (!d.name.trim() || !(s.topic || "").trim()) { toast(t("name_topic_required"), true); return false; }
      if (!s.field) s.field = s.technical_section;
      const r = await api.post("/api/projects", d);
      location.hash = `#/p/${r.id}/facts`;
      toast(t("project_created"));
    },
  }]);
}

// ── settings ─────────────────────────────────────────────────────────────
async function settingsView() {
  nav("settings");
  const s = await api.get("/api/settings");
  const models = h("datalist", { id: "models" });
  const status = h("div", { class: "muted small" });
  const val = (k, attrs = {}) => h("input", { ...attrs, value: s[k], onInput: (e) => { s[k] = attrs.type === "number" ? Number(e.target.value) : e.target.value; } });
  const presets = { ollama: "http://localhost:11434", openai_compatible: "http://localhost:1234", mock: "" };
  const baseUrl = val("llm_base_url");
  const provider = h("select", { onChange: (e) => { s.llm_provider = e.target.value; if (presets[s.llm_provider] !== undefined && presets[s.llm_provider]) { baseUrl.value = presets[s.llm_provider]; s.llm_base_url = baseUrl.value; } } },
    [["ollama", "Ollama"], ["openai_compatible", "OpenAI-compatible (LM Studio, llama.cpp, vLLM, Jan)"], ["mock", t("demo_model")]].map(([v, l]) => h("option", { value: v, selected: v === s.llm_provider }, l)));
  const loadModels = async () => {
    status.textContent = t("checking");
    try {
      await api.put("/api/settings", s);
      const st = await api.get("/api/llm/status");
      models.replaceChildren(...(st.models || []).map((m) => h("option", { value: m })));
      status.textContent = st.ok ? t("models_found", { n: (st.models || []).length }) : `${t("llm_offline")}: ${st.error || ""}`;
    } catch (e) { status.textContent = e.message; }
  };
  const judge = h("input", { type: "checkbox", checked: s.llm_judge, onChange: (e) => { s.llm_judge = e.target.checked; } });
  view.replaceChildren(
    h("div", { class: "topbar" }, h("h1", {}, t("settings_title"))),
    h("div", { class: "card" }, h("h3", {}, t("llm_section")),
      h("p", { class: "muted small" }, t("llm_hint")),
      h("div", { class: "grid2" },
        h("label", { class: "f" }, h("span", { class: "l" }, t("provider")), provider),
        h("label", { class: "f" }, h("span", { class: "l" }, t("base_url")), baseUrl),
        h("label", { class: "f" }, h("span", { class: "l" }, t("model")), h("input", { list: "models", value: s.llm_model, onInput: (e) => { s.llm_model = e.target.value; } }), models),
        h("label", { class: "f" }, h("span", { class: "l" }, t("api_key")), val("llm_api_key", { type: "password", placeholder: t("optional") })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("temperature")), val("llm_temperature", { type: "number", step: "0.05", min: 0, max: 1.5 })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("num_ctx")), val("llm_num_ctx", { type: "number", step: 1024, min: 2048 })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("timeout")), val("llm_timeout_s", { type: "number", min: 30 })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("json_retries")), val("llm_json_retries", { type: "number", min: 0, max: 5 }))),
      h("div", { class: "actions" }, h("button", { onClick: loadModels }, t("find_models")),
        h("button", { onClick: async () => { await api.put("/api/settings", s); status.textContent = t("testing"); try { const r = await api.post("/api/llm/test"); status.textContent = t("test_ok", { s: r.seconds, r: r.reply }); } catch (e) { status.textContent = e.message; } } }, t("test_connection")), status),
      h("div", { class: "muted small", style: { marginTop: "10px" } }, t("model_reco"))),
    h("div", { class: "card" }, h("h3", {}, t("pm_section")),
      h("div", { class: "grid2" },
        h("label", { class: "f" }, h("span", { class: "l" }, t("max_auto")), val("max_auto_revisions", { type: "number", min: 0, max: 3 })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("llm_judge")), h("label", { class: "check" }, judge, t("llm_judge_hint"))))),
    h("div", { class: "card" }, h("h3", {}, t("refs_section")),
      h("div", { class: "grid3" },
        h("label", { class: "f" }, h("span", { class: "l" }, t("openalex_mail")), val("openalex_mailto", { type: "email", placeholder: t("optional") })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("refs_per_query")), val("references_per_query", { type: "number", min: 1, max: 25 })),
        h("label", { class: "f" }, h("span", { class: "l" }, t("refs_from_year")), val("references_from_year", { type: "number", min: 1950, max: 2100 })))),
    h("div", { class: "actions" }, h("div", { class: "spacer" }),
      h("button", { onClick: () => guard(() => api.post("/api/rules/reload"), t("rules_reloaded")) }, t("reload_rules")),
      h("button", { class: "primary", onClick: async () => { await guard(() => api.put("/api/settings", s), t("saved")); refreshLlmPill(); } }, icon("save"), t("save"))));
  loadModels();
}

// ── guide ────────────────────────────────────────────────────────────────
function guideView() {
  nav("guide");
  const steps = ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"];
  view.replaceChildren(
    h("div", { class: "topbar" }, h("h1", {}, t("guide_title"))),
    h("div", { class: "card" }, h("h3", {}, t("guide_logic")), h("p", {}, t("guide_logic_text"))),
    h("div", { class: "card" }, h("h3", {}, t("guide_flow")), h("ol", {}, steps.map((k) => h("li", { style: { marginBottom: "8px" } }, t(k))))),
    h("div", { class: "card" }, h("h3", {}, t("guide_rules")), h("table", { class: "data" },
      h("thead", {}, h("tr", {}, h("th", {}, t("gr_section")), h("th", {}, t("gr_rule")), h("th", {}, t("gr_block")))),
      h("tbody", {}, ["goal", "problem", "nails", "endings", "ch3", "refs"].map((k) => h("tr", {}, h("td", {}, t(`gr_${k}_s`)), h("td", {}, t(`gr_${k}_r`)), h("td", {}, t(`gr_${k}_b`))))))),
    h("div", { class: "integrity" }, t("integrity_banner")));
}

// ── router ───────────────────────────────────────────────────────────────
async function route() {
  const hash = location.hash || "#/projects";
  const parts = hash.slice(2).split("/");
  try {
    if (parts[0] === "p" && parts[1]) {
      nav("projects");
      await renderWorkspace(view, parts[1], parts[2]);
      return;
    }
    leaveWorkspace();
    if (parts[0] === "settings") await settingsView();
    else if (parts[0] === "guide") guideView();
    else await projectsView();
  } catch (e) {
    view.replaceChildren(h("div", { class: "card notice bad" }, e.message));
  }
}

let lastHash = location.hash;
window.addEventListener("hashchange", (e) => {
  if (workspaceDirty() && !confirm(t("discard_changes"))) { history.replaceState(null, "", lastHash); return; }
  lastHash = location.hash;
  route();
});
window.addEventListener("beforeunload", (e) => { if (workspaceDirty()) { e.preventDefault(); e.returnValue = ""; } });

async function boot() {
  store.meta = await api.get("/api/meta");
  const sel = document.getElementById("ui-lang");
  const names = { uz: "O'zbekcha", en: "English", ru: "Русский", lv: "Latviešu" };
  sel.replaceChildren(...store.meta.ui_languages.map((l) => h("option", { value: l, selected: l === store.lang }, names[l] || l)));
  sel.addEventListener("change", () => { setLang(sel.value); refreshLlmPill(); route(); });
  setLang(store.lang);
  refreshLlmPill();
  setInterval(refreshLlmPill, 60000);
  route();
}

boot().catch((e) => { view.textContent = e.message; });
