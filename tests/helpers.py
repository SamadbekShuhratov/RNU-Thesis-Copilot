from pathlib import Path

from app.experiments.analysis import SAMPLE_CSV
from tests.conftest import FACTS

ROOT = Path(__file__).resolve().parent.parent
REAL_CSV = SAMPLE_CSV.replace("412", "411").replace("0.91", "0.92")


def complete_project(c, doc_type="course_work", language="en"):
    """Drive a project through every stage with the demo model."""
    pid = c.create_project("Demo", doc_type, language, {
        "topic": "local multi-agent thesis assistant", "object_hint": "Riga Nordic University",
        "subject_hint": "automated compliance validation", "facts": FACTS,
        "student_name": "Test Student", "student_email": "student@example.com",
        "supervisor": "Dr. A. Supervisor", "technical_section": "AI, Data Science and Intelligent Systems"})
    c.run(pid, wait=True)
    for _ in range(40):
        st = c.get_state(pid)
        if st["status"] == "done":
            return pid
        stage = st["state"]["stage"]
        if stage == "practical" and not st["state"]["experiments"].get("analysis"):
            impl = st["state"]["implementation"]
            c.apply_patch(pid, {"implementation": {**impl, "local_path": str(ROOT / "app"),
                                                   "run_command": "python -m app"}})
            c.upload_experiments(pid, REAL_CSV, "measurements.csv")
            c.run(pid, {"action": "revise", "feedback": "use measurements"}, wait=True)
            continue
        if stage == "final" and doc_type == "conference_paper":
            sub = st["state"]["submission"]
            if not sub.get("keywords"):
                sub["keywords"] = "multi-agent systems; LLM; compliance"
                c.apply_patch(pid, {"submission": sub})
        c.run(pid, {"action": "approve"}, wait=True)
        assert c.jobs[pid].status != "error", c.jobs[pid].error
    raise AssertionError("workflow did not finish")
