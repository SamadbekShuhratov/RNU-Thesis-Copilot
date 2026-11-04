// Core helpers: API client, DOM builder, i18n, toasts, modals, text counters.
import { STRINGS } from "./i18n.js";

export const store = {
  lang: localStorage.getItem("ui_lang") || "uz",
  meta: null,
  settings: null,
};

export function t(key, params = {}) {
  const table = STRINGS[store.lang] || STRINGS.en;
  let s = table[key] ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, v);
  return s;
}

export function setLang(lang) {
  store.lang = lang;
  try { localStorage.setItem("ui_lang", lang); } catch (_) { /* private mode */ }
  document.documentElement.lang = lang;
}

// ── API ────────────────────────────────────────────────────────────────
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, url, body, isForm = false) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    if (isForm) opts.body = body;
    else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
  }
  const sep = url.includes("?") ? "&" : "?";
  const res = await fetch(`${url}${sep}lang=${store.lang}`, opts);
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    if (!res.ok) throw new ApiError(await res.text(), res.status);
    return res;
  }
  const json = await res.json();
  if (!json.ok) throw new ApiError(json.error || res.statusText, res.status);
  return json.data;
}

export const api = {
  get: (u) => request("GET", u),
  post: (u, b = {}) => request("POST", u, b),
  put: (u, b = {}) => request("PUT", u, b),
  patch: (u, b = {}) => request("PATCH", u, b),
  del: (u) => request("DELETE", u),
  form: (u, fd) => request("POST", u, fd, true),
};

// ── DOM ────────────────────────────────────────────────────────────────
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k === "html") el.innerHTML = v;
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export const svgIcon = (path) => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.8"); s.setAttribute("stroke-linecap", "round"); s.setAttribute("stroke-linejoin", "round");
  s.innerHTML = path;
  return s;
};

export const ICONS = {
  projects: '<path d="M3 7h18M3 12h18M3 17h12"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  guide: '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z"/><path d="M8 7h8M8 11h6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  play: '<path d="M6 4l14 8-14 8z"/>',
  check: '<path d="M5 12l5 5L20 7"/>',
  redo: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>',
  save: '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8"/><path d="M8 21v-7h8v7"/>',
  download: '<path d="M12 3v12M7 10l5 5 5-5"/><path d="M5 21h14"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14"/>',
};

export function icon(name) { return svgIcon(ICONS[name] || ""); }

export function toast(message, bad = false) {
  const el = h("div", { class: `toast${bad ? " bad" : ""}` }, message);
  document.getElementById("toasts").append(el);
  setTimeout(() => el.remove(), bad ? 6500 : 3500);
}

export function modal(title, content, buttons = []) {
  const root = document.getElementById("modal-root");
  const close = () => { root.innerHTML = ""; };
  const foot = h("div", { class: "foot" },
    h("button", { onClick: close }, t("cancel")),
    ...buttons.map((b) => h("button", {
      class: b.primary ? "primary" : "", onClick: async (ev) => {
        ev.currentTarget.disabled = true;
        try { if ((await b.onClick()) !== false) close(); }
        catch (e) { toast(e.message, true); }
        finally { if (ev.currentTarget) ev.currentTarget.disabled = false; }
      },
    }, b.label)));
  const bg = h("div", { class: "modal-bg", onClick: (e) => { if (e.target === bg) close(); } },
    h("div", { class: "modal", role: "dialog", "aria-modal": "true" }, h("h2", {}, title), content, foot));
  root.innerHTML = "";
  root.append(bg);
  return close;
}

export async function guard(fn, okMessage) {
  try {
    const r = await fn();
    if (okMessage) toast(okMessage);
    return r;
  } catch (e) {
    toast(e.message || String(e), true);
    throw e;
  }
}

// ── text metrics (mirror of the server validators, for live hints) ─────
const ABBR = new Set(["e.g", "i.e", "etc", "et al", "fig", "no", "vs", "cf", "dr", "prof", "pp", "vol", "т.е", "т.д", "рис", "см", "piem"]);
export function sentences(text) {
  const s = (text || "").replace(/\s+/g, " ").trim();
  if (!s) return 0;
  let count = 0, start = 0;
  const re = /([.!?…]+)(['"”»)\]]*)(\s+)/g;
  let m;
  while ((m = re.exec(s))) {
    const before = s.slice(start, m.index);
    const last = (before.split(/[\s(]/).pop() || "").toLowerCase();
    const next = s[m.index + m[0].length] || "";
    if (m[1] === "." && (ABBR.has(last) || (last.length === 1 && /\p{L}/u.test(last)))) continue;
    if (next && /\p{Ll}/u.test(next)) continue;
    count++; start = m.index + m[0].length;
  }
  if (s.slice(start).trim()) count++;
  return count;
}
export function wordCount(text) {
  return ((text || "").replace(/\[@[^\]]+\]/g, "").match(/[\p{L}][\p{L}\p{M}'’\-]*/gu) || []).length;
}

export function fmtDate(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString(store.lang === "en" ? "en-GB" : store.lang);
}

export function download(url) {
  const sep = url.includes("?") ? "&" : "?";
  const a = h("a", { href: `${url}${sep}lang=${store.lang}`, download: "" });
  document.body.append(a); a.click(); a.remove();
}

export function copyText(text) {
  navigator.clipboard?.writeText(text).then(() => toast(t("copied")), () => toast(t("copy_failed"), true));
}
