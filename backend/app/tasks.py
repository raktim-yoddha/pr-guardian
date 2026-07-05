"""Celery tasks for background PR processing and agent maintenance."""
from app.worker import celery_app
from app.pipeline.runner import run_pipeline


@celery_app.task(name="process_pr")
def process_pr_task(repo_full_name: str, pr_number: int, pr_url: str, author: str, pr_title: str = "", pr_body: str = ""):
    """Process a PR through the LangGraph pipeline."""
    import asyncio
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.pr_processing_status import PRProcessingStatus
    
    logger = logging.getLogger(__name__)
    
    async def _run():
        # Create a fresh engine for this task to avoid event loop issues
        engine = None
        session = None
        try:
            engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,  # Enable to detect stale connections
                pool_size=settings.WORKER_DB_POOL_SIZE,
                max_overflow=settings.WORKER_DB_MAX_OVERFLOW,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
            session_maker = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            
            session = session_maker()
            
            # Get the agent to retrieve installation_id
            agent = await session.scalar(
                select(Agent)
                .where(Agent.repo_full_name == repo_full_name)
                .where(Agent.is_active.is_(True))
                .order_by(Agent.id.desc())
                .limit(1)
            )
            
            if agent:
                logger.info(f"process_pr: agent_id={agent.id}, installation_id={agent.github_installation_id}")
            else:
                logger.warning(f"process_pr: no agent found for {repo_full_name}")
                # Update status to failed if no agent found
                processing_status = await session.scalar(
                    select(PRProcessingStatus).where(
                        PRProcessingStatus.agent_id == 0,  # We don't know the agent_id
                        PRProcessingStatus.pr_number == pr_number
                    )
                )
                if not processing_status:
                    # Try to find by repo_full_name through agent
                    processing_status = await session.scalar(
                        select(PRProcessingStatus).join(
                            Agent, PRProcessingStatus.agent_id == Agent.id
                        ).where(
                            Agent.repo_full_name == repo_full_name,
                            PRProcessingStatus.pr_number == pr_number
                        )
                    )
                if processing_status:
                    processing_status.status = "failed"
                    processing_status.error_message = "No active agent found for this repository"
                    processing_status.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                return
            
            try:
                # Update status to processing before running pipeline
                processing_status = await session.scalar(
                    select(PRProcessingStatus).where(
                        PRProcessingStatus.agent_id == agent.id,
                        PRProcessingStatus.pr_number == pr_number
                    )
                )
                if processing_status:
                    processing_status.status = "queued"
                    processing_status.started_at = datetime.now(timezone.utc)
                    processing_status.error_message = None
                    await session.commit()
                
                await run_pipeline(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    pr_url=pr_url,
                    author=author,
                    pr_title=pr_title,
                    pr_body=pr_body,
                )
            except Exception as exc:
                logger.exception(f"run_pipeline failed for PR #{pr_number}: {exc}")
                # Update status to failed
                processing_status = await session.scalar(
                    select(PRProcessingStatus).where(
                        PRProcessingStatus.agent_id == agent.id,
                        PRProcessingStatus.pr_number == pr_number
                    )
                )
                if processing_status:
                    processing_status.status = "failed"
                    processing_status.error_message = str(exc)[:500]
                    processing_status.completed_at = datetime.now(timezone.utc)
                    await session.commit()
        finally:
            if session:
                await session.close()
            if engine:
                await engine.dispose()
    
    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.exception(f"process_pr_task failed for PR #{pr_number}: {exc}")


