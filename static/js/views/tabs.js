// Secondary workspace tabs: project & facts, references, implementation & experiments,
// Science Week submission, export & reports, history.
import { api, h, t, toast, guard, icon, store, fmtDate, download, copyText, wordCount, modal } from "../core.js";

const running = (data) => data.status === "running";

async function patch(pid, p, msg) {
  return guard(() => api.patch(`/api/projects/${pid}/state`, { patch: p, message: msg }), t("saved"));
}

function field(label, input, hint) {
  return h("label", { class: "f" }, h("span", { class: "l" }, h("span", {}, label)), hint ? h("div", { class: "muted small", style: { marginBottom: "5px" } }, hint) : null, input);
}

function bound(obj, key, type = "input", attrs = {}) {
  const el = h(type, { ...attrs, value: obj[key] ?? "", onInput: (e) => { obj[key] = e.target.value; } });
  return el;
}

// ── project details & facts ──────────────────────────────────────────────
function factsTab(root, data, ctx) {
  const st = data.state;
  const p = structuredClone(st.project);
  const facts = structuredClone(st.facts || []);
  const langs = store.meta.output_languages;
  const proj = h("div", { class: "card" },
    h("div", { class: "card-head" }, h("h3", {}, t("project_details")), h("div", { class: "spacer" }),
      h("button", { class: "primary", disabled: running(data), onClick: async () => { await patch(ctx.pid, { project: p }, "Project details updated"); ctx.reload(); } }, icon("save"), t("save"))),
    h("div", { class: "grid2" },
      field(t("f_name"), bound(p, "name")),
      field(t("f_language"), h("select", { onChange: (e) => { p.language = e.target.value; } },
        Object.entries(langs).map(([k, v]) => h("option", { value: k, selected: k === p.language }, `${v.native} (${v.name})`)))),
      field(t("f_topic"), bound(p, "topic", "textarea", { rows: 2 })),
      field(t("f_notes"), bound(p, "notes", "textarea", { rows: 2 })),
      field(t("f_object_hint"), bound(p, "object_hint")),
      field(t("f_subject_hint"), bound(p, "subject_hint")),
      field(t("f_field"), bound(p, "field")),
      field(t("f_citation_style"), h("select", { onChange: (e) => { p.citation_style = e.target.value; } },
        ["apa", "ieee"].map((s) => h("option", { value: s, selected: s === p.citation_style }, s.toUpperCase())))),
      field(t("f_student"), bound(p, "student_name")),
      field(t("f_student_email"), bound(p, "student_email", "input", { type: "email" })),
      field(t("f_group"), bound(p, "student_group")),
      field(t("f_supervisor"), bound(p, "supervisor")),
      field(t("f_supervisor_email"), bound(p, "supervisor_email", "input", { type: "email" })),
      field(t("f_university"), bound(p, "university")),
      field(t("f_faculty"), bound(p, "faculty")),
      field(t("f_programme"), bound(p, "programme")),
      field(t("f_city"), bound(p, "city")),
      field(t("f_year"), bound(p, "year"))));

  const tbody = h("tbody", {});
  const refKeys = (st.references || []).filter((r) => r.status === "verified").map((r) => r.key);
  const renderFacts = () => {
    tbody.replaceChildren(...facts.map((f, i) => h("tr", {},
      h("td", { class: "mono" }, f.id),
      h("td", {}, h("textarea", { rows: 2, value: f.text || "", onInput: (e) => { f.text = e.target.value; } })),
      h("td", {}, h("textarea", { rows: 2, value: f.source || "", placeholder: t("fact_source_ph"), onInput: (e) => { f.source = e.target.value; } })),
      h("td", {}, h("select", { onChange: (e) => { f.ref_key = e.target.value; } }, h("option", { value: "" }, "—"),
        refKeys.map((k) => h("option", { value: k, selected: k === f.ref_key }, k)))),
      h("td", {}, h("button", { class: "ghost btn-sm", onClick: () => { facts.splice(i, 1); renderFacts(); } }, "×")))));
  };
  renderFacts();
  const factsCard = h("div", { class: "card" },
    h("div", { class: "card-head" }, h("h3", {}, t("facts_title")), h("div", { class: "spacer" }),
      h("button", { onClick: () => { const n = facts.reduce((m, f) => Math.max(m, parseInt(String(f.id).slice(1)) || 0), 0) + 1; facts.push({ id: `F${n}`, text: "", source: "" }); renderFacts(); } }, icon("plus"), t("add_fact")),
      h("button", { class: "primary", disabled: running(data), onClick: async () => { await patch(ctx.pid, { facts }, "Facts updated"); ctx.reload(); } }, icon("save"), t("save"))),
    h("div", { class: "integrity" }, t("facts_hint")),
    h("table", { class: "data" }, h("thead", {}, h("tr", {}, h("th", {}, "ID"), h("th", {}, t("fact_text")), h("th", {}, t("fact_source")), h("th", {}, t("fact_ref")), h("th", {}))), tbody));
  root.replaceChildren(factsCard, proj);
}

