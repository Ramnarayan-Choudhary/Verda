"""Vector store backed by in-memory cosine similarity (with optional pgvector)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_embedding_model = None


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


async def _embed_texts(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384))
    model = _get_embedding_model()
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(
        None,
        lambda: model.encode(texts, batch_size=min(64, len(texts)), show_progress_bar=False, normalize_embeddings=True),
    )
    return np.asarray(embeddings, dtype=np.float32)


@dataclass
class VectorStoreClient:
    """In-memory vector store with cosine similarity search."""

    namespace: str = "default"
    embedding_dim: int = 384
    _records: list[tuple[str, np.ndarray, dict[str, Any]]] = field(default_factory=list, repr=False)

    async def add_chunks(self, doc_id: str, chunks: list[str]) -> None:
        if not chunks:
            return
        embeddings = await _embed_texts(chunks)
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=False)):
            record_id = f"{doc_id}:{idx}"
            meta = {"id": record_id, "doc_id": doc_id, "position": idx, "text": chunk}
            self._records.append((record_id, embedding, meta))
        logger.info("vector_store.chunks_added", doc_id=doc_id, count=len(chunks))

    async def similarity_search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not self._records:
            return []
        query_emb = await _embed_texts([query])
        scores: list[tuple[float, dict[str, Any]]] = []
        for _, emb, meta in self._records:
            score = float(np.dot(query_emb[0], emb))
            scores.append((score, meta))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [{**meta, "score": score} for score, meta in scores[:k]]
