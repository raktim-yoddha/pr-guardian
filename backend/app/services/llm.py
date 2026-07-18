"""LLM chat abstraction — groq / gemini / ollama.

Every node calls ``get_llm_response`` (or ``llm_from_state``); never a provider
API directly. Embeddings live in ``services.embeddings`` (local CPU, fastembed).

Provider + API key resolve per agent: the agent owner's stored BYO key wins,
else the server's env-default provider + key. Resolution is done once in the
pipeline runner and carried on ``PRState`` so nodes don't re-hit the DB.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

import httpx

from app.core.config import settings
from app.services.resilience import retry_async

logger = logging.getLogger(__name__)

Provider = Literal["groq", "gemini", "ollama"]

# Re-exported so existing callers (ingestion/rag) keep importing from here.
from app.services.embeddings import (  # noqa: E402,F401
    embed_one as get_embedding_raw,
    embed_texts as embed_batch,
    embeddings_available,
)


# --------------------------------------------------------------------- providers


async def _groq_chat(prompt: str, system: str, model: str, api_key: str, *, temperature: float, max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _gemini_chat(prompt: str, system: str, model: str, api_key: str, *, temperature: float, max_tokens: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            url,
            params={"key": api_key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()


async def _ollama_chat(prompt: str, system: str, model: str, base_url: str, *, temperature: float, max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()


# --------------------------------------------------------------------- resolution


def _default_key(provider: str) -> str | None:
    return {"groq": settings.GROQ_API_KEY, "gemini": settings.GEMINI_API_KEY, "ollama": "local"}.get(provider)


def _default_model(provider: str) -> str:
    return {"groq": settings.GROQ_MODEL, "gemini": settings.GEMINI_MODEL, "ollama": settings.OLLAMA_MODEL}[provider]


def resolve_llm_config(user: Any | None) -> dict:
    """Resolve (provider, model, api_key, base_url) for a user's LLM calls.

    Precedence: the user's stored BYO provider + decrypted key → env-default
    provider + env key. ``user`` may be None (webhook flows) → env defaults.
    """
    from app.core.security import decrypt_secret

    provider = settings.LLM_PROVIDER
    api_key = _default_key(provider)
    base_url = settings.OLLAMA_BASE_URL

    if user is not None and getattr(user, "preferred_provider", None):
        provider = user.preferred_provider  # type: ignore[assignment]
        base_url = getattr(user, "ollama_base_url", None) or settings.OLLAMA_BASE_URL
        raw_keys = getattr(user, "encrypted_api_keys", None)
        api_key = _default_key(provider)  # env fallback for the chosen provider
        if raw_keys:
            try:
                enc = json.loads(raw_keys).get(provider)
                if enc:
                    dec = decrypt_secret(enc)
                    if dec:
                        api_key = dec
            except (ValueError, TypeError):
                pass

    return {
        "provider": provider,
        "model": _default_model(provider),
        "api_key": api_key,
        "base_url": base_url,
    }


# --------------------------------------------------------------------------- chat


async def get_llm_response(
    prompt: str,
    system: str = "",
    *,
    provider: Provider | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """Return the model's text response. Provider/key default to the env config."""
    provider = provider or settings.LLM_PROVIDER  # type: ignore[assignment]
    model = model or _default_model(provider)
    api_key = api_key or _default_key(provider)
    base_url = base_url or settings.OLLAMA_BASE_URL

    if provider != "ollama" and not api_key:
        raise RuntimeError(f"No API key configured for provider {provider!r}")

    if provider == "groq":
        call = lambda: _groq_chat(prompt, system, model, api_key, temperature=temperature, max_tokens=max_tokens)  # type: ignore[arg-type]
    elif provider == "gemini":
        call = lambda: _gemini_chat(prompt, system, model, api_key, temperature=temperature, max_tokens=max_tokens)  # type: ignore[arg-type]
    else:
        call = lambda: _ollama_chat(prompt, system, model, base_url, temperature=temperature, max_tokens=max_tokens)

    try:
        return await retry_async(call, description=f"{provider}_chat")
    except httpx.HTTPError as exc:
        logger.error("LLM provider %s request failed: %s", provider, exc)
        raise


async def llm_from_state(state: dict, prompt: str, system: str = "", **kwargs: Any) -> str:
    """Call the LLM using the provider/key resolved onto ``PRState`` by the runner."""
    return await get_llm_response(
        prompt,
        system,
        provider=state.get("llm_provider"),
        model=state.get("llm_model"),
        api_key=state.get("llm_api_key"),
        base_url=state.get("llm_base_url"),
        **kwargs,
    )


# ---------------------------------------------------------------- embeddings shim


async def get_embedding(text: str, *, provider: Any = None, model: Any = None) -> list[float]:
    """Embed ``text`` via the local CPU model. ``provider``/``model`` ignored (kept
    for backward-compatible call sites in ingestion/rag)."""
    return await get_embedding_raw(text)
