"""Agent CRUD endpoints: create, list, get, update, delete, sync.

Ownership is enforced: every query scopes agents to the current user.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DBSession
from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.ingestion_log import IngestionLog
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.schemas.ingestion_log import IngestionLogRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


async def _detect_prs_for_agent(
    agent_id: int,
    db: DBSession,
) -> int:
    """Internal function to detect PRs for an agent."""
    from datetime import datetime, timezone
    from app.models.pr_event import PREvent
    from app.models.pr_processing_status import PRProcessingStatus
    from app.services.github import github_client
    
    agent = await db.get(Agent, agent_id)
    if not agent:
        return 0
    
    try:
        prs = await github_client.list_pull_requests(agent.repo_full_name, state="open", installation_id=agent.github_installation_id)
        
        if not prs:
            return 0
        
        detected_count = 0
        for pr in prs:
            pr_number = pr.get("number")
            pr_url = pr.get("html_url")
            author = pr.get("user", {}).get("login")
            pr_title = pr.get("title", "")
            
            if not pr_number or not pr_url:
                continue
            
            # Check if already processed
            existing_event = await db.execute(
                select(PREvent).where(
                    PREvent.agent_id == agent.id,
                    PREvent.pr_number == pr_number
                )
            )
            if existing_event.scalar_one_or_none():
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
                    status="detected",
                    detected_at=datetime.now(timezone.utc)
                )
                db.add(processing_status)
                detected_count += 1
        
        await db.commit()
        return detected_count
    except Exception as exc:
        logger.exception(f"PR detection failed for agent {agent_id}: {exc}")
        return 0


@router.get("", response_model=list[AgentRead])
async def list_agents(current_user: CurrentUser, db: DBSession) -> list[Agent]:
    result = await db.execute(
        select(Agent)
        .where(Agent.user_id == current_user.id)
        .order_by(Agent.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    current_user: CurrentUser,
    db: DBSession,
    background_tasks: BackgroundTasks,
) -> Agent:
    agent = Agent(
        user_id=current_user.id,
        name=payload.name,
        repo_full_name=payload.repo_full_name,
        llm_provider=payload.llm_provider,
        vector_db_type=payload.vector_db_type,
        github_installation_id=payload.github_installation_id,
        is_active=True,
        ingestion_status="pending",
    )
    db.add(agent)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create agent (invalid input)",
        ) from exc
    await db.refresh(agent)

    # Run ingestion in background so agent creation returns immediately
    background_tasks.add_task(_run_ingestion_and_detection, agent.id)
    
    return agent


async def _run_ingestion_and_detection(agent_id: int) -> None:
    """Background task to run ingestion and PR detection for an agent."""
    from app.services.ingestion import ingest_agent
    
    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if not agent:
            return
        
        try:
            agent.ingestion_status = "running"
            await db.commit()
            await ingest_agent(agent_id)
            # Trigger PR detection after successful ingestion
            await _detect_prs_for_agent(agent_id, db)
        except Exception as exc:
            logger.exception(f"Initial ingestion failed for agent {agent_id}: {exc}")
            agent.ingestion_status = "failed"
            await db.commit()


async def _get_owned_or_404(db: DBSession, agent_id: int, user_id: int) -> Agent:
    """Fetch an agent owned by ``user_id`` or raise 404."""
    agent = await db.get(Agent, agent_id)
    if agent is None or agent.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found"
        )
    return agent


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: int, current_user: CurrentUser, db: DBSession
) -> Agent:
    return await _get_owned_or_404(db, agent_id, current_user.id)


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: int,
    payload: AgentUpdate,
    current_user: CurrentUser,
    db: DBSession,
) -> Agent:
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}/progress", response_model=dict)
async def get_agent_progress(
    agent_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get real-time progress for an agent's ingestion and PR processing."""
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    
    from sqlalchemy import select
    from app.models.pr_processing_status import PRProcessingStatus
    
    # Get PR processing status for this agent
    result = await db.execute(
        select(PRProcessingStatus).where(PRProcessingStatus.agent_id == agent_id)
    )
    pr_statuses = result.scalars().all()
    
    # Count PRs by status
    pr_counts = {}
    for status in pr_statuses:
        pr_counts[status.status] = pr_counts.get(status.status, 0) + 1
    
    return {
        "agent_id": agent.id,
        "agent_name": agent.name,
        "repo_full_name": agent.repo_full_name,
        "ingestion_status": agent.ingestion_status,
        "ingestion_chunk_count": agent.chunk_count,
        "last_ingested_at": agent.last_ingested_at.isoformat() if agent.last_ingested_at else None,
        "pr_processing": {
            "total_prs": len(pr_statuses),
            "by_status": pr_counts,
            "recent_prs": [
                {
                    "pr_number": s.pr_number,
                    "pr_url": s.pr_url,
                    "status": s.status,
                    "detected_at": s.detected_at.isoformat() if s.detected_at else None,
                    "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                }
                for s in sorted(pr_statuses, key=lambda x: x.detected_at or x.updated_at, reverse=True)[:5]
            ]
        }
    }


@router.get("/{agent_id}/ingestion-logs", response_model=list[IngestionLogRead])
async def get_agent_ingestion_logs(
    agent_id: int,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 100,
) -> list[IngestionLog]:
    """Get ingestion progress logs for an agent."""
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    
    result = await db.execute(
        select(IngestionLog)
        .where(IngestionLog.agent_id == agent_id)
        .order_by(IngestionLog.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("/{agent_id}/sync", response_model=AgentRead)
async def sync_agent(
    agent_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> Agent:
    """Manually trigger sync (ingestion + PR detection) for an agent."""
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    
    # Reset ingestion status to pending before triggering sync
    agent.ingestion_status = "running"
    await db.commit()
    await db.refresh(agent)
    
    # Run ingestion synchronously (bypass Celery for reliability)
    from app.services.ingestion import ingest_agent
    try:
        await ingest_agent(agent.id)
        # Trigger PR detection after successful ingestion
        await _detect_prs_for_agent(agent.id, db)
    except Exception as exc:
        logger.exception(f"Sync failed for agent {agent_id}: {exc}")
        agent.ingestion_status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(exc)}"
        )
    
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/cancel-sync", response_model=AgentRead)
async def cancel_sync(
    agent_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> Agent:
    """Cancel an ongoing sync for an agent."""
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    
    if agent.ingestion_status not in ["running", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No sync in progress to cancel"
        )
    
    agent.ingestion_status = "cancelled"
    await db.commit()
    await db.refresh(agent)
    
    return agent


@router.post("/{agent_id}/detect-prs", response_model=dict)
async def detect_prs(
    agent_id: int,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """Manually trigger PR detection for an agent without re-ingesting."""
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    
    # Run PR detection synchronously (bypass Celery for reliability)
    from datetime import datetime, timezone
    from app.models.pr_event import PREvent
    from app.models.pr_processing_status import PRProcessingStatus
    from app.services.github import github_client
    
    try:
        prs = await github_client.list_pull_requests(agent.repo_full_name, state="open", installation_id=agent.github_installation_id)
        
        if not prs:
            return {"status": "success", "message": "No open PRs found", "detected_count": 0}
        
        detected_count = 0
        for pr in prs:
            pr_number = pr.get("number")
            pr_url = pr.get("html_url")
            author = pr.get("user", {}).get("login")
            pr_title = pr.get("title", "")
            pr_body = pr.get("body", "")
            
            if not pr_number or not pr_url:
                continue
            
            # Check if already processed
            existing_event = await db.execute(
                select(PREvent).where(
                    PREvent.agent_id == agent.id,
                    PREvent.pr_number == pr_number
                )
            )
            if existing_event.scalar_one_or_none():
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
                    status="detected",
                    detected_at=datetime.now(timezone.utc)
                )
                db.add(processing_status)
                detected_count += 1
        
        await db.commit()
        return {"status": "success", "message": f"Detected {detected_count} new PRs", "detected_count": detected_count}
    except Exception as exc:
        logger.exception(f"PR detection failed for agent {agent_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PR detection failed: {str(exc)}"
        )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: int, current_user: CurrentUser, db: DBSession
) -> None:
    agent = await _get_owned_or_404(db, agent_id, current_user.id)
    await db.delete(agent)
    await db.commit()