// ── references ───────────────────────────────────────────────────────────
function refStatus(s) {
  const m = { verified: "ok", unverified: "", not_found: "block", mismatch: "block", error: "warn" };
  return h("span", { class: `badge ${m[s] || ""}` }, t(`rs_${s}`));
}

function authorsShort(r) {
  const a = (r.authors || []).map((x) => x.family).filter(Boolean);
  return a.length > 3 ? `${a.slice(0, 3).join(", ")} et al.` : a.join(", ");
}

function referencesTab(root, data, ctx) {
  const st = data.state;
  const refs = st.references || [];
  const results = h("div", {});
  const q = h("input", { placeholder: t("search_ph") });
  const src = h("select", {}, h("option", { value: "openalex" }, "OpenAlex"), h("option", { value: "semantic_scholar" }, "Semantic Scholar"));
  const search = async () => {
    results.replaceChildren(h("div", { class: "muted" }, h("span", { class: "spin" }), " ", t("searching")));
    try {
      const items = await api.post(`/api/projects/${ctx.pid}/refs/search`, { query: q.value, source: src.value, limit: 12 });
      results.replaceChildren(items.length ? h("table", { class: "data" }, h("tbody", {}, items.map((it) => h("tr", {},
        h("td", {}, h("div", { class: "ref-title" }, it.title), h("div", { class: "muted small" }, `${authorsShort(it)} (${it.year || "n.d."}) · ${it.venue || ""} · ${it.doi || ""} · ${t("cited_by", { n: it.cited_by_count || 0 })}`)),
        h("td", { style: { width: "110px" } }, h("button", { class: "btn-sm", onClick: async (e) => {
          e.currentTarget.disabled = true;
          const r = await guard(() => api.post(`/api/projects/${ctx.pid}/refs/add`, { candidate: it }));
          toast(r.created ? t("ref_added", { k: r.reference.key, s: t(`rs_${r.reference.status}`) }) : t("ref_exists", { k: r.reference.key }));
          ctx.reload();
        } }, icon("plus"), t("add"))))))) : h("div", { class: "muted" }, t("no_results")));
    } catch (e) { results.replaceChildren(h("div", { class: "notice bad" }, e.message)); }
  };
  q.addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
  const doi = h("input", { placeholder: "10.xxxx/…" });
  const bib = h("input", { type: "file", accept: ".bib,.txt" });

  const list = h("table", { class: "data" },
    h("thead", {}, h("tr", {}, h("th", {}, t("ref_key")), h("th", {}, t("ref_work")), h("th", {}, t("status")), h("th", {}, t("included")), h("th", {}))),
    h("tbody", {}, refs.map((r) => h("tr", {},
      h("td", { class: "mono" }, r.key),
      h("td", {}, h("div", { class: "ref-title" }, r.title), h("div", { class: "muted small" }, `${authorsShort(r)} (${r.year || "n.d."}) · ${r.venue || ""} `,
        r.doi ? h("a", { href: `https://doi.org/${r.doi}`, target: "_blank", rel: "noopener" }, r.doi) : (r.url ? h("a", { href: r.url, target: "_blank", rel: "noopener" }, "URL") : ""),
        r.verification?.score !== undefined ? ` · ${t("match")} ${Math.round(r.verification.score * 100)}%` : "", ` · ${r.source}`)),
      h("td", {}, refStatus(r.status)),
      h("td", {}, h("input", { type: "checkbox", checked: r.included !== false, disabled: running(data), onChange: (e) => guard(() => api.patch(`/api/projects/${ctx.pid}/refs/${encodeURIComponent(r.key)}`, { included: e.target.checked })).then(ctx.reload) })),
      h("td", { style: { whiteSpace: "nowrap" } },
        h("button", { class: "ghost btn-sm", title: t("verify"), disabled: running(data), onClick: () => guard(() => api.post(`/api/projects/${ctx.pid}/refs/verify`, { keys: [r.key] }), t("verified_done")).then(ctx.reload) }, icon("check")),
        h("button", { class: "ghost btn-sm danger", title: t("remove"), disabled: running(data), onClick: () => confirm(t("confirm_remove_ref", { k: r.key })) && guard(() => api.del(`/api/projects/${ctx.pid}/refs/${encodeURIComponent(r.key)}`)).then(ctx.reload) }, icon("trash")))))));

  const counts = refs.reduce((m, r) => { m[r.status] = (m[r.status] || 0) + 1; return m; }, {});
  root.replaceChildren(
    h("div", { class: "integrity" }, t("refs_integrity")),
    h("div", { class: "card" }, h("h3", {}, t("find_sources")),
      h("div", { class: "row" }, q, h("div", { style: { flex: "0 0 180px" } }, src), h("div", { style: { flex: "0 0 auto" } }, h("button", { class: "primary", onClick: search }, t("search")))),
      h("div", { style: { marginTop: "12px" } }, results)),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h3", {}, t("add_by_doi")), h("div", { class: "row" }, doi, h("div", { style: { flex: "0 0 auto" } },
        h("button", { onClick: async () => { const r = await guard(() => api.post(`/api/projects/${ctx.pid}/refs/add`, { doi: doi.value })); toast(t("ref_added", { k: r.reference.key, s: t(`rs_${r.reference.status}`) })); ctx.reload(); } }, icon("plus"), t("add"))))),
      h("div", { class: "card" }, h("h3", {}, t("import_bibtex")), h("div", { class: "row" }, bib, h("div", { style: { flex: "0 0 auto" } },
        h("button", { onClick: async () => { if (!bib.files[0]) return; const fd = new FormData(); fd.append("file", bib.files[0]); const r = await guard(() => api.form(`/api/projects/${ctx.pid}/refs/bibtex`, fd)); toast(t("bib_imported", { n: r.added.length })); ctx.reload(); } }, t("import")))),
        h("div", { class: "muted small" }, t("bibtex_hint")))),
    h("div", { class: "card" },
      h("div", { class: "card-head" }, h("h3", {}, t("library"), " ", h("span", { class: "muted" }, `(${refs.length})`)),
        Object.entries(counts).map(([s, n]) => h("span", {}, refStatus(s), " ", n)), h("div", { class: "spacer" }),
        h("button", { disabled: running(data) || !refs.length, onClick: () => guard(() => api.post(`/api/projects/${ctx.pid}/refs/verify`, {}), t("verified_done")).then(ctx.reload) }, icon("check"), t("verify_all"))),
      refs.length ? list : h("div", { class: "empty" }, t("no_refs"))));
}

