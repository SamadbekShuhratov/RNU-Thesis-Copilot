// Stage editors: field specifications + generic editors bound to a draft object.
import { h, t, sentences, wordCount, icon } from "../core.js";

export const STAGE_KEY = {
  architect: "outline", chapter1: "chapter1", literature: "literature", theory: "theory",
  practical: "practical", conclusion: "conclusion", references: "bibliography", final: "compliance",
};

export const SPECS = {
  architect: [
    { key: "titles", type: "list", label: "f_titles", hint: "h_titles" },
    { key: "selected_title", type: "title", label: "f_selected_title" },
    { key: "object", type: "text", label: "f_object", hint: "h_object" },
    { key: "subject", type: "text", label: "f_subject", hint: "h_subject" },
    { key: "goal", type: "textarea", label: "f_goal", hint: "h_goal", sentences: [1, 1], rows: 3 },
    { key: "tasks", type: "list", label: "f_tasks" },
    { key: "nails", type: "nails", label: "f_nails", hint: "h_nails" },
    { key: "keywords", type: "list", label: "f_keywords" },
    { key: "rationale", type: "textarea", label: "f_rationale", rows: 3 },
  ],
  chapter1: [
    { key: "topicality", type: "textarea", label: "f_topicality", hint: "h_facts_only", sentences: [3, 4] },
    { key: "problem_formulation", type: "textarea", label: "f_problem", hint: "h_facts_only", sentences: [3, 4] },
    { key: "research_questions", type: "list", label: "f_rq" },
    { key: "methods", type: "textarea", label: "f_methods" },
    { key: "planned_results", type: "table", label: "f_planned", cols: [["result", "c_result"], ["metric", "c_metric"], ["beneficiary", "c_beneficiary"]] },
    { key: "novelty", type: "textarea", label: "f_novelty" },
    { key: "structure", type: "textarea", label: "f_structure" },
    { key: "sections", type: "sections", label: "f_sections" },
    { key: "conclusion", type: "textarea", label: "f_ch_conclusion", hint: "h_ch_conclusion" },
  ],
  literature: [
    { key: "sections", type: "sections", label: "f_lit_sections" },
    { key: "comparison", type: "table", label: "f_comparison", cols: [["approach", "c_approach"], ["sources", "c_sources"], ["strengths", "c_strengths"], ["limitations", "c_limitations"]] },
    { key: "gaps", type: "list", label: "f_gaps" },
    { key: "conclusion", type: "textarea", label: "f_lit_summary" },
  ],
  theory: [
    { key: "concepts", type: "table", label: "f_concepts", cols: [["term", "c_term"], ["definition", "c_definition"]] },
    { key: "frameworks", type: "table", label: "f_frameworks", cols: [["name", "c_name"], ["description", "c_description"], ["how_used", "c_how_used"]] },
    { key: "sections", type: "sections", label: "f_sections" },
    { key: "gap_to_solution", type: "table", label: "f_gap_solution", cols: [["gap", "c_gap"], ["solution_element", "c_solution"]] },
    { key: "conclusion", type: "textarea", label: "f_ch2_conclusion", hint: "h_ch2_conclusion" },
  ],
  practical: [
    { key: "architecture", type: "textarea", label: "f_architecture", rows: 8 },
    { key: "components", type: "table", label: "f_components", cols: [["name", "c_name"], ["responsibility", "c_responsibility"], ["technology", "c_technology"]] },
    { key: "data_flow", type: "textarea", label: "f_data_flow" },
    { key: "deployment_steps", type: "list", label: "f_deployment" },
    { key: "sections", type: "sections", label: "f_sections" },
    { key: "experiment_design", type: "textarea", label: "f_experiment" },
    { key: "results_discussion", type: "textarea", label: "f_results", hint: "h_results", rows: 8 },
    { key: "conclusion", type: "textarea", label: "f_ch_conclusion", hint: "h_ch_conclusion" },
  ],
  conclusion: [
    { key: "general_conclusion", type: "textarea", label: "f_general_conclusion", hint: "h_general_conclusion", rows: 14, words: [250, 650] },
    { key: "nail_evidence", type: "table", label: "f_nail_evidence", cols: [["nail", "c_nail"], ["evidence", "c_evidence"]] },
    { key: "limitations", type: "textarea", label: "f_limitations" },
    { key: "future_work", type: "textarea", label: "f_future" },
    { key: "abstract", type: "textarea", label: "f_abstract", rows: 8, words: [0, 400] },
  ],
};