@celery_app.task(name="poll_new_prs")
def poll_new_prs_task():
    """Poll GitHub for new PRs every 5 seconds for all active agents.
    
    This task runs continuously via Celery Beat to detect new PRs without
    relying on webhooks. It checks each active agent's repository for open PRs
    and queues any that haven't been processed yet.
    """
    import asyncio
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.agent import Agent
    from app.models.pr_event import PREvent
    from app.models.pr_processing_status import PRProcessingStatus
    from app.services.github import github_client
    
    logger = logging.getLogger(__name__)
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async def _run():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Agent).where(Agent.is_active == True)
                )
                agents = result.scalars().all()
                
                if not agents:
                    logger.debug("poll_new_prs: No active agents found")
                    return
                
                total_new_prs = 0
                
                for agent in agents:
                    try:
                        logger.debug(f"poll_new_prs: Checking {agent.repo_full_name} (agent_id={agent.id})")
                        
                        # Fetch open PRs from GitHub
                        prs = await github_client.list_pull_requests(
                            agent.repo_full_name, 
                            state="open", 
                            installation_id=agent.github_installation_id
                        )
                        
                        if not prs:
                            continue
                        
                        for pr in prs:
                            pr_number = pr.get("number")
                            pr_url = pr.get("html_url")
                            author = pr.get("user", {}).get("login")
                            pr_title = pr.get("title", "")
                            pr_body = pr.get("body", "")
                            
                            if not pr_number or not pr_url:
                                continue
                            
                            # Check if already processed (has a PREvent)
                            existing_event = await db.execute(
                                select(PREvent).where(
                                    PREvent.agent_id == agent.id,
                                    PREvent.pr_number == pr_number
                                )
                            )
                            if existing_event.scalar_one_or_none():
                                logger.debug(f"poll_new_prs: PR #{pr_number} already processed, skipping")
                                continue
                            
                            # Check if already in processing queue
                            existing_status = await db.scalar(
                                select(PRProcessingStatus).where(
                                    PRProcessingStatus.agent_id == agent.id,
                                    PRProcessingStatus.pr_number == pr_number
                                )
                            )
                            
                            if existing_status:
                                logger.debug(f"poll_new_prs: PR #{pr_number} already in queue (status={existing_status.status}), skipping")
                                continue
                            
                            # Create new processing status entry
                            processing_status = PRProcessingStatus(
                                agent_id=agent.id,
                                pr_number=pr_number,
                                pr_url=pr_url,
                                pr_title=pr_title,
                                author_github=author or "unknown",
                                status="queued",
                                detected_at=datetime.now(timezone.utc),
                                queued_at=datetime.now(timezone.utc)
                            )
                            db.add(processing_status)
                            await db.commit()
                            
                            logger.info(f"poll_new_prs: Detected new PR #{pr_number} in {agent.repo_full_name}")
                            total_new_prs += 1
                            
                            # Queue the PR for processing
                            process_pr_task.delay(
                                repo_full_name=agent.repo_full_name,
                                pr_number=pr_number,
                                pr_url=pr_url,
                                author=author or "unknown",
                                pr_title=pr_title,
                                pr_body=pr_body,
                            )
                    
                    except Exception as exc:
                        logger.exception(f"poll_new_prs: Failed to check agent {agent.id}: {exc}")
                
                if total_new_prs > 0:
                    logger.info(f"poll_new_prs: Detected and queued {total_new_prs} new PRs across all agents")
        
        loop.run_until_complete(_run())
    except Exception as exc:
        logger.exception(f"poll_new_prs_task failed: {exc}")
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass


@celery_app.task(name="sync_all_agents")
def sync_all_agents_task():
    """Trigger ingestion for all active agents and then process pending PRs."""
    import asyncio
    import logging
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.agent import Agent
    from app.services.ingestion import ingest_agent
    
    logger = logging.getLogger(__name__)
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async def _run():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Agent).where(Agent.is_active == True)
                )
                agents = result.scalars().all()
                
                if not agents:
                    logger.info("No active agents found for sync")
                    return
                
                for agent in agents:
                    try:
                        logger.info(f"Starting ingestion for agent {agent.id} ({agent.repo_full_name})")
                        # Update status to running before starting
                        agent.ingestion_status = "running"
                        await db.commit()
                        
                        await ingest_agent(agent.id)
                        logger.info(f"Completed ingestion for agent {agent.id}")
                    except Exception as exc:
                        logger.exception(f"Ingestion failed for agent {agent.id}: {exc}")
                        # Update status to failed on error
                        agent.ingestion_status = "failed"
                        await db.commit()
            
            # After ingestion, trigger pending PR processing
            logger.info("Ingestion complete, triggering pending PR processing")
            process_pending_prs_task.delay()
        
        loop.run_until_complete(_run())
    except Exception as exc:
        logger.exception(f"sync_all_agents_task failed: {exc}")
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass


