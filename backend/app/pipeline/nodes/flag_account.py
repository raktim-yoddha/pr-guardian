"""Shared — Flag Account node.

Upserts the GithubAccount by username, increments flag_count, writes the
PREvent row. If flag_count >= 3, bans the account.
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.github_account import GithubAccount
from app.models.pr_event import PREvent
from app.pipeline.state import PRState

logger = logging.getLogger(__name__)


async def flag_account_node(state: PRState) -> dict:
    author = state.get("pr_author") or "unknown"
    agent_id = state.get("agent_id") or 0
    pr_number = state.get("pr_number") or 0
    pr_url = state.get("pr_url") or ""
    decline_reason = state.get("decline_reason") or ""
    layer_results = state.get("layer_results") or {}

    # Determine which layer caught it.
    layer_caught = "unknown"
    for layer in ("spam", "malicious_code", "prompt_injection"):
        if layer in layer_results:
            lr = layer_results[layer]
            if isinstance(lr, dict):
                # For spam layer, check for heuristic or LLM detection
                if layer == "spam":
                    if lr.get("heuristic") or lr.get("llm"):
                        layer_caught = layer
                        break
                # For prompt_injection and malicious_code, check for detection signals
                if layer in ("prompt_injection", "malicious_code"):
                    if lr.get("regex") or lr.get("llm") or lr.get("encoded") or lr.get("static"):
                        layer_caught = layer
                        break

    logger.info("flag_account: %s via %s", author, layer_caught)

    async with AsyncSessionLocal() as db:
        # Upsert the GitHub account.
        account = await db.scalar(
            select(GithubAccount).where(GithubAccount.github_username == author)
        )
        if account is None:
            account = GithubAccount(github_username=author, flag_count=0, account_status="active")
            db.add(account)

        account.flag_count += 1

        if account.flag_count >= settings.FLAG_BAN_THRESHOLD:
            account.account_status = "banned"
            from datetime import datetime, timezone
            account.banned_at = datetime.now(timezone.utc)
            logger.info("flag_account: BANNED %s (flag_count=%d)", author, account.flag_count)

        # Record the PREvent.
        event = PREvent(
            agent_id=agent_id,
            pr_number=pr_number,
            pr_url=pr_url,
            author_github=author,
            decision="declined",
            layer_caught=layer_caught,
            reason=decline_reason,
        )
        db.add(event)
        await db.commit()

    return {}
