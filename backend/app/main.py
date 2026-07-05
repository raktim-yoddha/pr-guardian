"""PR Guardian FastAPI application.

Wires all routers, configures CORS, structured logging, a health endpoint, and
attempts to enable the ``pgvector`` extension on startup (best-effort: only
needed when the vector DB is pgvector; failures are logged, not fatal, so the
app still boots if the extension isn't installed yet).
"""
from __future__ import annotations

import asyncio
import logging
import sys
import subprocess
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.events import router as events_router
from app.api.github import router as github_router
from app.api.github_oauth import router as github_oauth_router
from app.api.google_oauth import router as google_oauth_router
from app.api.webhooks import router as webhooks_router
from app.core.metrics import serialize_metrics
from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger("pr_guardian")


def _configure_logging() -> None:
    """JSON-ish structured logging to stdout.

    Keeps output parseable for the Phase 5 observability work without pulling in
    a heavier dependency now. Each record carries level, name, message, and
    process id.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "pid": %(process)d, "msg": %(message)r}'
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    for noisy in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def _try_enable_pgvector() -> None:
    """Best-effort ``CREATE EXTENSION IF NOT EXISTS vector``.

    Runs once at startup. Suppressed failures: the role lacks superuser/CREATEDB
    rights, or the extension image isn't built. Migrations that *use* the vector
    type will surface the real error later if it's genuinely missing.
    """
    from sqlalchemy import text

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        logger.info("startup: pgvector extension ensured")
    except Exception as exc:  # noqa: BLE001 — startup must not crash on this
        logger.warning("startup: could not enable pgvector (%s)", exc)


async def _run_alembic_upgrade() -> None:
    """Run ``alembic upgrade head`` at startup so migrations are always applied."""
    try:
        import sys
        import os
        # Use python -m alembic to ensure it runs from the virtual environment
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        if result.returncode != 0:
            logger.error("startup: alembic upgrade failed: %s", result.stderr.strip())
        else:
            logger.info("startup: alembic upgrade head succeeded")
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup: alembic upgrade error (%s)", exc)


async def _ensure_ollama_models() -> None:
    """Ensure required Ollama models are pulled at startup."""
    if settings.LLM_PROVIDER != "ollama":
        return
    
    import httpx
    models_to_check = [
        settings.OLLAMA_MODEL,
        settings.OLLAMA_EMBED_MODEL,
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in models_to_check:
            try:
                # Check if model exists
                resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                resp.raise_for_status()
                existing_models = [m["name"] for m in resp.json().get("models", [])]
                
                if model not in existing_models:
                    logger.info("startup: pulling Ollama model %s", model)
                    # Pull the model
                    pull_resp = await client.post(
                        f"{settings.OLLAMA_BASE_URL}/api/pull",
                        json={"name": model, "stream": False},
                        timeout=300.0,
                    )
                    pull_resp.raise_for_status()
                    logger.info("startup: successfully pulled model %s", model)
                else:
                    logger.info("startup: Ollama model %s already available", model)
            except Exception as exc:  # noqa: BLE001
                logger.warning("startup: could not ensure Ollama model %s (%s)", model, exc)


async def _sync_all_agents() -> None:
    """Trigger ingestion for all active agents on startup."""
    from sqlalchemy import select
    from app.core.database import async_session_maker
    from app.models.agent import Agent
    from app.services.ingestion import ingest_agent

    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Agent).where(Agent.is_active == True)
            )
            agents = result.scalars().all()

            if not agents:
                logger.info("startup: no active agents to sync")
                return

            logger.info("startup: syncing %d active agents", len(agents))
            for agent in agents:
                try:
                    logger.info("startup: triggering ingestion for agent %d (%s)", agent.id, agent.name)
                    await ingest_agent(agent.id)
                    logger.info("startup: ingestion completed for agent %d", agent.id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("startup: ingestion failed for agent %d (%s)", agent.id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup: agent sync error (%s)", exc)


async def _process_pending_prs() -> None:
    """Process open PRs that existed before agent setup."""
    from sqlalchemy import select
    from app.core.database import async_session_maker
    from app.models.agent import Agent
    from app.models.pr_event import PREvent
    from app.services.github import github_client
    from app.pipeline.runner import run_pipeline
    from app.tasks import process_pr_task

    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Agent).where(Agent.is_active == True)
            )
            agents = result.scalars().all()

            if not agents:
                logger.info("startup: no active agents to check for pending PRs")
                return

            logger.info("startup: checking for pending PRs across %d agents", len(agents))
            for agent in agents:
                try:
                    # Fetch open PRs for this repo
                    prs = await github_client.list_pull_requests(agent.repo_full_name, state="open", installation_id=agent.github_installation_id)
                    
                    if not prs:
                        logger.info("startup: no open PRs for %s", agent.repo_full_name)
                        continue

                    logger.info("startup: found %d open PRs for %s", len(prs), agent.repo_full_name)
                    
                    for pr in prs:
                        pr_number = pr.get("number")
                        pr_url = pr.get("html_url")
                        author = pr.get("user", {}).get("login")
                        pr_title = pr.get("title", "")
                        
                        if not pr_number or not pr_url:
                            continue

                        # Check if this PR was already processed
                        existing_event = await db.execute(
                            select(PREvent).where(
                                PREvent.agent_id == agent.id,
                                PREvent.pr_number == pr_number
                            )
                        )
                        if existing_event.scalar_one_or_none():
                            logger.info("startup: PR #%d already processed, skipping", pr_number)
                            continue

                        logger.info("startup: queuing PR #%d from %s for processing", pr_number, agent.repo_full_name)
                        
                        # Use Celery to process the PR asynchronously
                        process_pr_task.delay(
                            agent_id=agent.id,
                            repo_full_name=agent.repo_full_name,
                            pr_number=pr_number,
                            pr_url=pr_url,
                            pr_title=pr_title,
                            pr_body=pr.get("body", ""),
                            pr_author=author or "unknown",
                        )

                except Exception as exc:  # noqa: BLE001
                    logger.error("startup: failed to process pending PRs for agent %d (%s)", agent.id, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup: pending PR processing error (%s)", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger.info("startup: %s starting", settings.APP_NAME)
    
    # Essential startup tasks - these must complete before app is ready
    await _try_enable_pgvector()
    await _run_alembic_upgrade()
    
    # Ollama model check is now optional and non-blocking
    # Models will be pulled on-demand by the Celery workers
    logger.info("startup: skipping Ollama model pull (handled by workers)")
    
    # Heavy tasks removed from startup - handled by Celery workers
    # Agent sync and pending PR processing now run in separate Celery worker process
    logger.info("startup: background tasks delegated to Celery workers")
    
    # App is now ready to receive requests
    yield
    
    logger.info("shutdown: disposing database engine")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="RAG-powered agentic GitHub PR management.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(github_router)
app.include_router(github_oauth_router)
app.include_router(google_oauth_router)
app.include_router(agents_router)
app.include_router(events_router)
app.include_router(dashboard_router)
app.include_router(webhooks_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/metrics", tags=["meta"])
async def metrics():
    """Prometheus-style metrics (no external dependency)."""
    from starlette.responses import PlainTextResponse
    return PlainTextResponse(serialize_metrics(), media_type="text/plain")
