"""Unit tests for the RNU Output Constraints Matrix (Employee 1)."""
from app.experiments.analysis import SAMPLE_CSV, analyze, parse_csv
from app.references.formatting import apa, ieee, plain, render_citations
from app.references.sources import parse_bibtex, title_similarity
from app.validators.rules import (
    check_bounded, check_goal, check_nails, check_practical, check_references, check_submission,
)
from app.validators.text import citation_keys, count_sentences, has_statistic, split_sentences


def codes(findings):
    return {f["code"] for f in findings}


def test_sentence_splitter_handles_abbreviations_and_decimals():
    text = "E.g. latency fell to 3.5 s in Fig. 2 by J. Smith et al. today. Второе предложение. Trešais!"
    assert count_sentences(text) == 3
    assert split_sentences("One [@a2020]. Two.") == ["One [@a2020].", "Two."]


def test_goal_rules():
    assert "GOAL_VAGUE" in codes(check_goal("Analyze information systems.", "en"))
    assert "GOAL_SENTENCES" in codes(check_goal("Develop a system for RNU students. Reduce errors by 30% by 2027.", "en"))
    good = "To develop and deploy a local assistant for RNU students that reduces formatting errors by 40% by June 2027."
    assert not [f for f in check_goal(good, "en") if f["severity"] == "block"]


def test_nail_prefixes_en_and_localized():
    nails = ["Has been OFFERED a multi-agent architecture for compliance checks at RNU.",
             "Has been MODIFIED the retrieval pipeline with independent Crossref verification.",
             "Has been SUGGESTED a guideline for human approval of AI-assisted drafts."]
    assert not check_nails(nails, "en")
    bad = ["We offer a system for checking theses at RNU today.", nails[1]]
    c = codes(check_nails(bad, "en"))
    assert {"NAILS_COUNT", "NAIL_PREFIX"} <= c
    lv = ["Ir PIEDĀVĀTS daudzaģentu arhitektūra RNU noslēguma darbu pārbaudei.", nails[1], nails[2]]
    assert not [f for f in check_nails(lv, "lv") if f["code"] == "NAIL_PREFIX"]


def test_problem_needs_statistics_and_bounds():
    assert {"SENTENCE_BOUNDS", "NO_STATISTICS"} <= codes(check_bounded("It is a problem. Really.", "problem_formulation", "chapter1", "p"))
    ok = "In 2024, 38% of theses were returned. Supervisors spend 6.5 hours per thesis. This delays graduation."
    assert not check_bounded(ok, "problem_formulation", "chapter1", "p")


def test_statistic_detection():
    assert has_statistic("38% of users") and has_statistic("6.5 hours") and has_statistic("in 2024")
    assert not has_statistic("one big problem")


def test_practical_blocks_unbacked_numbers_and_sample_data(tmp_path):
    rows = parse_csv(SAMPLE_CSV.replace("412", "410"))
    analysis = analyze(rows)
    (tmp_path / "main.py").write_text("print('hi')")
    (tmp_path / "test_main.py").write_text("def test(): pass")
    state = {"project": {"doc_type": "course_work", "language": "en"},
             "implementation": {"local_path": str(tmp_path), "run_command": "python main.py"},
             "experiments": {"analysis": analysis},
             "practical": {"architecture": "x", "deployment_steps": ["a"], "conclusion": "One. Two.",
                           "results_discussion": "Latency dropped from 413 ms to 267.67 ms, a 99.9% gain."},
             "references": []}
    f = check_practical(state)
    unbacked = [x for x in f if x["code"] == "RESULT_NUMBER_UNBACKED"]
    assert unbacked and "99.9%" in unbacked[0]["params"]["numbers"][0]
    state["experiments"]["is_sample"] = True
    assert "EXPERIMENT_SAMPLE_DATA" in codes(check_practical(state))


def test_mockups_only_fails(tmp_path):
    (tmp_path / "design.fig").write_text("x")
    state = {"project": {"doc_type": "course_work"}, "implementation": {"local_path": str(tmp_path), "run_command": "x"},
             "experiments": {}, "practical": {}, "references": []}
    assert "IMPL_NO_CODE" in codes(check_practical(state))


def test_hallucinated_citation_blocked():
    state = {"references": [{"key": "smith2021", "status": "verified", "included": True, "title": "A"}],
             "chapter1": {"topicality": "x [@smith2021] and [@ghost2020]."}}
    f = check_references(state)
    assert any(x["code"] == "CITATION_UNKNOWN" and x["params"]["keys"] == ["ghost2020"] for x in f)
    assert citation_keys("see [@a2020; @b2021]") == ["a2020", "b2021"]


def test_submission_form_rules():
    state = {"outline": {"selected_title": "T"}, "submission": {
        "authors": [{"first_name": "A", "surname": "B", "affiliation": "RNU", "email": "bad", "corresponding": True},
                    {"first_name": "C", "surname": "D", "affiliation": "RNU", "email": "c@d.lv", "corresponding": True}],
        "technical_section": "Nope", "keywords": "one", "presentation_type": "Hybrid"}}
    c = codes(check_submission(state))
    assert {"CORRESPONDING_AUTHOR", "AUTHOR_EMAIL", "TECHNICAL_SECTION", "SUBMISSION_KEYWORDS", "PRESENTATION_TYPE"} <= c
    state["submission"]["authors"] = [{"first_name": "x", "surname": "y", "affiliation": "z", "email": f"a{i}@b.lv"} for i in range(11)]
    assert "AUTHORS_COUNT" in codes(check_submission(state))


def test_statistics():
    a = analyze(parse_csv(SAMPLE_CSV))
    rt = next(m for m in a["metrics"] if m["metric"] == "response_time_ms")
    acc = next(m for m in a["metrics"] if m["metric"] == "accuracy")
    assert rt["direction"] == "lower" and rt["improved"] and rt["significant"] and rt["welch_p"] > 0
    assert acc["direction"] == "higher" and acc["improved"]


def test_citation_styles():
    ref = {"key": "smith2021", "title": "Deep learning for invoices", "authors": [{"given": "John Paul", "family": "Smith"},
           {"given": "Anna", "family": "Lee"}], "year": 2021, "venue": "Journal X", "volume": "3", "issue": "2",
           "pages": "1-9", "doi": "10.1/x"}
    assert plain(apa(ref)).startswith("Smith, J. P., & Lee, A. (2021). Deep learning for invoices.")
    assert plain(ieee(ref, 1)).startswith("[1] J. P. Smith, and A. Lee")
    assert render_citations("as shown [@smith2021].", {"smith2021": ref}, "apa", {}) == "as shown (Smith & Lee, 2021)."
    assert render_citations("as shown [@smith2021].", {"smith2021": ref}, "ieee", {"smith2021": 4}) == "as shown [4]."


def test_bibtex_and_similarity():
    bib = """@article{k1, author = {Smith, John and Lee, Anna}, title = {{Deep} learning for invoices},
    journal = {Journal X}, year = {2021}, doi = {https://doi.org/10.1/X}}
    @inproceedings{k2, author = "Jane Doe", title = "Agents", booktitle = "Proc. Y", year = 2023}"""
    e = parse_bibtex(bib)
    assert len(e) == 2 and e[0]["authors"][1]["family"] == "Lee" and e[0]["doi"] == "10.1/x"
    assert e[1]["authors"][0]["family"] == "Doe" and e[1]["year"] == 2023
    assert title_similarity("Deep Learning for Invoices", "Deep learning for invoices.") > 0.95
