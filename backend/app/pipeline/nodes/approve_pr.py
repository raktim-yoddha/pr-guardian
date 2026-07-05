"""Shared — Approve PR node.

Records the PREvent row as "approved" and optionally posts a comment.
"""
from __future__ import annotations

import logging

from app.core.database import AsyncSessionLocal
from app.models.pr_event import PREvent
from app.pipeline.state import PRState
from app.services.github import GithubError, github_client

logger = logging.getLogger(__name__)

APPROVE_COMMENT_BODY = """\
✅ **PR Guardian — Approved**

This PR passed all automated review layers (spam, malicious code, hijack-proof).
Title and description have been improved by the agent.
"""


async def approve_pr(state: PRState) -> dict:
    agent_id = state.get("agent_id") or 0
    pr_number = state.get("pr_number") or 0
    pr_url = state.get("pr_url") or ""
    author = state.get("pr_author") or "unknown"

    logger.info("approve_pr: PR #%s on %s", pr_number, state.get("repo_full_name"))

    async with AsyncSessionLocal() as db:
        event = PREvent(
            agent_id=agent_id,
            pr_number=pr_number,
            pr_url=pr_url,
            author_github=author,
            decision="approved",
            layer_caught=None,
            reason="Passed all detection layers",
        )
        db.add(event)
        await db.commit()

    # Post approval comment (best-effort).
    repo = state.get("repo_full_name") or ""
    agent = state.get("agent")
    installation_id = agent.github_installation_id if agent else None
    try:
        await github_client.post_pr_comment(repo, pr_number, APPROVE_COMMENT_BODY, installation_id=installation_id)
    except GithubError as exc:
        logger.warning("approve_pr: failed to post comment (%s)", exc)

    return {"final_decision": "approved"}