@celery_app.task(name="process_pending_prs")
def process_pending_prs_task():
    """Process open PRs that existed before agent setup."""
    import asyncio
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.agent import Agent
    from app.models.pr_event import PREvent
    from app.models.pr_processing_status import PRProcessingStatus
    from app.services.github import github_client
    
    logger = logging.getLogger(__name__)
    
    # Create new event loop for this task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        async def _run():
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(Agent).where(Agent.is_active == True)
                )
                agents = result.scalars().all()
                
                if not agents:
                    logger.info("No active agents found for pending PR processing")
                    return
                
                logger.info(f"Processing pending PRs for {len(agents)} agents")
                
                for agent in agents:
                    try:
                        logger.info(f"Checking for open PRs in {agent.repo_full_name} (agent_id={agent.id}, installation_id={agent.github_installation_id})")
                        prs = await github_client.list_pull_requests(agent.repo_full_name, state="open", installation_id=agent.github_installation_id)
                        logger.info(f"GitHub API returned {len(prs) if prs else 0} PRs for {agent.repo_full_name}")
                        
                        if not prs:
                            logger.info(f"No open PRs found in {agent.repo_full_name}")
                            continue
                        
                        logger.info(f"Found {len(prs)} open PRs in {agent.repo_full_name}: {[pr.get('number') for pr in prs]}")
                        
                        for pr in prs:
                            pr_number = pr.get("number")
                            pr_url = pr.get("html_url")
                            author = pr.get("user", {}).get("login")
                            pr_title = pr.get("title", "")
                            pr_body = pr.get("body", "")
                            
                            if not pr_number or not pr_url:
                                logger.warning(f"Skipping PR with missing data: {pr}")
                                continue
                            
                            # Check if already processed
                            existing_event = await db.execute(
                                select(PREvent).where(
                                    PREvent.agent_id == agent.id,
                                    PREvent.pr_number == pr_number
                                )
                            )
                            if existing_event.scalar_one_or_none():
                                logger.info(f"PR #{pr_number} already processed, skipping")
                                continue
                            
                            # Create processing status entry if not exists
                            existing_status = await db.scalar(
                                select(PRProcessingStatus).where(
                                    PRProcessingStatus.agent_id == agent.id,
                                    PRProcessingStatus.pr_number == pr_number
                                )
                            )
                            if not existing_status:
                                processing_status = PRProcessingStatus(
                                    agent_id=agent.id,
                                    pr_number=pr_number,
                                    pr_url=pr_url,
                                    pr_title=pr_title,
                                    author_github=author or "unknown",
                                    status="queued",
                                    detected_at=datetime.now(timezone.utc),
                                    queued_at=datetime.now(timezone.utc)
                                )
                                db.add(processing_status)
                                await db.commit()
                                logger.info(f"Created processing status for PR #{pr_number} with status 'queued'")
                            
                            logger.info(f"Queueing PR #{pr_number} for processing")
                            process_pr_task.delay(
                                repo_full_name=agent.repo_full_name,
                                pr_number=pr_number,
                                pr_url=pr_url,
                                author=author or "unknown",
                                pr_title=pr_title,
                                pr_body=pr_body,
                            )
                    except Exception as exc:
                        logger.exception(f"Failed to process pending PRs for agent {agent.id}: {exc}")
        
        loop.run_until_complete(_run())
    except Exception as exc:
        logger.exception(f"process_pending_prs_task failed: {exc}")
    finally:
        # Clean up the event loop
        try:
            loop.close()
        except:
            pass


@celery_app.task(name="ensure_ollama_models")
def ensure_ollama_models_task():
    """Ensure required Ollama models are pulled."""
    import asyncio
    import httpx
    from app.core.config import settings
    
    if settings.LLM_PROVIDER != "ollama":
        return
    
    async def _run():
        models_to_check = [
            settings.OLLAMA_MODEL,
            settings.OLLAMA_EMBED_MODEL,
        ]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for model in models_to_check:
                try:
                    resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                    resp.raise_for_status()
                    existing_models = [m["name"] for m in resp.json().get("models", [])]
                    
                    if model not in existing_models:
                        pull_resp = await client.post(
                            f"{settings.OLLAMA_BASE_URL}/api/pull",
                            json={"name": model, "stream": False},
                            timeout=300.0,
                        )
                        pull_resp.raise_for_status()
                except Exception:
                    pass
    
    asyncio.run(_run())


