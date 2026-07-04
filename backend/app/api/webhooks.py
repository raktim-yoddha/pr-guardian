"""GitHub webhook receiver.

Validates the ``X-Hub-Signature-256`` header with HMAC-SHA256, then routes
valid ``pull_request`` events (actions ``opened`` / ``synchronize``) to a
background task that runs the full LangGraph pipeline. Per AGENTS.md the
webhook must respond within 10 seconds, so all pipeline work happens out-of-band.

Hardening (Phase 5): diff size limit, per-account rate limiting.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.core.config import settings
from app.core.metrics import inc_counter
from app.core.database import AsyncSessionLocal
from app.models.pr_event import PREvent
from app.tasks import process_pr_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# PR actions we treat as "review this PR".
HANDLED_PR_ACTIONS = {"opened", "synchronize"}

# Per-account rate limit: {username: [(timestamp,)]}
_account_windows: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW_S = 3600  # 1 hour
RATE_LIMIT_MAX_PRS = 10  # max PRs per account per window

# Diff size limit (from settings).
MAX_DIFF_BYTES = settings.MAX_PR_DIFF_BYTES


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Constant-time HMAC-SHA256 verification of the GitHub webhook signature."""
    if not signature_header:
        return False
    try:
        algo, delivered = signature_header.split("=", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    expected = hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode(),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(delivered, expected)


def _is_rate_limited(author: str) -> bool:
    """Return True if ``author`` has exceeded RATE_LIMIT_MAX_PRS in the window."""
    now = time.monotonic()
    window = _account_windows[author]
    # Prune old entries.
    _account_windows[author] = [t for t in window if now - t < RATE_LIMIT_WINDOW_S]
    if len(_account_windows[author]) >= RATE_LIMIT_MAX_PRS:
        logger.warning("webhook: rate-limited %s (>%d PRs/hour)", author, RATE_LIMIT_MAX_PRS)
        return True
    _account_windows[author].append(now)
    return False


async def _auto_flag_account(repo_full_name: str, author: str, reason: str) -> None:
    """Record an auto-flag event when rate-limited."""
    from sqlalchemy import select
    from app.models.agent import Agent
    from app.models.github_account import GithubAccount

    async with AsyncSessionLocal() as db:
        agent = await db.scalar(
            select(Agent)
            .where(Agent.repo_full_name == repo_full_name)
            .where(Agent.is_active.is_(True))
            .order_by(Agent.id.desc())
            .limit(1)
        )
        if agent is None:
            return

        account = await db.scalar(
            select(GithubAccount).where(GithubAccount.github_username == author)
        )
        if account is None:
            account = GithubAccount(github_username=author, flag_count=0, account_status="active")
            db.add(account)
        account.flag_count += 1
        if account.flag_count >= settings.FLAG_BAN_THRESHOLD:
            from datetime import datetime, timezone
            account.account_status = "banned"
            account.banned_at = datetime.now(timezone.utc)

        db.add(
            PREvent(
                agent_id=agent.id,
                pr_number=0,
                pr_url="",
                author_github=author,
                decision="declined",
                layer_caught="rate_limit",
                reason=reason,
            )
        )
        await db.commit()


@router.post("/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict[str, str]:
    raw_body = await request.body()

    # 1. Validate the signature before any processing.
    if not _verify_signature(raw_body, x_hub_signature_256):
        logger.warning("webhook: invalid signature, rejecting")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # 2. Only act on pull_request events.
    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event {x_github_event!r} not handled"}

    try:
        payload: dict[str, Any] = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        ) from exc

    action = payload.get("action")
    if action not in HANDLED_PR_ACTIONS:
        return {"status": "ignored", "reason": f"action {action!r} not handled"}

    pr = payload.get("pull_request") or {}
    repo = payload.get("repository") or {}
    repo_full_name = repo.get("full_name")
    if not repo_full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing repository.full_name",
        )

    pr_number = pr.get("number")
    pr_url = pr.get("html_url") or ""
    author = ((pr.get("user") or {}).get("login")) or "unknown"
    if not pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing pull_request.number",
        )

    # 3. Rate-limit check per GitHub account.
    if _is_rate_limited(author):
        inc_counter("webhook_rate_limited_total", labels={"author": author})
        # Auto-flag + decline without running the pipeline.
        background_tasks.add_task(
            _auto_flag_account,
            repo_full_name=repo_full_name,
            author=author,
            reason=f"Rate limited: >{RATE_LIMIT_MAX_PRS} PRs/hour",
        )
        return {"status": "rate_limited", "pr_number": str(pr_number)}

    # 4. Diff size guard — reject huge PRs before any pipeline work.
    if len(raw_body) > MAX_DIFF_BYTES:
        logger.warning(
            "webhook: payload too large (%d bytes > %d) for PR #%s",
            len(raw_body),
            MAX_DIFF_BYTES,
            pr_number,
        )
        return {"status": "ignored", "reason": "payload exceeds size limit"}

    # 5. Dispatch — do NOT block the webhook response.
    process_pr_task.delay(
        repo_full_name=repo_full_name,
        pr_number=int(pr_number),
        pr_url=pr_url,
        author=author,
    )
    return {"status": "accepted", "pr_number": str(pr_number)}


@router.post("/webhooks/rotate-secret", tags=["webhooks"])
async def rotate_webhook_secret() -> dict[str, str]:
    """Rotate the webhook secret. Returns the new secret.

    Call this endpoint and update the GitHub webhook configuration with the
    returned value. The old secret stops working immediately.
    """
    import secrets as _secrets
    new_secret = _secrets.token_urlsafe(48)
    settings.GITHUB_WEBHOOK_SECRET = new_secret  # type: ignore[misc]
    logger.info("webhook: secret rotated (length=%d)", len(new_secret))
    return {"new_secret": new_secret}
