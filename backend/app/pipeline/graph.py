"""LangGraph wiring for the PR review pipeline.

Flow (strict sequential gate — a PR that fails any of Layers 1–3 never reaches
Layer 4):

    START → prompt_injection → spam → malicious → summary → approve → END
               │         │          │
               └─[decline]─┴──[decline]┘──► flag_account → decline → END

Each detection node returns ``final_decision = "declined"`` on a hit. The
conditional edge after every layer checks that field; if declined it routes to
``flag_account`` then ``decline_pr``, otherwise forward to the next layer.
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.pipeline.nodes.approve_pr import approve_pr
from app.pipeline.nodes.decline_pr import decline_pr
from app.pipeline.nodes.flag_account import flag_account_node
from app.pipeline.nodes.prompt_injection import prompt_injection_detection
from app.pipeline.nodes.malicious_code import malicious_code_detection
from app.pipeline.nodes.spam import spam_detection
from app.pipeline.nodes.summary import summary_layer
from app.pipeline.state import PRState

logger = logging.getLogger(__name__)


def _route_after_layer(state: PRState, *, next_node: str) -> str:
    """Return ``flag_account`` if a layer declined, else ``next_node``.

    Hard rule from AGENTS.md: a PR that fails any detection layer must never
    move forward — it always routes to flag_account → decline_pr.
    """
    if state.get("final_decision") == "declined":
        return "flag_account"
    return next_node


def _after_prompt_injection(state: PRState) -> str:
    return _route_after_layer(state, next_node="spam")


def _after_spam(state: PRState) -> str:
    return _route_after_layer(state, next_node="malicious_code")


def _after_malicious(state: PRState) -> str:
    return _route_after_layer(state, next_node="summary")


def build_pipeline():  # type: ignore[no-untyped-def]
    """Compile and return the runnable LangGraph pipeline."""
    graph = StateGraph(PRState)

    graph.add_node("prompt_injection", prompt_injection_detection)
    graph.add_node("spam", spam_detection)
    graph.add_node("malicious_code", malicious_code_detection)
    graph.add_node("summary", summary_layer)
    graph.add_node("flag_account", flag_account_node)
    graph.add_node("approve_pr", approve_pr)
    graph.add_node("decline_pr", decline_pr)

    graph.add_edge(START, "prompt_injection")
    graph.add_conditional_edges("prompt_injection", _after_prompt_injection)
    graph.add_conditional_edges("spam", _after_spam)
    graph.add_conditional_edges("malicious_code", _after_malicious)
    graph.add_edge("summary", "approve_pr")
    graph.add_edge("flag_account", "decline_pr")
    graph.add_edge("approve_pr", END)
    graph.add_edge("decline_pr", END)

    return graph.compile()


# Compiled once at import time — cheap & reused for every PR.
pipeline = build_pipeline()
