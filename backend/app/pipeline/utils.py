"""Shared utilities for pipeline nodes."""
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.pr_processing_status import PRProcessingStatus


async def update_layer_progress(
    agent_id: int,
    pr_number: int,
    layer_name: str,
    layer_result: dict
) -> None:
    """Update the processing status for a specific layer completion."""
    async with AsyncSessionLocal() as db:
        processing_status = await db.scalar(
            select(PRProcessingStatus).where(
                PRProcessingStatus.agent_id == agent_id,
                PRProcessingStatus.pr_number == pr_number
            )
        )
        if processing_status:
            # Update status to the current layer
            status_map = {
                "prompt_injection": "prompt_injection_check",
                "spam": "spam_check",
                "malicious_code": "malicious_code_check",
                "summary": "summary_generation"
            }
            processing_status.status = status_map.get(layer_name, processing_status.status)
            
            # Update layer_results
            if processing_status.layer_results is None:
                processing_status.layer_results = {}
            processing_status.layer_results[layer_name] = layer_result
            
            # Set started_at if not set
            if processing_status.started_at is None:
                processing_status.started_at = datetime.now(timezone.utc)
            
            await db.commit()
            
            # Log the progress update
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Updated PR #{pr_number} progress: layer={layer_name}, status={processing_status.status}")
