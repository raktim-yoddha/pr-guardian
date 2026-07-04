"""Celery tasks for background PR processing."""
from app.worker import celery_app
from app.pipeline.runner import run_pipeline


@celery_app.task(name="process_pr")
def process_pr_task(repo_full_name: str, pr_number: int, pr_url: str, author: str):
    """Process a PR through the LangGraph pipeline."""
    import asyncio
    from app.core.database import AsyncSessionLocal
    
    async def _run():
        async with AsyncSessionLocal() as db:
            await run_pipeline(
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                pr_url=pr_url,
                author=author,
                db=db,
            )
    
    asyncio.run(_run())
