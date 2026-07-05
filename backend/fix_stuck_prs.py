"""Fix stuck PRs in the database.

This script updates PRs that are stuck in 'detected' or 'queued' status
and re-queues them for processing through the worker pipeline.
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.pr_processing_status import PRProcessingStatus
from sqlalchemy import select


async def fix_stuck_prs():
    """Update stuck PRs and re-queue them for processing."""
    async with AsyncSessionLocal() as db:
        # Find PRs stuck in 'detected' status (10%)
        detected_result = await db.execute(
            select(PRProcessingStatus).where(
                PRProcessingStatus.status == "detected"
            )
        )
        detected_prs = detected_result.scalars().all()
        
        # Find PRs stuck in 'queued' status (20%) that haven't been processed
        queued_result = await db.execute(
            select(PRProcessingStatus).where(
                PRProcessingStatus.status == "queued",
                PRProcessingStatus.started_at.is_(None)
            )
        )
        queued_prs = queued_result.scalars().all()
        
        total_fixed = 0
        
        # Fix detected PRs
        for pr_status in detected_prs:
            pr_status.status = "queued"
            pr_status.queued_at = datetime.now(timezone.utc)
            total_fixed += 1
            print(f"Fixed PR #{pr_status.pr_number}: detected -> queued")
        
        # Fix queued PRs that never started
        for pr_status in queued_prs:
            # Reset timestamps to force re-processing
            pr_status.queued_at = datetime.now(timezone.utc)
            pr_status.started_at = None
            pr_status.completed_at = None
            pr_status.error_message = None
            pr_status.retry_count = 0
            pr_status.last_retry_at = None
            total_fixed += 1
            print(f"Reset PR #{pr_status.pr_number}: queued (stuck) -> queued (reset)")
        
        await db.commit()
        print(f"\nTotal PRs fixed: {total_fixed}")
        
        # Show current status of all PRs
        print("\nCurrent PR status summary:")
        all_result = await db.execute(
            select(PRProcessingStatus).order_by(PRProcessingStatus.detected_at.desc())
        )
        all_prs = all_result.scalars().all()
        
        status_counts = {}
        for pr in all_prs:
            status = pr.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")


if __name__ == "__main__":
    asyncio.run(fix_stuck_prs())
