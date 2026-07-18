"""RAG ingestion.

Fetches every text file (via the git tree + blobs) and every issue (with
comments) from the agent's repo, chunks everything, embeds it, and stores it in
the ``KnowledgeChunk`` table (pgvector). Tracks progress on the Agent row:
``ingestion_status`` pending → running → done|failed, plus ``last_ingested_at``
and ``chunk_count``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.agent import Agent
from app.models.ingestion_log import IngestionLog
from app.services.chunker import chunk_text, estimate_tokens
from app.services.embeddings import embed_one, embeddings_available
from app.services.github import GithubError, github_client
from app.services.vectorstore import vector_store

logger = logging.getLogger(__name__)


async def _maybe_embed(text: str) -> list[float] | None:
    """Embed with the local CPU model if available; else None (BM25-only fallback)."""
    if not embeddings_available():
        return None
    try:
        return await embed_one(text)
    except Exception:  # noqa: BLE001 — never fail ingestion over one embedding
        return None


async def _log_ingestion_step(
    agent_id: int,
    step: str,
    message: str,
    *,
    current: int | None = None,
    total: int | None = None,
    status: str = "info",
    update: bool = False,
) -> None:
    """Log an ingestion step to the database.
    
    If update=True, updates the most recent log entry for this step instead of creating a new one.
    """
    async with AsyncSessionLocal() as db:
        if update:
            # Update the most recent log entry for this step
            result = await db.execute(
                select(IngestionLog)
                .where(IngestionLog.agent_id == agent_id)
                .where(IngestionLog.step == step)
                .order_by(IngestionLog.created_at.desc())
                .limit(1)
            )
            log = result.scalar_one_or_none()
            if log:
                log.message = message
                log.current = current
                log.total = total
                log.status = status
                await db.commit()
                logger.info(f"ingestion[{agent_id}]: {step} - {message}")
                return
        
        log = IngestionLog(
            agent_id=agent_id,
            step=step,
            message=message,
            current=current,
            total=total,
            status=status,
        )
        db.add(log)
        await db.commit()
    logger.info(f"ingestion[{agent_id}]: {step} - {message}")


def _is_text_path(path: str) -> bool:
    if not path:
        return False
    lower = path.lower()
    # Filename-based matches (e.g. Dockerfile, .gitignore).
    basename = lower.rsplit("/", 1)[-1]
    name_hits = {"dockerfile", "license", "readme", "makefile", ".gitignore",
                 ".gitattributes", ".env.example", "requirements.txt"}
    if basename in name_hits:
        return True
    allowed = {ext.strip() for ext in settings.INGESTION_TEXT_EXTS.split(",") if ext.strip()}
    # Match by extension, including dotfiles.
    for ext in allowed:
        if lower.endswith(ext):
            return True
    return False


async def _fetch_repo_chunks(
    agent_id: int,
    repo_full_name: str, 
    branch: str | None, 
    provider: str, 
    installation_id: int | None = None
) -> list[tuple[str, str, list[float]]]:
    """Return (source_ref, content, embedding) triples for all repo files."""
    await _log_ingestion_step(agent_id, "fetch_repo_tree", f"Fetching repo tree for {repo_full_name}")
    blobs = await github_client.get_tree_blobs(repo_full_name, branch=branch, installation_id=installation_id)
    await _log_ingestion_step(agent_id, "fetch_repo_tree", f"Found {len(blobs)} blobs in repo tree")

    triples: list[tuple[str, str, list[float]]] = []
    processed = 0
    total_blobs = len(blobs[: settings.INGESTION_MAX_FILES])
    
    for blob in blobs[: settings.INGESTION_MAX_FILES]:
        path = blob.get("path", "")
        size = int(blob.get("size", 0) or 0)
        if not _is_text_path(path) or size == 0 or size > settings.INGESTION_MAX_FILE_BYTES:
            continue
        sha = blob.get("sha")
        if not sha:
            continue
        
        await _log_ingestion_step(agent_id, "fetch_file", f"Fetching {path}", current=processed, total=total_blobs, update=True)
        
        try:
            content = await github_client.get_blob_content(repo_full_name, sha, installation_id=installation_id)
        except GithubError as exc:
            await _log_ingestion_step(agent_id, "fetch_file", f"Skipping {path}: {exc}", status="warning", current=processed, total=total_blobs, update=True)
            continue
        
        processed += 1
        for chunk in chunk_text(content):
            text = f"# file: {path}\n{chunk.text}"
            embedding = await _maybe_embed(text)
            triples.append((path, text, embedding))

    await _log_ingestion_step(
        agent_id, 
        "fetch_repo_complete", 
        f"Processed {processed} files → {len(triples)} chunks",
        current=processed,
        total=len(triples),
        status="success"
    )
    return triples


async def _fetch_issue_chunks(
    agent_id: int,
    repo_full_name: str, 
    provider: str, 
    installation_id: int | None = None
) -> list[tuple[str, str, list[float]]]:
    """Return (source_ref, content, embedding) triples for issues + comments."""
    await _log_ingestion_step(agent_id, "fetch_issues", f"Fetching issues for {repo_full_name}")
    issues = await github_client.list_issues(repo_full_name, state="all", installation_id=installation_id)
    # GitHub's issues endpoint also returns PRs; filter PRs out.
    issues = [i for i in issues if "pull_request" not in i]
    await _log_ingestion_step(agent_id, "fetch_issues", f"Found {len(issues)} issues (excluding PRs)")

    triples: list[tuple[str, str, list[float]]] = []
    for idx, issue in enumerate(issues):
        number = issue.get("number")
        title = issue.get("title") or ""
        body = issue.get("body") or ""
        state = issue.get("state") or "open"
        ref = f"issues/{number}"
        
        if (idx + 1) % 5 == 0 or idx + 1 == len(issues):
            await _log_ingestion_step(
                agent_id,
                "process_issues",
                f"Processed {idx + 1}/{len(issues)} issues",
                current=idx + 1,
                total=len(issues)
            )

        try:
            comments = await github_client.get_issue_comments(repo_full_name, number, installation_id=installation_id)
        except GithubError:
            comments = []
        comment_bodies = [c.get("body") or "" for c in comments]

        text = f"# issue #{number} [{state}]: {title}\n\n{body}"
        if comment_bodies:
            text += "\n\n## comments\n" + "\n\n---\n\n".join(comment_bodies)

        for chunk in chunk_text(text):
            embedding = await _maybe_embed(chunk.text)
            triples.append((ref, chunk.text, embedding))

    await _log_ingestion_step(
        agent_id,
        "fetch_issues_complete",
        f"Processed {len(issues)} issues → {len(triples)} chunks",
        current=len(issues),
        total=len(triples),
        status="success"
    )
    return triples


async def _set_status(
    agent_id: int,
    status: str,
    *,
    chunk_count: int | None = None,
    last_ingested_at: datetime | None = None,
) -> None:
    values: dict = {"ingestion_status": status}
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if last_ingested_at is not None:
        values["last_ingested_at"] = last_ingested_at
    async with AsyncSessionLocal() as db:
        await db.execute(update(Agent).where(Agent.id == agent_id).values(**values))
        await db.commit()


async def _check_cancelled(agent_id: int) -> bool:
    """Check if ingestion was cancelled."""
    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if agent and agent.ingestion_status == "cancelled":
            await _log_ingestion_step(agent_id, "ingestion_cancelled", "Ingestion cancelled by user", status="warning")
            return True
    return False


async def ingest_agent(agent_id: int) -> int:
    """Run a full ingestion for an agent. Returns the chunk count stored."""
    async with AsyncSessionLocal() as db:
        agent = await db.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")
        repo_full_name = agent.repo_full_name
        installation_id = agent.github_installation_id

    provider = "local-embed" if embeddings_available() else "bm25-only"
    await _set_status(agent_id, "running")
    await _log_ingestion_step(
        agent_id,
        "ingestion_start",
        f"Starting ingestion for {repo_full_name} (retrieval: {provider})",
        status="info"
    )

    try:
        # Reset existing chunks for this agent (idempotent re-sync).
        await _log_ingestion_step(agent_id, "reset_vector_store", "Resetting vector store")
        await vector_store.reset(agent_id)
        await _log_ingestion_step(agent_id, "reset_vector_store", "Vector store reset complete", status="success")

        repo_triples = await _fetch_repo_chunks(agent_id, repo_full_name, None, provider, installation_id)
        
        if await _check_cancelled(agent_id):
            await _set_status(agent_id, "cancelled")
            raise RuntimeError("Ingestion cancelled")
        
        issue_triples = await _fetch_issue_chunks(agent_id, repo_full_name, provider, installation_id)
        
        if await _check_cancelled(agent_id):
            await _set_status(agent_id, "cancelled")
            raise RuntimeError("Ingestion cancelled")
        
        await _log_ingestion_step(
            agent_id,
            "store_chunks",
            f"Storing {len(repo_triples) + len(issue_triples)} chunks in vector store"
        )

        # Embedding already happened per-chunk above; build the store tuples.
        chunks = [
            ("repo", ref, content, embedding) for ref, content, embedding in repo_triples
        ] + [
            ("issue", ref, content, embedding) for ref, content, embedding in issue_triples
        ]

        stored = await vector_store.add(agent_id, chunks)

        await _set_status(
            agent_id,
            "done",
            chunk_count=stored,
            last_ingested_at=datetime.now(timezone.utc),
        )
        await _log_ingestion_step(
            agent_id,
            "ingestion_complete",
            f"Ingestion complete: {stored} chunks stored",
            current=stored,
            status="success"
        )
        return stored
    except RuntimeError as exc:
        if "cancelled" in str(exc):
            await _set_status(agent_id, "cancelled")
            raise
        await _log_ingestion_step(
            agent_id,
            "ingestion_error",
            f"Ingestion failed: {exc}",
            status="error"
        )
        await _set_status(agent_id, "failed")
        raise
    except Exception as exc:
        await _log_ingestion_step(
            agent_id,
            "ingestion_error",
            f"Ingestion failed: {exc}",
            status="error"
        )
        await _set_status(agent_id, "failed")
        raise
