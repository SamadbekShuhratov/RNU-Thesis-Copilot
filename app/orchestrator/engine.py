"""A small, dependency-free state-graph engine (LangGraph-style semantics).

* Nodes are functions ``fn(state, ctx) -> dict`` returning a partial update.
* Edges are router functions ``router(state) -> next node name | END``.
* ``ctx.interrupt(payload)`` pauses the graph for a human (like
  ``langgraph.types.interrupt``); the node is re-run on resume and the call
  returns the human's answer.
* Every step is checkpointed to SQLite, so a run survives restarts and the
  full history can be inspected or rolled back ("time travel").

The same node functions are also exported to real LangGraph in
``langgraph_adapter.py`` for students who want to compare both runtimes.
"""
from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from ..db import Database

END = "__end__"


class Interrupted(Exception):
    def __init__(self, payload: Any):
        super().__init__("graph interrupted for human review")
        self.payload = payload


class Cancelled(Exception):
    pass


@dataclass
class RunContext:
    thread_id: str
    resume_value: Any = None
    has_resume: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event)
    progress_cb: Callable[[str, dict], None] | None = None
    services: dict[str, Any] = field(default_factory=dict)

    def interrupt(self, payload: Any) -> Any:
        if self.has_resume:
            self.has_resume = False
            value, self.resume_value = self.resume_value, None
            return value
        raise Interrupted(payload)

    def check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise Cancelled()

    def progress(self, message: str, **data: Any) -> None:
        if self.progress_cb:
            self.progress_cb(message, data)


NodeFn = Callable[[dict, RunContext], dict]
Router = Callable[[dict], str]


class StateGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, NodeFn] = {}
        self.routers: dict[str, Router] = {}
        self.entry: str | None = None

    def add_node(self, name: str, fn: NodeFn) -> "StateGraph":
        self.nodes[name] = fn
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        self.routers[source] = lambda _state, _t=target: _t
        return self

    def add_conditional_edges(self, source: str, router: Router) -> "StateGraph":
        self.routers[source] = router
        return self

    def set_entry_point(self, name: str) -> "StateGraph":
        self.entry = name
        return self


@dataclass
class RunResult:
    status: str                 # "interrupted" | "done" | "cancelled"
    node: str | None
    payload: Any = None
    steps: int = 0


class Runner:
    """Executes a StateGraph against the checkpoint store."""

    MAX_STEPS = 200

    def __init__(self, graph: StateGraph, db: Database):
        self.graph = graph
        self.db = db

    # ── state access ───────────────────────────────────────────────────────
    def latest(self, thread_id: str) -> dict[str, Any] | None:
        return self.db.latest_checkpoint(thread_id)

    def create(self, thread_id: str, state: dict[str, Any]) -> int:
        return self.db.save_checkpoint(thread_id, None, self.graph.entry, state)

    def update_state(self, thread_id: str, patch: dict[str, Any], node: str = "human_edit") -> dict[str, Any]:
        """Merge ``patch`` into the latest checkpoint, keeping next node and
        any pending interrupt (safe while the graph waits for a human)."""
        cp = self.latest(thread_id)
        if cp is None:
            raise KeyError(thread_id)
        state = copy.deepcopy(cp["state"])
        state.update(copy.deepcopy(patch))
        self.db.save_checkpoint(thread_id, node, cp["next_node"], state, cp["pending"])
        return state

    def rollback(self, thread_id: str, seq: int) -> dict[str, Any]:
        cp = self.db.get_checkpoint(thread_id, seq)
        if cp is None:
            raise KeyError(f"checkpoint {seq} not found")
        self.db.save_checkpoint(thread_id, f"rollback:{seq}", cp["next_node"], cp["state"], cp["pending"])
        return cp["state"]

    # ── execution ──────────────────────────────────────────────────────────
    def run(self, ctx: RunContext, resume: Any = None, has_resume: bool = False) -> RunResult:
        cp = self.latest(ctx.thread_id)
        if cp is None:
            raise KeyError(f"no checkpoint for thread {ctx.thread_id}")
        node = cp["next_node"]
        state = copy.deepcopy(cp["state"])
        if node is None:
            return RunResult("done", None)
        if cp["pending"] is not None and not has_resume:
            return RunResult("interrupted", node, cp["pending"])
        ctx.resume_value, ctx.has_resume = resume, has_resume
        steps = 0
        while node and node != END:
            if steps >= self.MAX_STEPS:
                raise RuntimeError("graph exceeded maximum number of steps")
            ctx.check_cancel()
            fn = self.graph.nodes[node]
            try:
                update = fn(copy.deepcopy(state), ctx) or {}
            except Interrupted as intr:
                self.db.save_checkpoint(ctx.thread_id, node, node, state, intr.payload)
                return RunResult("interrupted", node, intr.payload, steps)
            except Cancelled:
                return RunResult("cancelled", node, None, steps)
            state.update(update)
            router = self.graph.routers.get(node)
            nxt = router(state) if router else END
            steps += 1
            self.db.save_checkpoint(ctx.thread_id, node, None if nxt == END else nxt, state, None)
            node = nxt
        return RunResult("done", None, None, steps)