// ── implementation & experiments ─────────────────────────────────────────
function chart(analysis) {
  const ms = analysis.metrics;
  const W = 300, H = 190, pad = 34;
  const wrap = h("div", { class: "chart", style: { display: "grid", gridTemplateColumns: `repeat(auto-fill,minmax(260px,1fr))`, gap: "12px" } });
  for (const m of ms) {
    const vals = [m.baseline, m.proposed];
    const max = Math.max(...vals.map((v) => v.ci95_high), 0) * 1.12 || 1;
    const bw = 70;
    const y = (v) => H - pad - (v / max) * (H - pad * 2);
    const bars = vals.map((v, i) => {
      const x = 70 + i * 120;
      return `<rect x="${x}" y="${y(v.mean)}" width="${bw}" height="${H - pad - y(v.mean)}" rx="4" fill="${i ? "var(--accent)" : "var(--line-2)"}"/>
        <line x1="${x + bw / 2}" x2="${x + bw / 2}" y1="${y(v.ci95_low)}" y2="${y(v.ci95_high)}" stroke="var(--ink-2)" stroke-width="1.5"/>
        <text x="${x + bw / 2}" y="${y(v.ci95_high) - 6}" text-anchor="middle">${v.mean}</text>
        <text x="${x + bw / 2}" y="${H - pad + 16}" text-anchor="middle">${i ? analysis.proposed_name : analysis.baseline_name}</text>`;
    }).join("");
    wrap.append(h("div", { class: "card", style: { margin: 0 } }, h("b", {}, m.metric, m.unit ? ` (${m.unit})` : ""),
      h("div", { html: `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${m.metric}"><line x1="40" x2="${W - 10}" y1="${H - pad}" y2="${H - pad}" stroke="var(--line-2)"/>${bars}</svg>` }),
      h("div", { class: "small" }, h("span", { class: `badge ${m.verdict === "improved_significant" ? "ok" : m.verdict.startsWith("worse") ? "block" : "warn"}` }, t(`v_${m.verdict}`)),
        ` Δ ${m.change_pct}% · p=${m.welch_p} · d=${m.cohen_d}`)));
  }
  return wrap;
}

