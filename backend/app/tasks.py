"""Background PR processing.

No Celery/Redis/worker process: PRs run in-process via FastAPI ``BackgroundTasks``
(webhook + agent-setup scan). ``run_pipeline`` owns all status bookkeeping and
never raises into the caller, so these are thin dispatchers.
"""
from __future__ import annotations

import logging

from app.pipeline.runner import run_pipeline

logger = logging.getLogger(__name__)


async def process_pr(
    repo_full_name: str,
    pr_number: int,
    pr_url: str,
    author: str,
    pr_title: str = "",
    pr_body: str = "",
) -> None:
    """Run one PR through the pipeline. Safe to schedule as a background task."""
    try:
        await run_pipeline(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            pr_url=pr_url,
            author=author,
            pr_title=pr_title,
            pr_body=pr_body,
        )
    except Exception:  # noqa: BLE001 — background task must never surface
        logger.exception("process_pr failed for PR #%s on %s", pr_number, repo_full_name)
