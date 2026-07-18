"""Local CPU embeddings via fastembed (ONNX runtime).

No external service, no API key, no GPU — the model downloads once (~130MB for
bge-small) and runs on the host CPU. fastembed is synchronous, so every call is
pushed to a thread to keep the event loop free.

If fastembed is unavailable (import fails or model can't load), embeddings are
disabled and RAG degrades to BM25-only keyword search (see services/rag.py).
"""
from __future__ import annotations

import asyncio
import logging
import threading

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_load_lock = threading.Lock()
_load_failed = False


def _get_model():
    """Lazily load the fastembed model once (thread-safe). Returns None if unavailable."""
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    with _load_lock:
        if _model is not None or _load_failed:
            return _model
        try:
            from fastembed import TextEmbedding  # type: ignore[import-not-found]

            logger.info("embeddings: loading fastembed model %s", settings.EMBED_MODEL)
            _model = TextEmbedding(model_name=settings.EMBED_MODEL)
            logger.info("embeddings: model ready")
        except Exception as exc:  # noqa: BLE001 — never crash the app over embeddings
            logger.warning("embeddings: fastembed unavailable (%s); RAG falls back to BM25", exc)
            _load_failed = True
    return _model


def embeddings_available() -> bool:
    """True if the local embedding model loaded successfully."""
    return _get_model() is not None


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    if model is None:
        raise RuntimeError("embeddings unavailable")
    return [vec.tolist() for vec in model.embed(texts)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts on a worker thread. Raises if embeddings unavailable."""
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)


async def embed_one(text: str) -> list[float]:
    """Embed a single text. Raises RuntimeError if embeddings unavailable."""
    out = await embed_texts([text])
    return out[0]


if __name__ == "__main__":  # ponytail: one runnable check
    import asyncio as _a

    async def _demo():
        if not embeddings_available():
            print("fastembed not installed — skipping (BM25 fallback path)")
            return
        v = await embed_one("hello world")
        assert len(v) == settings.EMBEDDING_DIM, f"dim {len(v)} != {settings.EMBEDDING_DIM}"
        print(f"ok: dim={len(v)}")

    _a.run(_demo())
