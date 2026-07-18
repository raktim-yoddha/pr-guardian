"""RAG retrieval helpers with hybrid BM25 + vector search.

``retrieve`` combines BM25 keyword scoring with vector similarity to return
the top-K most relevant knowledge chunks for an agent.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.embeddings import embed_one, embeddings_available
from app.services.vectorstore import ChunkHit, vector_store


class BM25Index:
    """BM25 index for keyword-based retrieval."""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs: dict[int, Counter] = {}
        self.idf: dict[str, float] = {}
        self.doc_lengths: dict[int, int] = {}
        self.avg_doc_length: float = 0.0
        self.total_docs: int = 0
    
    async def build_index(self, agent_id: int) -> None:
        """Build BM25 index from knowledge chunks for an agent."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(KnowledgeChunk).where(KnowledgeChunk.agent_id == agent_id)
            )
            chunks = result.scalars().all()
        
        if not chunks:
            return
        
        self.total_docs = len(chunks)
        self.doc_freqs = {}
        self.doc_lengths = {}
        
        # Tokenize and count term frequencies per document
        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            self.doc_freqs[chunk.id] = Counter(tokens)
            self.doc_lengths[chunk.id] = len(tokens)
        
        # Calculate average document length
        self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs
        
        # Calculate IDF for all terms
        all_terms = set()
        for freqs in self.doc_freqs.values():
            all_terms.update(freqs.keys())
        
        for term in all_terms:
            # Number of documents containing the term
            df = sum(1 for freqs in self.doc_freqs.values() if term in freqs)
            # IDF with smoothing
            self.idf[term] = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)
    
    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization by splitting on non-alphanumeric characters."""
        import re
        return re.findall(r'\b\w+\b', text.lower())
    
    def score(self, chunk_id: int, query: str) -> float:
        """Calculate BM25 score for a document given a query."""
        if chunk_id not in self.doc_freqs:
            return 0.0
        
        query_terms = self._tokenize(query)
        doc_freqs = self.doc_freqs[chunk_id]
        doc_length = self.doc_lengths[chunk_id]
        
        score = 0.0
        for term in query_terms:
            if term in doc_freqs:
                tf = doc_freqs[term]
                idf = self.idf.get(term, 0.0)
                # BM25 formula
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
                score += idf * (numerator / denominator)
        
        return score


# Global BM25 index cache: {agent_id: BM25Index}
_bm25_cache: dict[int, BM25Index] = {}


async def _get_bm25_index(agent_id: int) -> BM25Index:
    """Get or build BM25 index for an agent."""
    if agent_id not in _bm25_cache:
        index = BM25Index()
        await index.build_index(agent_id)
        _bm25_cache[agent_id] = index
    return _bm25_cache[agent_id]


def _normalize_scores(scores: list[float]) -> list[float]:
    """Normalize scores to [0, 1] range."""
    if not scores:
        return []
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [0.5] * len(scores)
    return [(s - min_score) / (max_score - min_score) for s in scores]


async def retrieve(
    agent,
    query: str,
    k: int = 8,
    alpha: float = 0.5,
) -> list[ChunkHit]:
    """Return the top-K chunk hits for ``query`` against ``agent``'s KB using hybrid search.
    
    Args:
        agent: The agent to search against
        query: The search query
        k: Number of results to return
        alpha: Weight for vector search (0-1). BM25 weight is (1-alpha).
    """
    # Load all chunks once.
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.agent_id == agent.id)
        )
        chunks = list(result.scalars().all())
    if not chunks:
        return []

    # BM25 keyword scores (always available).
    bm25_index = await _get_bm25_index(agent.id)
    bm25_by_content: dict[str, float] = {c.content: bm25_index.score(c.id, query) for c in chunks}

    # Vector scores — only if the local embedding model loaded. Otherwise BM25-only.
    vector_by_content: dict[str, float] = {}
    use_vector = embeddings_available()
    if use_vector:
        try:
            query_embedding = await embed_one(query)
            for hit in await vector_store.search(agent.id, query_embedding, k=k * 2):
                vector_by_content[hit.content] = hit.score
        except Exception:  # noqa: BLE001 — degrade to BM25-only on any embedding failure
            use_vector = False

    contents = [c.content for c in chunks]
    norm_bm25 = dict(zip(contents, _normalize_scores([bm25_by_content.get(x, 0.0) for x in contents])))
    if use_vector:
        norm_vec = dict(zip(contents, _normalize_scores([vector_by_content.get(x, 0.0) for x in contents])))
    else:
        alpha = 0.0  # BM25-only weighting
        norm_vec = {x: 0.0 for x in contents}

    scored = [
        (
            ChunkHit(content=c.content, source_type=c.source_type, source_ref=c.source_ref,
                     score=alpha * norm_vec[c.content] + (1 - alpha) * norm_bm25[c.content]),
            alpha * norm_vec[c.content] + (1 - alpha) * norm_bm25[c.content],
        )
        for c in chunks
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [hit for hit, _ in scored[:k]]


async def retrieve_texts(agent, query: str, k: int = 8) -> list[str]:
    """Convenience wrapper returning just the chunk contents as strings."""
    hits = await retrieve(agent, query, k=k)
    return [h.content for h in hits]
