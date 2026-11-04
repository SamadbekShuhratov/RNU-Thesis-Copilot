"""Optional: run the SAME employee nodes on LangGraph.

The portal uses the built-in engine (``engine.py``) because it has no heavy
dependencies and is fully covered by the test-suite. For the course work you
may want to show that the design is runtime-independent, or use LangGraph
Studio for visualisation. Install the extras first::

    pip install -r requirements-langgraph.txt
    python scripts/langgraph_demo.py --demo

Semantics are identical: ``ctx.interrupt`` maps to ``langgraph.types.interrupt``
and a review decision is resumed with ``Command(resume={...})``.
"""
from __future__ import annotations

from typing import Any, TypedDict

from .engine import END as OUR_END
from .graph import ALL_STAGES, human_review, make_agent_node, pm_final, pm_gate

STATE_FIELDS = ["project", "facts", "references", "implementation", "experiments", "submission", "stage", "stages",
                "stage_status", "attempts", "findings", "feedback", "notice", "ai_drafts", "_route", "revise_scope",
                "outline", "chapter1", "literature", "theory", "practical", "conclusion", "bibliography", "compliance"]

LGState = TypedDict("LGState", {k: Any for k in STATE_FIELDS}, total=False)  # type: ignore[misc]


class _LGContext:
    """Duck-typed replacement for ``RunContext`` inside LangGraph nodes."""

    def __init__(self, services: dict[str, Any], log=print):
        self.services = services
        self._log = log
        self.thread_id = ""

    def interrupt(self, payload: Any) -> Any:
        from langgraph.types import interrupt
        return interrupt(payload)

    def check_cancel(self) -> None:
        return None

    def progress(self, message: str, **data: Any) -> None:
        self._log(f"[{data.get('stage', '')}] {message}")


def build_langgraph(stages: list[str], services: dict[str, Any], checkpointer=None, log=print):
    from langgraph.graph import END, StateGraph

    ctx = _LGContext(services, log)

    def wrap(fn):
        def node(state):
            return fn(dict(state), ctx)
        node.__name__ = getattr(fn, "__name__", "node")
        return node

    def route(state) -> str:
        r = state.get("_route") or OUR_END
        return END if r == OUR_END else r

    g = StateGraph(LGState)
    targets = []
    for s in stages:
        name = "pm_final" if s == "final" else s
        g.add_node(name, wrap(pm_final if s == "final" else make_agent_node(s)))
        targets.append(name)
    g.add_node("pm_gate", wrap(pm_gate))
    g.add_node("human_review", wrap(human_review))
    targets += ["pm_gate", "human_review", END]
    for name in targets:
        if name != END:
            g.add_conditional_edges(name, route, targets)
    g.set_entry_point(stages[0])
    return g.compile(checkpointer=checkpointer)


__all__ = ["build_langgraph", "ALL_STAGES", "LGState"]
