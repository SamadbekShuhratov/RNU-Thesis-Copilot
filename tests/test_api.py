"""HTTP API smoke test: runs a real uvicorn server in a background thread and talks to it over HTTP."""
import socket
import threading
import time

import pytest
import requests
import uvicorn

from app.services import set_copilot  # noqa: E402
from app.web import app  # noqa: E402
from tests.conftest import FACTS  # noqa: E402


class Client:
    def __init__(self, base):
        self.base = base

    def __getattr__(self, method):
        return lambda path, **kw: requests.request(method.upper(), self.base + path, timeout=30, **kw)


@pytest.fixture
def client(copilot):
    set_copilot(copilot)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield Client(f"http://127.0.0.1:{port}")
    server.should_exit = True
    t.join(timeout=5)


def test_api_flow(copilot, client):
    assert client.get("/api/health").json()["ok"]
    meta = client.get("/api/meta").json()["data"]
    assert "conference_paper" in meta["doc_types"] and len(meta["output_languages"]) >= 10
    pid = client.post("/api/projects", json={"name": "API", "doc_type": "course_work", "language": "en",
                                             "setup": {"topic": "x", "facts": FACTS}}).json()["data"]["id"]
    st = client.get(f"/api/projects/{pid}?lang=uz").json()["data"]
    assert st["status"] == "ready"
    r = client.patch(f"/api/projects/{pid}/state", json={"patch": {"stage": "final"}})
    assert r.status_code == 400
    copilot.run(pid, wait=True)
    st = client.get(f"/api/projects/{pid}").json()["data"]
    assert st["status"] == "review"
    assert client.post(f"/api/projects/{pid}/run").status_code == 409
    files = {"file": ("m.csv", "metric,variant,value\nt,baseline,1\nt,baseline,2\nt,proposed,1\nt,proposed,0.5\n", "text/csv")}
    assert client.post(f"/api/projects/{pid}/experiments", files=files).json()["ok"]
    assert client.get(f"/api/projects/{pid}/export/progress?lang=ru").json()["data"]["subject"]
    assert client.get(f"/api/projects/{pid}/export/thesis.docx").status_code == 200
    assert client.get("/api/projects/ffffffffffff").status_code == 404