function counter(spec, value) {
  if (spec.sentences) {
    const n = sentences(value);
    const [lo, hi] = spec.sentences;
    return h("em", { class: `counter${n < lo || n > hi ? " bad" : ""}` }, t("n_sentences", { n, range: lo === hi ? lo : `${lo}–${hi}` }));
  }
  if (spec.words) {
    const n = wordCount(value);
    const [lo, hi] = spec.words;
    return h("em", { class: `counter${n < lo || n > hi ? " bad" : ""}` }, t("n_words", { n, range: `${lo}–${hi}` }));
  }
  return value && typeof value === "string" ? h("em", { class: "counter" }, t("n_words_plain", { n: wordCount(value) })) : null;
}

function autosize(el) {
  const fit = () => { el.style.height = "auto"; el.style.height = Math.min(el.scrollHeight + 2, 900) + "px"; };
  requestAnimationFrame(fit);
  el.addEventListener("input", fit);
  return el;
}

function textArea(value, onInput, rows = 4, cls = "") {
  return autosize(h("textarea", { rows, class: cls, value: value || "", onInput: (e) => onInput(e.target.value) }));
}

function listEditor(arr, onChange, { min = 0, fixed = null, prefixes = null } = {}) {
  const items = Array.isArray(arr) ? [...arr] : [];
  if (fixed) while (items.length < fixed) items.push("");
  const wrap = h("div", { class: "list-ed" });
  const render = () => {
    wrap.innerHTML = "";
    items.forEach((v, i) => {
      const ta = textArea(v, (nv) => { items[i] = nv; onChange([...items]); }, 1);
      if (prefixes && prefixes[i]) ta.placeholder = prefixes[i] + " …";
      wrap.append(h("div", { class: "li" }, h("span", { class: "idx" }, `${i + 1}.`), ta,
        fixed ? null : h("button", { class: "ghost btn-sm", title: t("remove"), onClick: () => { items.splice(i, 1); onChange([...items]); render(); } }, "×")));
    });
    if (!fixed) wrap.append(h("div", {}, h("button", { class: "btn-sm", onClick: () => { items.push(""); onChange([...items]); render(); } }, icon("plus"), t("add"))));
  };
  render();
  return wrap;
}

function tableEditor(rows, cols, onChange) {
  const data = (Array.isArray(rows) ? rows : []).map((r) => (typeof r === "object" && r ? { ...r } : {}));
  const wrap = h("div", {});
  const render = () => {
    wrap.innerHTML = "";
    const tbl = h("table", { class: "tbl-ed" },
      h("thead", {}, h("tr", {}, cols.map(([, label]) => h("th", {}, t(label))), h("th", {}))),
      h("tbody", {}, data.map((row, i) => h("tr", {},
        cols.map(([key]) => h("td", {}, textArea(row[key], (v) => { row[key] = v; onChange(data.map((r) => ({ ...r }))); }, 1))),
        h("td", {}, h("button", { class: "ghost btn-sm", title: t("remove"), onClick: () => { data.splice(i, 1); onChange(data.map((r) => ({ ...r }))); render(); } }, "×"))))));
    wrap.append(tbl, h("button", { class: "btn-sm", onClick: () => { data.push({}); onChange(data.map((r) => ({ ...r }))); render(); } }, icon("plus"), t("add_row")));
  };
  render();
  return wrap;
}

