import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RNU_DATA_DIR", tempfile.mkdtemp(prefix="rnu-test-"))

import pytest  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.llm import MockLLM, LLMOptions  # noqa: E402
from app.services import Copilot  # noqa: E402

FAKE_WORKS = [
    {"title": f"Study {i} on multi-agent academic writing assistants", "authors": [{"given": "Anna", "family": f"Author{i}"}],
     "year": 2020 + i % 5, "venue": "Journal of Testing", "volume": str(i), "issue": "1", "pages": "1-10",
     "doi": f"10.1000/test.{i}", "url": "", "abstract": "Abstract text.", "type": "article",
     "cited_by_count": i, "source": "openalex", "source_id": f"W{i}"}
    for i in range(1, 9)
]


def fake_verify(ref):
    r = dict(ref)
    r["status"] = "verified"
    r["verification"] = {"method": "test", "score": 1.0}
    return r


@pytest.fixture
def copilot(tmp_path, monkeypatch):
    import app.references.library as lib
    import app.services as svc
    monkeypatch.setattr(lib, "verify_reference", fake_verify)
    monkeypatch.setattr(svc, "verify_reference", fake_verify)
    settings.update({"llm_provider": "mock", "max_auto_revisions": 1, "llm_judge": True})
    db = Database(tmp_path / "test.sqlite3")
    search = lambda q, per_page=8, from_year=None, mailto="": FAKE_WORKS  # noqa: E731
    return Copilot(db, services_override={"llm": MockLLM(LLMOptions(model="mock")), "search": search})


FACTS = [
    {"id": "F1", "text": "In 2024, 38% of RNU theses were returned at least once for formatting errors",
     "source": "RNU Study Department report 2024"},
    {"id": "F2", "text": "Supervisors spend on average 6.5 hours per thesis on formal checks",
     "source": "Survey of 42 RNU supervisors, 2025"},
]
