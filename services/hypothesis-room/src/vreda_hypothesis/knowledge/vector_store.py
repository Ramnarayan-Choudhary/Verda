"""
Vector store helper backed by Supabase pgvector (via `vecs`) with an
in-memory fallback for local development and testing.

Critical fix: vecs.create_client() requires a Postgres connection string
(not a Supabase REST URL). Now uses settings.supabase.postgres_url.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from vreda_hypothesis.config import settings

logger = structlog.get_logger(__name__)


def _get_embedding_model():
    """Lazy-load SentenceTransformer once per process."""
    if not hasattr(_get_embedding_model, "_model"):
        from sentence_transformers import SentenceTransformer

        _get_embedding_model._model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info(
            "vector_store.model_loaded",
            dimension=_get_embedding_model._model.get_sentence_embedding_dimension(),
        )
    return _get_embedding_model._model


async def _embed_texts(texts: list[str]) -> np.ndarray:
    """Compute normalized embeddings asynchronously."""
    if not texts:
        return np.zeros((0, 384))

    model = _get_embedding_model()
    loop = asyncio.get_running_loop()
    embeddings = await loop.run_in_executor(
        None,
        lambda: model.encode(
            texts,
            batch_size=min(64, len(texts)),
            show_progress_bar=False,
            normalize_embeddings=True,
        ),
    )
    return np.asarray(embeddings, dtype=np.float32)


class InMemoryVectorStore:
    """Simple cosine-similarity store for fallback usage."""

    def __init__(self) -> None:
        self._records: list[tuple[str, np.ndarray, dict[str, Any]]] = []

    async def upsert(self, texts: list[str], metadata: list[dict[str, Any]]) -> None:
        embeddings = await _embed_texts(texts)
        for text, embedding, meta in zip(texts, embeddings, metadata, strict=False):
            record_id = meta.get("id") or uuid.uuid4().hex
            enriched_meta = {"text": text, **meta}
            self._records.append((record_id, embedding, enriched_meta))

    async def similarity_search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        if not self._records:
            return []
        query_emb = await _embed_texts([query])
        scores: list[tuple[float, dict[str, Any]]] = []
        for _, emb, meta in self._records:
            score = float(np.dot(query_emb[0], emb))
            scores.append((score, meta))
        scores.sort(key=lambda item: item[0], reverse=True)
        return [
            {**meta, "score": score}
            for score, meta in scores[:k]
        ]


@dataclass
class VectorStoreClient:
    """Abstraction over Supabase pgvector (via vecs) with fallback."""

    namespace: str = "vreda_hypothesis"

    def __post_init__(self) -> None:
        # vecs requires a Postgres connection string, NOT a Supabase REST URL
        postgres_url = settings.supabase.postgres_url
        self._backend: str

        if postgres_url:
            try:
                import vecs

                self._client = vecs.create_client(postgres_url)
                self._collection = self._client.get_or_create_collection(
                    name=self.namespace,
                    dimension=384,
                    distance="cosine",
                )
                self._backend = "supabase"
                logger.info("vector_store.backend_ready", backend="supabase", namespace=self.namespace)
                return
            except Exception as exc:
                logger.warning("vector_store.supabase_failed_falling_back", error=str(exc))

        self._backend = "memory"
        self._collection = InMemoryVectorStore()
        logger.info("vector_store.backend_ready", backend="memory", namespace=self.namespace)

    async def add_chunks(self, doc_id: str, chunks: list[str]) -> None:
        """Embed and upsert paper chunks to the store."""
        if not chunks:
            return
        metadata = [
            {"id": f"{doc_id}:{idx}", "doc_id": doc_id, "position": idx}
            for idx in range(len(chunks))
        ]
        if self._backend == "supabase":
            embeddings = await _embed_texts(chunks)
            records = []
            for meta, vector, text in zip(metadata, embeddings, chunks, strict=False):
                records.append((meta["id"], vector.tolist(), {"text": text, **meta}))
            await asyncio.get_running_loop().run_in_executor(None, self._collection.upsert, records)
        else:
            await self._collection.upsert(chunks, metadata)

    async def similarity_search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """Return the top-k most similar chunks."""
        if self._backend == "supabase":
            query_vector = (await _embed_texts([query]))[0].tolist()

            def _query():
                return self._collection.query(
                    data=query_vector,
                    limit=k,
                    include_value=True,
                    include_metadata=True,
                )

            raw_results = await asyncio.get_running_loop().run_in_executor(None, _query)
            formatted = []
            for score, metadata, _ in raw_results:
                formatted.append({"score": score, **metadata})
            return formatted

        return await self._collection.similarity_search(query, k)