function implementationTab(root, data, ctx) {
  const st = data.state;
  const impl = structuredClone(st.implementation || {});
  const ev = impl.evidence || {};
  const exp = st.experiments || {};
  const file = h("input", { type: "file", accept: ".csv,text/csv" });
  const cfg = structuredClone(exp.config || {});
  cfg.metrics ||= {};

  const implCard = h("div", { class: "card" },
    h("div", { class: "card-head" }, h("h3", {}, t("impl_title")), h("div", { class: "spacer" }),
      h("button", { disabled: running(data), onClick: async () => { await patch(ctx.pid, { implementation: impl }, "Implementation updated"); await guard(() => api.post(`/api/projects/${ctx.pid}/implementation/check`)); ctx.reload(); } }, icon("check"), t("save_and_check"))),
    h("div", { class: "integrity" }, t("impl_integrity")),
    h("div", { class: "grid2" },
      field(t("f_repo"), bound(impl, "repo_url", "input", { placeholder: "https://github.com/…" })),
      field(t("f_local_path"), bound(impl, "local_path", "input", { placeholder: "C:\\Users\\…\\my-project  /  ~/projects/my-app" }), t("h_local_path")),
      field(t("f_stack"), bound(impl, "stack", "input", { placeholder: "Python, FastAPI, React, PostgreSQL…" })),
      field(t("f_deployed"), bound(impl, "deployed_url", "input", { placeholder: "https://…" })),
      field(t("f_run_cmd"), bound(impl, "run_command", "input", { placeholder: "docker compose up -d" })),
      field(t("f_impl_desc"), bound(impl, "description", "textarea", { rows: 3 }))),
    field(t("f_deploy_steps"), bound(impl, "deploy_steps", "textarea", { rows: 4, class: "code" })),
    ev.checked_at ? h("dl", { class: "kv" },
      h("dt", {}, t("ev_code_files")), h("dd", {}, ev.code_files ? h("span", { class: "badge ok" }, ev.code_files) : h("span", { class: "badge block" }, "0")),
      h("dt", {}, t("ev_tests")), h("dd", {}, ev.has_tests ? "✓" : "—"),
      h("dt", {}, "Git / README"), h("dd", {}, `${ev.has_git ? "✓" : "—"} / ${ev.has_readme ? "✓" : "—"}`),
      h("dt", {}, t("ev_languages")), h("dd", {}, Object.entries(ev.languages || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "—"),
      h("dt", {}, t("ev_http")), h("dd", {}, ev.deployed_status ?? "—"),
      h("dt", {}, t("checked")), h("dd", {}, fmtDate(ev.checked_at))) : null);

  const analysis = exp.analysis;
  const expCard = h("div", { class: "card" },
    h("div", { class: "card-head" }, h("h3", {}, t("exp_title")), h("div", { class: "spacer" }),
      h("a", { class: "btn btn-sm", href: "/api/experiments/sample.csv" }, icon("download"), t("csv_format"))),
    h("div", { class: "integrity" }, t("exp_integrity")),
    exp.is_sample ? h("div", { class: "notice bad" }, t("exp_is_sample")) : null,
    h("div", { class: "row" }, file, h("div", { style: { flex: "0 0 auto" } },
      h("button", { class: "primary", disabled: running(data), onClick: async () => {
        if (!file.files[0]) return toast(t("choose_csv"), true);
        const fd = new FormData(); fd.append("file", file.files[0]);
        await guard(() => api.form(`/api/projects/${ctx.pid}/experiments`, fd), t("exp_uploaded"));
        ctx.reload();
      } }, t("upload")))),
    analysis ? h("div", { style: { marginTop: "14px" } },
      h("p", { class: "muted small" }, t("exp_summary", { rows: analysis.rows, file: exp.source_name || "CSV", b: analysis.baseline_name, p: analysis.proposed_name })),
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, ["metric_col", "direction", "baseline", "proposed", "change", "p_value", "effect", "unit"].map((k) => h("th", {}, t(k))))),
        h("tbody", {}, analysis.metrics.map((m) => {
          cfg.metrics[m.metric] ||= { direction: m.direction, unit: m.unit };
          return h("tr", {}, h("td", { class: "mono" }, m.metric),
            h("td", {}, h("select", { onChange: (e) => { cfg.metrics[m.metric].direction = e.target.value; } },
              ["lower", "higher"].map((d) => h("option", { value: d, selected: d === m.direction }, t(`dir_${d}`))))),
            h("td", {}, `${m.baseline.mean} ± ${m.baseline.std} (n=${m.baseline.n})`),
            h("td", {}, `${m.proposed.mean} ± ${m.proposed.std} (n=${m.proposed.n})`),
            h("td", {}, `${m.change_pct}%`), h("td", {}, m.welch_p), h("td", {}, m.cohen_d),
            h("td", {}, h("input", { value: m.unit || "", style: { width: "80px" }, onInput: (e) => { cfg.metrics[m.metric].unit = e.target.value; } })));
        }))),
      h("div", { style: { margin: "10px 0" } }, h("button", { class: "btn-sm", disabled: running(data), onClick: async () => { await guard(() => api.put(`/api/projects/${ctx.pid}/experiments/config`, { config: cfg }), t("saved")); ctx.reload(); } }, icon("save"), t("save_metric_cfg"))),
      chart(analysis)) : h("div", { class: "empty" }, t("no_measurements")));
  root.replaceChildren(implCard, expCard);
}