@celery_app.task(name="retry_failed_prs")
def retry_failed_prs_task():
    """Automatically detect and retry stuck PRs at any layer.
    
    Handles:
    - Failed PRs (with retry limit)
    - PRs stuck at intermediate layers (timeout detection)
    - PRs stuck at queued without starting
    """
    import asyncio
    import logging
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, or_
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.core.config import settings
    from app.models.agent import Agent
    from app.models.pr_processing_status import PRProcessingStatus
    
    logger = logging.getLogger(__name__)
    MAX_RETRIES = 3
    RETRY_INTERVAL_SECONDS = 5
    LAYER_TIMEOUT_SECONDS = 300  # 5 minutes timeout for each layer
    QUEUED_TIMEOUT_SECONDS = 60  # 1 minute timeout for queued status
    
    logger.info("retry_failed_prs_task: Starting stuck PR detection")
    
    async def _run():
        # Create a fresh engine for this task to avoid event loop issues
        engine = None
        session = None
        try:
            engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_pre_ping=True,  # Enable to detect stale connections
                pool_size=settings.WORKER_DB_POOL_SIZE,
                max_overflow=settings.WORKER_DB_MAX_OVERFLOW,
                pool_recycle=3600,  # Recycle connections after 1 hour
            )
            session_maker = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            
            session = session_maker()
            
            now = datetime.now(timezone.utc)
            retry_cutoff = now - timedelta(seconds=RETRY_INTERVAL_SECONDS)
            layer_cutoff = now - timedelta(seconds=LAYER_TIMEOUT_SECONDS)
            queued_cutoff = now - timedelta(seconds=QUEUED_TIMEOUT_SECONDS)
            
            # Find PRs that need retry in multiple scenarios:
            # 1. Failed status with retry count under limit
            # 2. Stuck at intermediate layer for too long (started_at set but no completion)
            # 3. Stuck at queued for too long without starting
            result = await session.execute(
                select(PRProcessingStatus).where(
                    or_(
                        # Scenario 1: Failed with retries available
                        (PRProcessingStatus.status == "failed") &
                        (PRProcessingStatus.retry_count < MAX_RETRIES) &
                        ((PRProcessingStatus.last_retry_at.is_(None)) | 
                         (PRProcessingStatus.last_retry_at < retry_cutoff)),
                        
                        # Scenario 2: Stuck at intermediate layer (not completed, started too long ago)
                        (PRProcessingStatus.status.in_(["prompt_injection_check", "spam_check", "malicious_code_check", "summary_generation"])) &
                        (PRProcessingStatus.started_at.isnot(None)) &
                        (PRProcessingStatus.started_at < layer_cutoff) &
                        (PRProcessingStatus.completed_at.is_(None)),
                        
                        # Scenario 3: Stuck at queued without starting
                        (PRProcessingStatus.status == "queued") &
                        (PRProcessingStatus.started_at.is_(None)) &
                        (PRProcessingStatus.queued_at < queued_cutoff),
                        
                        # Scenario 4: Stuck at detected (legacy status - auto-convert to queued)
                        (PRProcessingStatus.status == "detected")
                    )
                )
            )
            stuck_statuses = result.scalars().all()
            
            if not stuck_statuses:
                logger.info("retry_failed_prs_task: No stuck PRs found")
                return
            
            logger.info(f"retry_failed_prs_task: Found {len(stuck_statuses)} stuck PRs to retry")
            
            for status in stuck_statuses:
                try:
                    # Get the agent
                    agent = await session.scalar(
                        select(Agent).where(Agent.id == status.agent_id)
                    )
                    
                    if not agent or not agent.is_active:
                        logger.warning(f"retry_failed_prs_task: Agent not found or inactive for PR #{status.pr_number}, skipping")
                        continue
                    
                    # Determine retry reason
                    if status.status == "failed":
                        reason = "failed"
                        status.retry_count += 1
                    elif status.status == "queued":
                        reason = "stuck_at_queued"
                        status.retry_count += 1
                    elif status.status == "detected":
                        reason = "legacy_detected_status"
                        status.retry_count += 1
                    else:
                        reason = f"stuck_at_{status.status}"
                        status.retry_count += 1
                    
                    if status.retry_count > MAX_RETRIES:
                        logger.warning(f"retry_failed_prs_task: PR #{status.pr_number} exceeded max retries ({status.retry_count}), marking as permanently failed")
                        status.status = "failed"
                        status.error_message = f"Exceeded maximum retries ({MAX_RETRIES}) - last stuck at: {reason}"
                        await session.commit()
                        continue
                    
                    # Reset status for retry
                    status.status = "queued"
                    status.error_message = None
                    status.started_at = None
                    status.completed_at = None
                    status.last_retry_at = now
                    # Set queued_at if it was detected (legacy status)
                    if status.queued_at is None:
                        status.queued_at = now
                    await session.commit()
                    
                    logger.info(f"retry_failed_prs_task: Retrying PR #{status.pr_number} (reason: {reason}, attempt {status.retry_count}/{MAX_RETRIES})")
                    
                    # Re-queue the PR for processing
                    process_pr_task.delay(
                        repo_full_name=agent.repo_full_name,
                        pr_number=status.pr_number,
                        pr_url=status.pr_url,
                        author=status.author_github,
                        pr_title=status.pr_title,
                        pr_body="",  # Will fetch from GitHub
                    )
                except Exception as exc:
                    logger.exception(f"retry_failed_prs_task: Failed to retry PR #{status.pr_number}: {exc}")
        finally:
            if session:
                await session.close()
            if engine:
                await engine.dispose()
    
    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.exception(f"retry_failed_prs_task failed: {exc}")
