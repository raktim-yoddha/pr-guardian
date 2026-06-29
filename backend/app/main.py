"""PR Guardian FastAPI application.

Wires all routers, configures CORS, structured logging, a health endpoint, and
attempts to enable the ``pgvector`` extension on startup (best-effort: only
needed when the vector DB is pgvector; failures are logged, not fatal, so the
app still boots if the extension isn't installed yet).
"""
from __future__ import annotations

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
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("startup: alembic upgrade failed: %s", result.stderr.strip())
        else:
            logger.info("startup: alembic upgrade head succeeded")
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup: alembic upgrade error (%s)", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    logger.info("startup: %s starting", settings.APP_NAME)
    await _try_enable_pgvector()
    await _run_alembic_upgrade()
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
