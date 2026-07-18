"""Shared utilities for pipeline nodes."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.pr_processing_status import PRProcessingStatus

logger = logging.getLogger(__name__)


def extract_json(raw: str) -> dict:
    """Best-effort parse of a JSON object from an LLM response.

    Handles the common failure modes: ```json code fences, prose before/after,
    and nested braces (naive ``{[^}]+}`` regexes break on all three). Returns {}
    if nothing parseable is found — callers decide the safe default.
    """
    if not raw:
        return {}
    text = raw.strip()
    # Strip code fences.
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()
    # Fast path.
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass
    # Brace-matched scan for the first balanced {...}.
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                    return obj if isinstance(obj, dict) else {}
                except (json.JSONDecodeError, ValueError):
                    return {}
    return {}


async def update_layer_progress(
    agent_id: int,
    pr_number: int,
    layer_name: str,
    layer_result: dict,
) -> None:
    """Update the processing status for a specific layer completion."""
    async with AsyncSessionLocal() as db:
        processing_status = await db.scalar(
            select(PRProcessingStatus).where(
                PRProcessingStatus.agent_id == agent_id,
                PRProcessingStatus.pr_number == pr_number,
            )
        )
        if not processing_status:
            return

        status_map = {
            "prompt_injection": "prompt_injection_check",
            "spam": "spam_check",
            "malicious_code": "malicious_code_check",
            "summary": "summary_generation",
        }
        processing_status.status = status_map.get(layer_name, processing_status.status)

        if processing_status.layer_results is None:
            processing_status.layer_results = {}
        # Reassign (not mutate) so SQLAlchemy detects the JSON change.
        processing_status.layer_results = {
            **processing_status.layer_results,
            layer_name: layer_result,
        }

        if processing_status.started_at is None:
            processing_status.started_at = datetime.now(timezone.utc)

        await db.commit()
        logger.info("PR #%s progress: layer=%s status=%s", pr_number, layer_name, processing_status.status)