function sectionsEditor(sections, onChange, onReviseSection) {
  const data = (Array.isArray(sections) ? sections : []).map((s) => ({ ...s }));
  const wrap = h("div", {});
  const render = () => {
    wrap.innerHTML = "";
    if (!data.length) wrap.append(h("p", { class: "muted small" }, t("no_sections")));
    data.forEach((sec, i) => {
      const cnt = h("span", { class: "counter" }, t("n_words_plain", { n: wordCount(sec.text) }));
      wrap.append(h("div", { class: "sec-ed" },
        h("div", { class: "sh" }, h("span", { class: "muted" }, `${i + 1}.`),
          h("input", { value: sec.heading || "", onInput: (e) => { sec.heading = e.target.value; onChange(data.map((s) => ({ ...s }))); } }),
          cnt,
          onReviseSection ? h("button", { class: "btn-sm", title: t("revise_section_tip"), onClick: () => onReviseSection(i, sec.heading) }, icon("redo"), t("revise_section")) : null,
          h("button", { class: "ghost btn-sm", title: t("remove"), onClick: () => { data.splice(i, 1); onChange(data.map((s) => ({ ...s }))); render(); } }, "×")),
        textArea(sec.text, (v) => { sec.text = v; cnt.textContent = t("n_words_plain", { n: wordCount(v) }); onChange(data.map((s) => ({ ...s }))); }, 8)));
    });
    wrap.append(h("button", { class: "btn-sm", onClick: () => { data.push({ heading: "", text: "" }); onChange(data.map((s) => ({ ...s }))); render(); } }, icon("plus"), t("add_section")));
  };
  render();
  return wrap;
}

/**
 * Build the editor for a stage.
 * @param {string} stage
 * @param {object} draft working copy (mutated)
 * @param {object} ctx {findings, lang, prefixes, onDirty, onReviseSection}
 */
export function stageEditor(stage, draft, ctx) {
  const specs = SPECS[stage] || [];
  const byField = {};
  for (const f of ctx.findings || []) {
    const top = (f.field || "").split(".")[0];
    (byField[top] ||= []).push(f);
  }
  const root = h("div", {});
  for (const spec of specs) {
    const fs = byField[spec.key] || [];
    const lab = h("span", { class: "l" }, h("span", {}, t(spec.label)));
    const cnt = h("span", {});
    lab.append(cnt);
    const setCounter = (v) => { cnt.innerHTML = ""; const c = counter(spec, v); if (c) cnt.append(c); };
    const set = (v) => { draft[spec.key] = v; ctx.onDirty(); if (typeof v === "string") setCounter(v); };
    let input;
    switch (spec.type) {
      case "text": input = h("input", { value: draft[spec.key] || "", onInput: (e) => set(e.target.value) }); break;
      case "textarea": input = textArea(draft[spec.key], set, spec.rows || 4); setCounter(draft[spec.key] || ""); break;
      case "list": input = listEditor(draft[spec.key], set); break;
      case "nails": input = listEditor(draft[spec.key], set, { fixed: 3, prefixes: ctx.prefixes }); break;
      case "table": input = tableEditor(draft[spec.key], spec.cols, set); break;
      case "sections": input = sectionsEditor(draft[spec.key], set, ctx.onReviseSection); break;
      case "title": {
        const titles = (draft.titles || []).filter(Boolean);
        const inp = h("input", { value: draft.selected_title || "", onInput: (e) => set(e.target.value) });
        const sel = h("select", { onChange: (e) => { if (e.target.value) { inp.value = e.target.value; set(e.target.value); } } },
          h("option", { value: "" }, t("choose_title")), titles.map((x) => h("option", { value: x, selected: x === draft.selected_title }, x)));
        input = h("div", { class: "list-ed" }, sel, inp);
        break;
      }
      default: input = h("div", {});
    }
    root.append(h("div", { class: fs.some((f) => f.severity === "block") ? "field-bad" : "" },
      h("label", { class: "f" }, lab, spec.hint ? h("div", { class: "muted small", style: { marginBottom: "5px" } }, t(spec.hint)) : null, input,
        fs.map((f) => h("div", { class: `fmsg${f.severity === "warn" ? " w" : ""}` }, f.message)))));
  }
  return root;
}

export function findingsList(findings) {
  if (!findings.length) return h("div", { class: "allclear" }, "✓ ", t("all_clear"));
  const order = { block: 0, warn: 1 };
  return h("ul", { class: "findings" }, [...findings].sort((a, b) => order[a.severity] - order[b.severity]).map((f) =>
    h("li", { class: f.severity }, h("span", {}, f.severity === "block" ? "⛔" : "⚠"), h("span", {}, f.message), h("span", { class: "code" }, f.code))));
}
