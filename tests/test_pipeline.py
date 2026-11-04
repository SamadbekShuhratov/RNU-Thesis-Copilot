"""End-to-end: run the whole 8-employee workflow with the demo model."""
from pathlib import Path

import pytest

from app.experiments.analysis import SAMPLE_CSV
from app.services import ConflictError
from tests.conftest import FACTS

ROOT = Path(__file__).resolve().parent.parent

REAL_CSV = SAMPLE_CSV.replace("412", "411").replace("0.91", "0.92")   # not the sample itself


def _wait(c, pid):
    job = c.jobs[pid]
    if job.thread:
        job.thread.join(timeout=60)
    assert job.status != "error", job.error
    return c.get_state(pid)


def _approve(c, pid):
    c.run(pid, {"action": "approve"}, wait=True)
    assert c.jobs[pid].status != "error", c.jobs[pid].error
    return c.get_state(pid)


@pytest.mark.parametrize("doc_type", ["course_work", "conference_paper"])
def test_full_workflow(copilot, doc_type):
    c = copilot
    pid = c.create_project("Demo", doc_type, "en", {
        "topic": "local multi-agent thesis assistant", "object_hint": "Riga Nordic University",
        "subject_hint": "automated compliance validation", "facts": FACTS,
        "student_name": "Test Student", "student_email": "student@example.com",
        "technical_section": "AI, Data Science and Intelligent Systems"})
    st = c.get_state(pid)
    assert st["status"] == "ready"

    # Employee 2
    c.run(pid, wait=True)
    st = c.get_state(pid)
    assert st["status"] == "review" and st["state"]["stage"] == "architect"
    assert not [f for f in st["findings"] if f["severity"] == "block"], st["findings"]
    st = _approve(c, pid)

    # Employee 3
    assert st["state"]["stage"] == "chapter1" and st["status"] == "review"
    assert not [f for f in st["findings"] if f["severity"] == "block"], st["findings"]
    st = _approve(c, pid)

    # Employee 4 (reference discovery through the fake search)
    assert st["state"]["stage"] == "literature"
    assert len(st["state"]["references"]) == 8
    assert all(r["status"] == "verified" for r in st["state"]["references"])
    st = _approve(c, pid)

    if doc_type != "conference_paper":
        assert st["state"]["stage"] == "theory"
        st = _approve(c, pid)

    # Employee 6 — blocked until real evidence is provided
    assert st["state"]["stage"] == "practical"
    codes = {f["code"] for f in st["findings"]}
    assert {"IMPL_EVIDENCE_MISSING", "EXPERIMENTS_MISSING"} <= codes
    c.run(pid, {"action": "approve"}, wait=True)
    st = c.get_state(pid)
    assert st["state"]["stage"] == "practical" and st["state"]["notice"] == "approval_blocked"

    # sample data is rejected as evidence
    c.upload_experiments(pid, SAMPLE_CSV, "sample.csv")
    assert "EXPERIMENT_SAMPLE_DATA" in {f["code"] for f in c.get_state(pid)["findings"]}

    c.apply_patch(pid, {"implementation": {**st["state"]["implementation"], "local_path": str(ROOT / "app"),
                                           "run_command": "python -m app"}})
    c.upload_experiments(pid, REAL_CSV, "measurements.csv")
    c.check_implementation(pid)
    c.run(pid, {"action": "revise", "feedback": "Use the uploaded measurements."}, wait=True)
    st = c.get_state(pid)
    blocks = [f for f in st["findings"] if f["severity"] == "block"]
    assert not blocks, blocks
    assert "411" in st["state"]["practical"]["results_discussion"] or "mean" in st["state"]["practical"]["results_discussion"]
    st = _approve(c, pid)

    # Employee 7
    assert st["state"]["stage"] == "conclusion"
    assert not [f for f in st["findings"] if f["severity"] == "block"], st["findings"]
    st = _approve(c, pid)

    # Employee 8
    assert st["state"]["stage"] == "references"
    assert st["state"]["bibliography"]["entries"]
    st = _approve(c, pid)

    # Employee 1 final
    assert st["state"]["stage"] == "final"
    if doc_type == "conference_paper":
        sub = st["state"]["submission"]
        sub["keywords"] = "multi-agent systems; LLM; compliance"
        c.apply_patch(pid, {"submission": sub})
    st = c.get_state(pid)
    assert not [f for f in st["findings"] if f["severity"] == "block"], st["findings"]
    st = _approve(c, pid)
    assert st["status"] == "done"

    with pytest.raises(ConflictError):
        c.run(pid)

    # rerun a stage from history
    hist = c.history(pid)
    assert len(hist) > 10


def test_single_section_revision(copilot):
    c = copilot
    pid = c.create_project("Demo", "course_work", "en", {"facts": FACTS})
    c.run(pid, wait=True)
    _approve(c, pid)
    before = c.raw_state(pid)["chapter1"]
    c.run(pid, {"action": "revise", "feedback": "shorter", "section": 0}, wait=True)
    after = c.raw_state(pid)["chapter1"]
    assert after["topicality"] == before["topicality"]
    assert len(after["sections"]) == len(before["sections"])


def test_rerun_and_rollback(copilot):
    c = copilot
    pid = c.create_project("Demo", "course_work", "en", {"facts": FACTS})
    c.run(pid, wait=True)
    _approve(c, pid)
    c.run(pid, {"action": "rerun", "target": "architect"}, wait=True)
    st = c.get_state(pid)
    assert st["state"]["stage"] == "architect" and st["status"] == "review"
    seq = c.history(pid)[-1]["seq"]
    c.rollback(pid, seq)
    assert c.get_state(pid)["status"] == "ready"


def test_missing_facts_blocks(copilot):
    c = copilot
    pid = c.create_project("Demo", "course_work", "en", {})
    c.run(pid, wait=True)
    _approve(c, pid)
    st = c.get_state(pid)
    codes = {f["code"] for f in st["findings"]}
    assert "PLACEHOLDER" in codes
    c.run(pid, {"action": "approve"}, wait=True)
    assert c.get_state(pid)["state"]["stage"] == "chapter1"
