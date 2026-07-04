"""PR pipeline — shared state."""
from __future__ import annotations

from typing import TypedDict


class PRState(TypedDict, total=False):
    # Input fields (set before graph starts)
    agent_id: int
    repo_full_name: str
    pr_number: int
    pr_url: str
    pr_title: str
    pr_body: str
    pr_diff: str
    pr_author: str
    agent: object  # The Agent ORM row — avoids repeated DB fetches.

    # Populated during pipeline execution
    retrieved_context: list[str]
    layer_results: dict
    final_decision: str          # "declined" | "approved"
    decline_reason: str | None
    flag_account: bool
    summary_title: str | None
    summary_body: str | None
    author_flag_count: int        # Number of flags on the author's account
    author_is_banned: bool        # Whether the author is banned
