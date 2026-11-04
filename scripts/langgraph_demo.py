"""Run the 8-employee workflow on LangGraph from the command line.

    pip install -r requirements-langgraph.txt
    python scripts/langgraph_demo.py --demo            # demo model, auto-approve
    python scripts/langgraph_demo.py --model qwen2.5:14b-instruct

Each human-review interrupt is answered on the terminal (a = approve,
r = revise with feedback, q = quit). State is checkpointed to
data/langgraph.sqlite so you can stop and continue later with the same --thread.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR, settings  # noqa: E402
from app.llm import create_llm  # noqa: E402
from app.orchestrator.langgraph_adapter import build_langgraph  # noqa: E402
from app.orchestrator.state import initial_state  # noqa: E402
from app.rules import stages_for  # noqa: E402
from app.validators import render_all  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--doc-type", default="course_work")
    ap.add_argument("--language", default="en")
    ap.add_argument("--topic", default="Local multi-agent assistant for RNU thesis compliance")
    ap.add_argument("--thread", default="cli-demo")
    args = ap.parse_args()

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.types import Command

    cfg = settings.all()
    if args.demo:
        cfg["llm_provider"] = "mock"
    if args.model:
        cfg["llm_model"] = args.model
    services = {"llm": create_llm(cfg), "settings": cfg, "verify_refs": True}
    saver = SqliteSaver(sqlite3.connect(str(DATA_DIR / "langgraph.sqlite"), check_same_thread=False))
    graph = build_langgraph(stages_for(args.doc_type), services, saver)
    config = {"configurable": {"thread_id": args.thread}}

    snapshot = graph.get_state(config)
    if not snapshot.values:
        state = initial_state(args.thread, "CLI", args.doc_type, args.language, {"topic": args.topic})
        result = graph.invoke(state, config)
    else:
        result = None
    while True:
        snapshot = graph.get_state(config)
        if not snapshot.next:
            print("Workflow complete.")
            break
        stage = snapshot.values.get("stage")
        print(f"\n=== Review: {stage} ===")
        for f in render_all(snapshot.values.get("findings", []), "en"):
            print(f"  [{f['severity']}] {f['message']}")
        if args.demo and snapshot.values.get("notice") == "approval_blocked":
            print("Blocked by Employee 1 — provide real evidence in the portal to continue.")
            break
        choice = "a" if args.demo else input("a = approve, r = revise, q = quit > ").strip().lower()
        if choice == "q":
            break
        if choice == "r":
            decision = {"action": "revise", "feedback": input("feedback > ")}
        else:
            decision = {"action": "approve"}
        result = graph.invoke(Command(resume=decision), config)
    _ = result


if __name__ == "__main__":
    main()
