"""Shared — Decline PR node.

Posts an optional comment to the PR explaining the decline, closes the PR,
then returns final state. No-op if the API calls fail (logged only).
"""
from __future__ import annotations

import logging

from app.pipeline.state import PRState
from app.services.github import GithubError, github_client

logger = logging.getLogger(__name__)

DECLINE_COMMENT_BODY = """\
🚫 **PR Guardian — Declined**

This PR was automatically declined by the review pipeline.

**Reason:** {reason}

Please review the above and open a new PR if you believe this is a mistake.
"""


async def decline_pr(state: PRState) -> dict:
    repo = state.get("repo_full_name") or ""
    pr_number = state.get("pr_number") or 0
    reason = state.get("decline_reason") or "Unknown reason"

    logger.info("decline_pr: PR #%s on %s — %s", pr_number, repo, reason)

    # Post comment (best-effort).
    body = DECLINE_COMMENT_BODY.format(reason=reason)
    agent = state.get("agent")
    installation_id = agent.github_installation_id if agent else None
    try:
        await github_client.post_pr_comment(repo, pr_number, body, installation_id=installation_id)
    except GithubError as exc:
        logger.warning("decline_pr: failed to post comment (%s)", exc)

    # Close the PR (best-effort).
    try:
        await github_client.update_pr(repo, pr_number, state="closed", installation_id=installation_id)
        logger.info("decline_pr: closed PR #%s on %s", pr_number, repo)
    except GithubError as exc:
        logger.warning("decline_pr: failed to close PR (%s)", exc)

    return {"final_decision": "declined"}