// ── RNU Science Week submission ──────────────────────────────────────────
function submissionTab(root, data, ctx) {
  const st = data.state;
  const sw = store.meta.science_week;
  const sub = structuredClone(st.submission || {});
  sub.authors ||= [];
  const abstract = st.conclusion?.abstract || "";
  const authorsBox = h("div", {});
  const renderAuthors = () => {
    authorsBox.replaceChildren(
      h("table", { class: "tbl-ed" }, h("thead", {}, h("tr", {}, h("th", {}, "#"), ["first_name", "surname", "affiliation", "email"].map((k) => h("th", {}, t(`a_${k}`) + " *")), h("th", {}, t("a_corresponding")), h("th", {}))),
        h("tbody", {}, sub.authors.map((a, i) => h("tr", {}, h("td", { class: "muted" }, `${i + 1}.`),
          ["first_name", "surname", "affiliation", "email"].map((k) => h("td", {}, h("input", { value: a[k] || "", type: k === "email" ? "email" : "text", onInput: (e) => { a[k] = e.target.value; } }))),
          h("td", { style: { textAlign: "center" } }, h("input", { type: "radio", name: "corr", checked: !!a.corresponding, style: { width: "auto" }, onChange: () => { sub.authors.forEach((x, j) => { x.corresponding = j === i; }); } })),
          h("td", {}, h("button", { class: "ghost btn-sm", onClick: () => { sub.authors.splice(i, 1); renderAuthors(); } }, "×")))))),
      h("button", { class: "btn-sm", disabled: sub.authors.length >= sw.max_authors, onClick: () => { sub.authors.push({ first_name: "", surname: "", affiliation: st.project.university || "", email: "", corresponding: !sub.authors.length }); renderAuthors(); } }, icon("plus"), t("add_author", { n: sw.max_authors })));
  };
  renderAuthors();
  const kw = h("input", { value: sub.keywords || (st.outline?.keywords || []).join("; "), placeholder: "resilience; critical infrastructure; digital systems", onInput: (e) => { sub.keywords = e.target.value; } });
  if (!sub.keywords) sub.keywords = kw.value;
  const tpl = h("input", { type: "file", accept: ".docx" });
  const tplState = h("span", { class: "muted small" });
  api.get(`/api/projects/${ctx.pid}/templates`).then((s) => { tplState.textContent = s.paper ? t("template_loaded") : t("template_missing"); });
  const pagesOut = h("span", { class: "muted small" });

  root.replaceChildren(
    h("div", { class: "integrity" }, t("sw_intro"), " ", h("a", { href: sw.template_url, target: "_blank", rel: "noopener" }, t("sw_template_link"))),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", {}, "01 · ", t("sw_authors")), h("div", { class: "spacer" }), h("span", { class: "muted small" }, t("sw_authors_hint", { n: sw.max_authors }))), authorsBox),
    h("div", { class: "card" }, h("h3", {}, "02 · ", t("sw_details")),
      field(t("sw_title"), h("input", { value: st.outline?.selected_title || "", disabled: true }), t("sw_title_hint")),
      field(t("sw_abstract"), h("textarea", { value: abstract, rows: 8, disabled: true }), `${wordCount(abstract)} / ${sw.abstract_max_words} ${t("words")} · ${t("sw_abstract_hint")}`)),
    h("div", { class: "card" }, h("h3", {}, "03 · ", t("sw_section")),
      field(t("sw_tech_section") + " *", h("select", { onChange: (e) => { sub.technical_section = e.target.value; } }, h("option", { value: "" }, t("select")),
        sw.technical_sections.map((s) => h("option", { value: s, selected: s === sub.technical_section }, s)))),
      field(t("sw_keywords") + " *", kw, t("sw_keywords_hint", { min: sw.keywords_min, max: sw.keywords_max }))),
    h("div", { class: "card" }, h("h3", {}, "04 · ", t("sw_file")),
      h("p", { class: "muted small" }, t("sw_file_hint", { min: sw.pages[0], max: sw.pages[1], mb: sw.max_file_mb })),
      h("div", { class: "row" }, tpl, h("div", { style: { flex: "0 0 auto" } }, h("button", { onClick: async () => {
        if (!tpl.files[0]) return; const fd = new FormData(); fd.append("file", tpl.files[0]);
        await guard(() => api.form(`/api/projects/${ctx.pid}/template/paper`, fd), t("template_loaded")); tplState.textContent = t("template_loaded");
      } }, t("upload_template")))), tplState,
      h("div", { class: "actions", style: { marginTop: "12px" } },
        h("button", { onClick: () => download(`/api/projects/${ctx.pid}/export/paper.docx`) }, icon("download"), t("download_paper")),
        h("button", { onClick: async () => { pagesOut.textContent = t("measuring"); const r = await guard(() => api.get(`/api/projects/${ctx.pid}/export/paper.docx?measure=1`)); pagesOut.textContent = r.pages ? t("pages_measured", { n: r.pages }) : t("no_libreoffice"); ctx.reload(); } }, t("measure_pages")), pagesOut)),
    h("div", { class: "card" }, h("h3", {}, "05 · ", t("sw_additional")),
      field(t("sw_presentation") + " *", h("div", { class: "actions" }, sw.presentation_types.map((pt) => h("label", { class: "check" }, h("input", { type: "radio", name: "ptype", checked: sub.presentation_type === pt, onChange: () => { sub.presentation_type = pt; } }), pt)))),
      field(t("sw_notes"), bound(sub, "notes", "textarea", { rows: 3 }))),
    h("div", { class: "actions" }, h("div", { class: "spacer" }),
      h("button", { onClick: () => download(`/api/projects/${ctx.pid}/export/submission?format=md`) }, icon("download"), t("download_sheet")),
      h("button", { class: "primary", disabled: running(data), onClick: async () => { await patch(ctx.pid, { submission: sub }, "Submission form updated"); ctx.reload(); } }, icon("save"), t("save"))));
}

