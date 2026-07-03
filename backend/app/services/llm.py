"""LLM + embedding abstraction — Ollama only.

Per AGENTS.md every node and service calls ``get_embedding`` /
``get_llm_response`` — never the provider APIs directly.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.services.resilience import retry_async

logger = logging.getLogger(__name__)

Provider = Literal["ollama"]


# --------------------------------------------------------------------------- chat


async def _ollama_chat(
    prompt: str, system: str, model: str, *, temperature: float
) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {"temperature": temperature},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


async def get_llm_response(
    prompt: str,
    system: str = "",
    *,
    provider: Provider | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> str:
    """Return the model's text response for ``prompt``.

    Args:
        prompt: The user message (PR content wrapped in XML delimiters upstream).
        system: Injection-resistant system prompt.
        provider: Override the default provider; defaults to settings.
        model: Override the default model for the chosen provider.
        temperature: 0.0–1.0; default 0.2 for deterministic decisions.
    """
    provider = provider or settings.LLM_PROVIDER  # type: ignore[assignment]
    model = model or settings.OLLAMA_MODEL

    try:
        return await retry_async(
            lambda: _ollama_chat(prompt, system, model, temperature=temperature),
            description="ollama_chat",
        )
    except httpx.HTTPError as exc:
        logger.error("LLM provider %s request failed: %s", provider, exc)
        raise


# --------------------------------------------------------------------- embeddings


async def _ollama_embed(text: str, model: str) -> list[float]:
    """Embed text via Ollama. Uses the modern /api/embed endpoint.

    Ollama 0.1.13+ renamed /api/embeddings → /api/embed and changed the response
    shape from {"embedding": [...]} to {"embeddings": [[...]]}. This handles both
    so it works on any version.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Try the new /api/embed endpoint first.
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": model, "input": text},
        )
        if resp.status_code == 404:
            # Fall back to the legacy /api/embeddings endpoint for old Ollama.
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                json={"model": model, "prompt": text},
            )
        resp.raise_for_status()
        data = resp.json()
        # New shape: {"embeddings": [[...]]}; legacy: {"embedding": [...]}
        if "embeddings" in data:
            return list(data["embeddings"][0])
        return list(data["embedding"])


async def get_embedding(
    text: str, *, provider: Provider | None = None, model: str | None = None
) -> list[float]:
    """Return the embedding vector for ``text``."""
    provider = provider or settings.LLM_PROVIDER  # type: ignore[assignment]
    model = model or settings.OLLAMA_EMBED_MODEL

    try:
        return await retry_async(
            lambda: _ollama_embed(text, model),
            description="ollama_embed",
        )
    except httpx.HTTPError as exc:
        logger.error("Embedding provider %s request failed: %s", provider, exc)
        raise


async def embed_batch(
    texts: list[str], *, provider: Provider | None = None
) -> list[list[float]]:
    """Embed multiple texts sequentially (provider rate-limits make this safest).

    Used by ingestion. Batching could be added later but most repos fit fine.
    """
    return [await get_embedding(t, provider=provider) for t in texts]


# --------------------------------------------------------------------------- helpers


def resolve_provider(agent: Any) -> Provider:
    """Pick the provider for an agent, falling back to the global default."""
    return "ollama"  # type: ignore[return-value]
