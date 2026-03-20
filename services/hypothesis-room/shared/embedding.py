"""Shared embedding helpers for hypothesis engine v2.

Supports multiple embedding providers with fallback chain:
1. Gemini (gemini-embedding-001, 768-dim) — cheap and fast
2. sentence-transformers (all-MiniLM-L6-v2, 384-dim) — local, no API needed
3. Rule-based hash fallback — always available
"""

from __future__ import annotations

import asyncio
import os

import numpy as np

import structlog

from shared.dedup import compute_embeddings

logger = structlog.get_logger(__name__)

# Lazy-loaded Gemini client
_gemini_client = None
_GEMINI_MODEL = "gemini-embedding-001"
_GEMINI_DIM = 768


def _get_gemini_embedding_client():
    """Lazy-initialize Gemini client for embeddings."""
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if api_key:
            try:
                from google import genai
                _gemini_client = genai.Client(api_key=api_key)
                logger.info("embedding.gemini_initialized")
            except ImportError:
                logger.debug("embedding.gemini_not_available", reason="google-genai not installed")
            except Exception as exc:
                logger.warning("embedding.gemini_init_failed", error=str(exc)[:200])
    return _gemini_client


async def embed(text: str) -> np.ndarray:
    """Embed a single text with fallback chain: Gemini → sentence-transformers → hash."""
    if not text.strip():
        return np.zeros(_GEMINI_DIM, dtype=np.float32)

    # Try Gemini first
    client = _get_gemini_embedding_client()
    if client is not None:
        try:
            result = await _gemini_embed_texts(client, [text])
            if len(result) > 0:
                return result[0]
        except Exception as exc:
            logger.debug("embedding.gemini_fallback", error=str(exc)[:100])

    # Fallback to sentence-transformers
    loop = asyncio.get_running_loop()
    vectors = await loop.run_in_executor(None, lambda: compute_embeddings([text]))
    if len(vectors) == 0:
        return np.zeros(384, dtype=np.float32)
    return np.asarray(vectors[0], dtype=np.float32)


async def embed_many(texts: list[str]) -> np.ndarray:
    """Embed multiple texts with fallback chain."""
    if not texts:
        return np.zeros((0, _GEMINI_DIM), dtype=np.float32)

    # Try Gemini first (batch)
    client = _get_gemini_embedding_client()
    if client is not None:
        try:
            result = await _gemini_embed_texts(client, texts)
            if len(result) == len(texts):
                return result
        except Exception as exc:
            logger.debug("embedding.gemini_batch_fallback", error=str(exc)[:100])

    # Fallback to sentence-transformers
    loop = asyncio.get_running_loop()
    vectors = await loop.run_in_executor(None, lambda: compute_embeddings(texts))
    return np.asarray(vectors, dtype=np.float32)


async def _gemini_embed_texts(client, texts: list[str]) -> np.ndarray:
    """Embed texts using Gemini API in batches."""
    from google.genai import types

    loop = asyncio.get_running_loop()

    # Gemini supports batches of up to 100 texts
    all_embeddings: list[np.ndarray] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await loop.run_in_executor(
            None,
            lambda b=batch: client.models.embed_content(
                model=_GEMINI_MODEL,
                contents=b,
                config=types.EmbedContentConfig(output_dimensionality=_GEMINI_DIM),
            ),
        )
        for emb in response.embeddings:
            all_embeddings.append(np.asarray(emb.values, dtype=np.float32))

    return np.stack(all_embeddings) if all_embeddings else np.zeros((0, _GEMINI_DIM), dtype=np.float32)