// ── export & reports ─────────────────────────────────────────────────────
function exportTab(root, data, ctx) {
  const st = data.state;
  const days = h("input", { type: "number", value: 14, min: 1, max: 90, style: { width: "90px" } });
  const lang = h("select", {}, store.meta.ui_languages.map((l) => h("option", { value: l, selected: l === store.lang }, l.toUpperCase())));
  const subj = h("input", { readonly: true });
  const bodyTa = h("textarea", { rows: 18, readonly: true, class: "code" });
  const to = h("span", { class: "muted small" });
  const gen = async () => {
    const r = await guard(() => api.get(`/api/projects/${ctx.pid}/export/progress?days=${days.value}&lang=${lang.value}`));
    subj.value = r.subject; bodyTa.value = r.body; to.textContent = r.to ? `→ ${r.to}` : t("no_supervisor_email");
  };
  const compBox = h("div", {});
  const loadComp = async () => {
    const c = await api.get(`/api/projects/${ctx.pid}/export/compliance`);
    compBox.replaceChildren(...Object.entries(c.findings).map(([s, fs]) => h("div", { style: { marginBottom: "10px" } },
      h("b", {}, t(`stage_${s}`)), " ", h("span", { class: "badge" }, t(`ss_${st.stage_status[s] || "pending"}`)),
      h("ul", { class: "findings", style: { marginTop: "6px" } }, fs.length ? fs.map((f) => h("li", { class: f.severity }, f.message)) : h("li", { class: "allclear" }, "✓ " + t("all_clear"))))));
  };
  const paper = st.project.doc_type === "conference_paper";
  root.replaceChildren(
    h("div", { class: "card" }, h("h3", {}, t("downloads")),
      h("div", { class: "actions" },
        paper ? h("button", { class: "primary", onClick: () => download(`/api/projects/${ctx.pid}/export/paper.docx`) }, icon("download"), t("download_paper"))
          : h("button", { class: "primary", onClick: () => download(`/api/projects/${ctx.pid}/export/thesis.docx`) }, icon("download"), t("download_thesis")),
        paper ? h("button", { onClick: () => download(`/api/projects/${ctx.pid}/export/submission?format=md`) }, icon("download"), t("download_sheet")) : null,
        h("button", { onClick: () => download(`/api/projects/${ctx.pid}/export/project.json`) }, icon("download"), t("download_json"))),
      h("p", { class: "muted small" }, t("export_hint"))),
    h("div", { class: "card" },
      h("div", { class: "card-head" }, h("h3", {}, t("progress_email")), h("div", { class: "spacer" }), h("span", { class: "muted small" }, t("days")), days, lang, h("button", { class: "primary", onClick: gen }, t("generate"))),
      h("p", { class: "muted small" }, t("progress_hint")),
      field(t("subject"), subj), field(t("body"), bodyTa), to,
      h("div", { class: "actions", style: { marginTop: "8px" } },
        h("button", { onClick: () => copyText(`${subj.value}\n\n${bodyTa.value}`) }, t("copy")),
        h("button", { onClick: () => { if (!bodyTa.value) return; const email = st.project.supervisor_email || ""; location.href = `mailto:${email}?subject=${encodeURIComponent(subj.value)}&body=${encodeURIComponent(bodyTa.value)}`; } }, t("open_mail")))),
    h("div", { class: "card" }, h("div", { class: "card-head" }, h("h3", {}, t("compliance_report")), h("div", { class: "spacer" }), h("button", { onClick: loadComp }, t("refresh"))), compBox));
  loadComp();
}

