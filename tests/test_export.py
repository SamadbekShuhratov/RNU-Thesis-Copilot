from docx import Document

from app.export.docx_writer import build_paper, build_thesis, count_pages
from app.export.submission import submission_markdown, submission_sheet
from app.reports.progress import progress_report
from tests.helpers import complete_project


def _text(path):
    d = Document(str(path))
    return "\n".join(p.text for p in d.paragraphs) + "\n".join(
        c.text for t in d.tables for r in t.rows for c in r.cells)


def test_thesis_docx(copilot, tmp_path):
    pid = complete_project(copilot, "course_work")
    st = copilot.raw_state(pid)
    out = build_thesis(st, tmp_path / "thesis.docx", model="mock")
    text = _text(out)
    assert "COURSE WORK" in text
    assert "Has been OFFERED" in text
    assert "REFERENCES" in text and "APPENDIX A" in text
    assert "[@" not in text and "[demo]" not in text          # citations rendered
    assert "(Author" in text                                     # APA in-text
    assert "RNU Study Department report 2024" in text            # fact source rendered


def test_paper_docx_ieee_and_pages(copilot, tmp_path):
    pid = complete_project(copilot, "conference_paper")
    st = copilot.raw_state(pid)
    st["project"]["citation_style"] = "ieee"
    out = build_paper(st, tmp_path / "paper.docx")
    text = _text(out)
    assert "Abstract" in text and "[1]" in text
    pages = count_pages(out)
    assert pages is None or pages >= 1
    sheet = submission_sheet(st)
    assert sheet["01_authors"][0]["corresponding_author_presenter"] is True
    md = submission_markdown(sheet)
    assert "02 Paper details" in md


def test_progress_email_languages(copilot):
    pid = complete_project(copilot, "course_work")
    st = copilot.raw_state(pid)
    ev = copilot.events(pid)
    for lang in ("en", "uz", "ru", "lv"):
        rep = progress_report(st, ev, 14, lang)
        assert rep["subject"] and len(rep["body"]) > 200
    assert "Hurmatli" in progress_report(st, ev, 14, "uz")["body"]
