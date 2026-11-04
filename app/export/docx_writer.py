"""DOCX export: RNU thesis / course work and RNU Science Week paper."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ..experiments.analysis import chart_png
from ..references.formatting import bibliography, render_citations
from ..reports.progress import authorship
from ..rules import rules
from .labels import labels

FACT_RE = re.compile(r"\((F\d+)\)")


class Writer:
    def __init__(self, state: dict[str, Any], template: Path | None = None, paper: bool = False):
        self.state = state
        self.p = state.get("project", {})
        self.L = labels(self.p.get("language", "en"))
        self.paper = paper
        fmt = rules()["formatting"]
        self.style = self.p.get("citation_style", fmt["default_citation_style"])
        self.refs = {r["key"]: r for r in state.get("references", []) if r.get("included", True)}
        texts = [self._flat(state.get(k)) for k in ("chapter1", "literature", "theory", "practical", "conclusion")]
        self.bib = bibliography(list(self.refs.values()), self.style, texts)
        self.numbers = {e["key"]: e["number"] for e in self.bib}
        self.facts = {f.get("id"): f for f in state.get("facts", [])}
        self.table_no = 0
        self.figure_no = 0
        if template and Path(template).exists():
            self.doc = Document(str(template))
            self._clear_body()
            self.from_template = True
        else:
            self.doc = Document()
            self.from_template = False
            self._setup_styles(fmt)

    # ── setup ──────────────────────────────────────────────────────────────
    @staticmethod
    def _flat(v: Any) -> str:
        from ..validators.text import flatten_text
        return flatten_text(v)

    def _clear_body(self) -> None:
        body = self.doc.element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)

    def _setup_styles(self, fmt: dict[str, Any]) -> None:
        size = fmt["paper_font_size_pt"] if self.paper else fmt["font_size_pt"]
        margins = fmt["paper_margins_cm"] if self.paper else fmt["margins_cm"]
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.top_margin, sec.bottom_margin = Cm(margins["top"]), Cm(margins["bottom"])
        sec.left_margin, sec.right_margin = Cm(margins["left"]), Cm(margins["right"])
        normal = self.doc.styles["Normal"]
        normal.font.size = Pt(size)
        self._set_font(normal, fmt["font"])
        pf = normal.paragraph_format
        pf.line_spacing = 1.0 if self.paper else fmt["line_spacing"]
        pf.space_after = Pt(4 if self.paper else 6)
        for name, sz in (("Heading 1", size + 2), ("Heading 2", size + 1), ("Heading 3", size), ("Title", size + 6)):
            st = self.doc.styles[name]
            st.font.name = fmt["font"]
            st.font.size = Pt(sz)
            st.font.bold = True
            st.font.color.rgb = RGBColor(0, 0, 0)
            self._set_font(st, fmt["font"])
            st.paragraph_format.space_before = Pt(12 if name == "Heading 1" else 8)
            st.paragraph_format.space_after = Pt(6)
            st.paragraph_format.keep_with_next = True
        self._add_page_numbers()

    @staticmethod
    def _set_font(style, font: str) -> None:
        style.font.name = font
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
            rfonts.attrib.pop(qn(attr), None)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), font)

    def _add_page_numbers(self) -> None:
        footer = self.doc.sections[0].footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._field(footer, "PAGE")

    @staticmethod
    def _field(paragraph, instr: str) -> None:
        run = paragraph.add_run()
        for tag, text in (("begin", None), (None, instr), ("separate", None), ("end", None)):
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)

    # ── primitives ─────────────────────────────────────────────────────────
    def text(self, s: str) -> str:
        s = s or ""

        def fact(m: re.Match) -> str:
            f = self.facts.get(m.group(1))
            if not f:
                return m.group(0)
            if f.get("ref_key") and f["ref_key"] in self.refs:
                return render_citations(f"[@{f['ref_key']}]", self.refs, self.style, self.numbers)
            return f"({f.get('source', '').strip()})" if f.get("source") else ""
        s = FACT_RE.sub(fact, s)
        s = render_citations(s, self.refs, self.style, self.numbers)
        return re.sub(r"\[demo\]\s*", "", s)

    def h(self, text: str, level: int = 1) -> None:
        style = f"Heading {level}"
        try:
            self.doc.add_paragraph(text, style=style)
        except KeyError:
            p = self.doc.add_paragraph()
            r = p.add_run(text)
            r.bold = True

    def para(self, text: str, bold_label: str | None = None, align_justify: bool = True) -> None:
        for chunk in [c for c in re.split(r"\n\s*\n", self.text(text)) if c.strip()]:
            p = self.doc.add_paragraph()
            if bold_label:
                p.add_run(bold_label + ": ").bold = True
                bold_label = None
            p.add_run(chunk.strip())
            if align_justify:
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    def bullets(self, items: list[str], numbered: bool = False) -> None:
        # Explicit markers keep numbering restarting at 1 for every list.
        for i, it in enumerate(items, start=1):
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.9)
            p.paragraph_format.first_line_indent = Cm(-0.6)
            p.paragraph_format.space_after = Pt(2)
            p.add_run(f"{i}.\t" if numbered else "•\t")
            p.add_run(self.text(str(it)))
            p.paragraph_format.tab_stops.add_tab_stop(Cm(0.9))

    def table(self, caption: str, headers: list[str], rows: list[list[str]]) -> None:
        if not rows:
            return
        self.table_no += 1
        cap = self.doc.add_paragraph()
        cap.add_run(f"{self.L['table']} {self.table_no}. {caption}").italic = True
        t = self.doc.add_table(rows=1, cols=len(headers))
        try:
            t.style = "Table Grid"
        except (KeyError, ValueError):
            pass
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, htxt in enumerate(headers):
            cell = t.rows[0].cells[i]
            cell.text = ""
            cell.paragraphs[0].add_run(htxt).bold = True
        for row in rows:
            cells = t.add_row().cells
            for i, val in enumerate(row):
                cells[i].text = self.text(str(val))
        for row in t.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    for run in par.runs:
                        run.font.size = Pt(9 if self.paper else 10)
        self.doc.add_paragraph()

    def figure(self, png: bytes, caption: str, width_cm: float = 15.0) -> None:
        self.figure_no += 1
        self.doc.add_picture(io.BytesIO(png), width=Cm(width_cm))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.add_run(f"{self.L['figure']} {self.figure_no}. {caption}").italic = True

    def page_break(self) -> None:
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def sections(self, items: list[dict], prefix: str, level: int = 2, start: int = 1) -> int:
        n = start
        for sec in items or []:
            self.h(f"{prefix}.{n}. {sec.get('heading', '')}" if prefix else sec.get("heading", ""), level)
            self.para(sec.get("text", ""))
            n += 1
        return n

    def bibliography_block(self, heading: str, level: int = 1) -> None:
        self.h(heading, level)
        for e in self.bib:
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0 if self.style == "apa" else 0.8)
            p.paragraph_format.first_line_indent = Cm(-1.0 if self.style == "apa" else -0.8)
            for txt, italic in e["segments"]:
                r = p.add_run(txt)
                r.italic = italic
                if self.paper:
                    r.font.size = Pt(9)

    def results_table(self) -> None:
        analysis = (self.state.get("experiments") or {}).get("analysis")
        if not analysis:
            return
        L = self.L
        rows = []
        for m in analysis["metrics"]:
            unit = f" {m['unit']}" if m.get("unit") else ""
            rows.append([m["metric"] + unit,
                         f"{m['baseline']['mean']} ± {m['baseline']['std']} (n={m['baseline']['n']})",
                         f"{m['proposed']['mean']} ± {m['proposed']['std']} (n={m['proposed']['n']})",
                         f"{m['change_pct']}%", str(m["welch_p"]), str(m["cohen_d"])])
        self.table(L["results"], [L["metric_col"], f"{L['baseline']} ({analysis['baseline_name']})",
                                  f"{L['proposed']} ({analysis['proposed_name']})", L["change"], L["p_value"],
                                  L["effect"]], rows)
        try:
            self.figure(chart_png(analysis), L["figure_results"], 8.5 if self.paper else 15.0)
        except Exception:  # noqa: BLE001 - matplotlib missing fonts etc.
            pass

    def save(self, path: Path) -> Path:
        # Ask Word to refresh the table of contents / page fields when the file is opened.
        settings_el = self.doc.settings.element
        if settings_el.find(qn("w:updateFields")) is None:
            upd = OxmlElement("w:updateFields")
            upd.set(qn("w:val"), "true")
            settings_el.append(upd)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path))
        return path


# ── thesis / course work ──────────────────────────────────────────────────
def build_thesis(state: dict[str, Any], path: Path, template: Path | None = None, model: str = "") -> Path:
    w = Writer(state, template, paper=False)
    L, p = w.L, w.p
    o = state.get("outline") or {}
    c1 = state.get("chapter1") or {}
    lit = state.get("literature") or {}
    th = state.get("theory") or {}
    pr = state.get("practical") or {}
    con = state.get("conclusion") or {}
    impl = state.get("implementation") or {}

    # title page
    for line in (p.get("university"), p.get("faculty"), p.get("programme")):
        if line:
            par = w.doc.add_paragraph(line)
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for _ in range(6):
        w.doc.add_paragraph()
    t = w.doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run(L.get(p.get("doc_type"), L["course_work"])).bold = True
    t2 = w.doc.add_paragraph()
    t2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t2.add_run(o.get("selected_title") or p.get("name", ""))
    r.bold = True
    r.font.size = Pt(16)
    for _ in range(6):
        w.doc.add_paragraph()
    for label, value in ((L["author"], f"{p.get('student_name', '')} {p.get('student_group', '')}".strip()),
                         (L["supervisor"], p.get("supervisor", ""))):
        par = w.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        par.add_run(f"{label}: ").bold = True
        par.add_run(value)
    for _ in range(4):
        w.doc.add_paragraph()
    city = w.doc.add_paragraph(f"{p.get('city', '')} {p.get('year', '')}")
    city.alignment = WD_ALIGN_PARAGRAPH.CENTER
    w.page_break()

    # abstract
    if con.get("abstract"):
        w.h(L["abstract"], 1)
        w.para(con["abstract"])
        w.para(", ".join(o.get("keywords", [])), bold_label=L["keywords"])
        w.page_break()

    # contents
    w.h(L["contents"], 1)
    w._field(w.doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u')
    w.page_break()

    # chapter 1
    w.h(f"1. {L['ch1']}", 1)
    w.h(f"1.1. {L['topicality']}", 2)
    w.para(c1.get("topicality", ""))
    w.h(f"1.2. {L['problem']}", 2)
    w.para(c1.get("problem_formulation", ""))
    w.h(f"1.3. {L['object_subject']}", 2)
    w.para(o.get("object", ""), bold_label=L["object"])
    w.para(o.get("subject", ""), bold_label=L["subject"])
    w.h(f"1.4. {L['aim_tasks']}", 2)
    w.para(o.get("goal", ""), bold_label=L["aim"])
    w.bullets(o.get("tasks", []), numbered=True)
    w.h(f"1.5. {L['nails']}", 2)
    w.bullets(o.get("nails", []), numbered=True)
    if c1.get("research_questions"):
        w.h(f"1.6. {L['rq']}", 2)
        w.bullets(c1["research_questions"])
    w.h(f"1.7. {L['methods']}", 2)
    w.para(c1.get("methods", ""))
    w.h(f"1.8. {L['planned']}", 2)
    w.table(L["planned"], [L["result"], L["metric"], L["beneficiary"]],
            [[r.get("result", ""), r.get("metric", ""), r.get("beneficiary", "")]
             for r in c1.get("planned_results", []) if isinstance(r, dict)])
    w.h(f"1.9. {L['novelty']}", 2)
    w.para(c1.get("novelty", ""))
    n = w.sections(c1.get("sections", []), "1", start=10)
    w.h(f"1.{n}. {L['structure']}", 2)
    w.para(c1.get("structure", ""))
    w.h(L["ch_conclusion"], 2)
    w.para(c1.get("conclusion", ""))
    w.page_break()

    # chapter 2
    w.h(f"2. {L['ch2']}", 1)
    n = w.sections(lit.get("sections", []), "2")
    w.h(f"2.{n}. {L['comparison']}", 2)
    w.table(L["comparison"], [L["approach"], L["sources"], L["strengths"], L["limitations"]],
            [[c.get("approach", ""), c.get("sources", ""), c.get("strengths", ""), c.get("limitations", "")]
             for c in lit.get("comparison", []) if isinstance(c, dict)])
    n += 1
    w.h(f"2.{n}. {L['gaps']}", 2)
    w.bullets(lit.get("gaps", []))
    if lit.get("conclusion"):
        w.para(lit["conclusion"], bold_label=L["lit_summary"])
    n += 1
    if th:
        w.h(f"2.{n}. {L['concepts']}", 2)
        w.table(L["concepts"], [L["term"], L["definition"]],
                [[c.get("term", ""), c.get("definition", "")] for c in th.get("concepts", []) if isinstance(c, dict)])
        n += 1
        w.h(f"2.{n}. {L['frameworks']}", 2)
        for fw in th.get("frameworks", []):
            if isinstance(fw, dict):
                w.para(f"{fw.get('description', '')} {fw.get('how_used', '')}", bold_label=fw.get("name", ""))
        n = w.sections(th.get("sections", []), "2", start=n + 1)
        w.h(f"2.{n}. {L['gap_solution']}", 2)
        w.table(L["gap_solution"], [L["gap"], L["solution"]],
                [[m.get("gap", ""), m.get("solution_element", "")] for m in th.get("gap_to_solution", [])
                 if isinstance(m, dict)])
        w.h(L["ch_conclusion"], 2)
        w.para(th.get("conclusion", ""))
    w.page_break()

    # chapter 3
    w.h(f"3. {L['ch3']}", 1)
    w.h(f"3.1. {L['architecture']}", 2)
    w.para(pr.get("architecture", ""))
    w.table(L["components"], [L["component"], L["responsibility"], L["technology"]],
            [[c.get("name", ""), c.get("responsibility", ""), c.get("technology", "")]
             for c in pr.get("components", []) if isinstance(c, dict)])
    w.h(f"3.2. {L['data_flow']}", 2)
    w.para(pr.get("data_flow", ""))
    w.h(f"3.3. {L['deployment']}", 2)
    w.bullets(pr.get("deployment_steps", []), numbered=True)
    n = w.sections(pr.get("sections", []), "3", start=4)
    w.h(f"3.{n}. {L['experiment']}", 2)
    w.para(pr.get("experiment_design", ""))
    w.h(f"3.{n + 1}. {L['results']}", 2)
    w.results_table()
    w.para(pr.get("results_discussion", ""))
    w.h(L["ch_conclusion"], 2)
    w.para(pr.get("conclusion", ""))
    w.page_break()

    # general conclusion
    w.h(L["general_conclusion"], 1)
    w.para(con.get("general_conclusion", ""))
    if con.get("limitations"):
        w.para(con["limitations"], bold_label=L["lim"])
    if con.get("future_work"):
        w.para(con["future_work"], bold_label=L["future"])
    w.page_break()

    w.bibliography_block(L["references"], 1)
    w.page_break()

    # appendices
    w.h(L["appendix_ai"], 1)
    w.para(L["ai_text"].format(model=model or "local LLM"))
    auth = authorship(state)
    w.table(L["changed"], [L["stage"], L["ai_words"], L["final_words"], L["changed"]],
            [[s, str(a["ai_words"]), str(a["final_words"]), f"{a['changed_pct']}%"] for s, a in auth.items()])
    w.h(L["appendix_impl"], 1)
    ev = impl.get("evidence") or {}
    rows = [[L["repo"], impl.get("repo_url", "")], [L["local"], impl.get("local_path", "")],
            [L["run"], impl.get("run_command", "")], [L["deployed"], impl.get("deployed_url", "")],
            [L["evidence"], f"{ev.get('code_files', 0)} code files; tests: {ev.get('has_tests')}; "
                            f"git: {ev.get('has_git')}; HTTP: {ev.get('deployed_status', '—')}"]]
    w.table(L["evidence"], ["", ""], [r for r in rows if r[1]])
    return w.save(path)


# ── RNU Science Week paper ────────────────────────────────────────────────
def build_paper(state: dict[str, Any], path: Path, template: Path | None = None) -> Path:
    w = Writer(state, template, paper=True)
    L = w.L
    o = state.get("outline") or {}
    c1 = state.get("chapter1") or {}
    lit = state.get("literature") or {}
    pr = state.get("practical") or {}
    con = state.get("conclusion") or {}
    sub = state.get("submission") or {}

    title = w.doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = title.add_run(o.get("selected_title", ""))
    tr.bold = True
    tr.font.size = Pt(14)

    authors = sub.get("authors", [])
    affiliations: list[str] = []
    for a in authors:
        if a.get("affiliation") and a["affiliation"] not in affiliations:
            affiliations.append(a["affiliation"])
    ap = w.doc.add_paragraph()
    ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, a in enumerate(authors):
        ap.add_run(f"{a.get('first_name', '')} {a.get('surname', '')}".strip())
        sup = ap.add_run(str(affiliations.index(a["affiliation"]) + 1) if a.get("affiliation") in affiliations else "")
        sup.font.superscript = True
        if a.get("corresponding"):
            star = ap.add_run("*")
            star.font.superscript = True
        if i < len(authors) - 1:
            ap.add_run(", ")
    for i, aff in enumerate(affiliations, start=1):
        par = w.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        s = par.add_run(str(i))
        s.font.superscript = True
        par.add_run(" " + aff).italic = True
    corr = [a for a in authors if a.get("corresponding")]
    if corr:
        par = w.doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        par.add_run(f"*{L['corresponding']}: {corr[0].get('email', '')}").font.size = Pt(9)

    w.para(con.get("abstract", ""), bold_label=L["abstract"].capitalize())
    kws = sub.get("keywords") or "; ".join(o.get("keywords", []))
    w.para(kws, bold_label=L["keywords"])

    w.h(f"1. {L['intro']}", 1)
    w.para(c1.get("topicality", ""))
    w.para(c1.get("problem_formulation", ""))
    w.para(o.get("goal", ""), bold_label=L["aim"])
    w.bullets(o.get("nails", []), numbered=True)
    for sec in c1.get("sections", []):
        w.para(sec.get("text", ""))

    w.h(f"2. {L['related']}", 1)
    for sec in lit.get("sections", []):
        w.para(sec.get("text", ""))
    if lit.get("gaps"):
        w.bullets(lit["gaps"])

    w.h(f"3. {L['method']}", 1)
    w.para(pr.get("architecture", ""))
    w.table(L["components"], [L["component"], L["responsibility"], L["technology"]],
            [[c.get("name", ""), c.get("responsibility", ""), c.get("technology", "")]
             for c in pr.get("components", []) if isinstance(c, dict)])
    w.para(pr.get("experiment_design", ""))
    for sec in pr.get("sections", []):
        w.para(sec.get("text", ""))

    w.h(f"4. {L['results_sec']}", 1)
    w.results_table()
    w.para(pr.get("results_discussion", ""))

    w.h(f"5. {L['conclusions']}", 1)
    w.para(con.get("general_conclusion", ""))
    if con.get("future_work"):
        w.para(con["future_work"])

    w.bibliography_block(L["references"].capitalize(), 1)
    return w.save(path)


# ── exact page count via LibreOffice ──────────────────────────────────────
def soffice_path() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if Path(p).exists():
            return p
    return None


def count_pages(docx_path: Path, timeout: int = 120) -> int | None:
    exe = soffice_path()
    if not exe:
        return None
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(docx_path)],
                           check=True, capture_output=True, timeout=timeout)
        except (subprocess.SubprocessError, OSError):
            return None
        pdf = Path(tmp) / (docx_path.stem + ".pdf")
        if not pdf.exists():
            return None
        return len(PdfReader(str(pdf)).pages)