// ── history ──────────────────────────────────────────────────────────────
async function historyTab(root, data, ctx) {
  root.replaceChildren(h("div", { class: "muted" }, h("span", { class: "spin" })));
  const hist = await api.get(`/api/projects/${ctx.pid}/history`);
  const evs = await api.get(`/api/projects/${ctx.pid}/events?since=0`);
  root.replaceChildren(
    h("div", { class: "card" }, h("h3", {}, t("checkpoints")), h("p", { class: "muted small" }, t("checkpoints_hint")),
      h("table", { class: "data" }, h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, t("time")), h("th", {}, t("node")), h("th", {}, t("stage")), h("th", {}, t("next")), h("th", {}))),
        h("tbody", {}, hist.slice(0, 150).map((c) => h("tr", {}, h("td", { class: "mono" }, c.seq), h("td", {}, fmtDate(c.created_at)), h("td", { class: "mono" }, c.node || "—"),
          h("td", {}, c.stage ? t(`stage_${c.stage}`) : "—"), h("td", { class: "mono" }, c.waiting ? "⏸ human_review" : (c.next_node || "■")),
          h("td", {}, h("button", { class: "btn-sm", disabled: running(data), onClick: () => {
            modal(t("restore_q"), h("p", {}, t("restore_warning", { n: c.seq })), [{ label: t("restore"), primary: true, onClick: async () => { await api.post(`/api/projects/${ctx.pid}/rollback`, { seq: c.seq }); toast(t("restored")); ctx.reload(); } }]);
          } }, t("restore")))))))),
    h("div", { class: "card" }, h("h3", {}, t("event_log")),
      h("table", { class: "data" }, h("tbody", {}, [...evs].reverse().slice(0, 400).map((e) => h("tr", {}, h("td", { class: "muted small", style: { whiteSpace: "nowrap" } }, fmtDate(e.ts)),
        h("td", {}, h("span", { class: "badge" }, e.kind)), h("td", {}, e.stage ? t(`stage_${e.stage}`) : ""), h("td", {}, e.message)))))));
}

export const TABS = {
  facts: factsTab,
  references: referencesTab,
  implementation: implementationTab,
  submission: submissionTab,
  export: exportTab,
  history: historyTab,
};
