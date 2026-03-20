"""Embedding-based deduplication using sentence-transformers."""

from __future__ import annotations

import hashlib
import os
import re

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

_model = None


def _stable_bucket(token: str, dim: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    value = int.from_bytes(digest, byteorder="big", signed=False)
    return value % dim


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("dedup.model_loaded", dim=_model.get_sentence_embedding_dimension())
    return _model


def _fallback_embeddings(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    dim = 384
    vectors = np.zeros((len(texts), dim), dtype=np.float32)
    for row, text in enumerate(texts):
        tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if not tokens:
            continue
        # Unigram features.
        for token in tokens:
            bucket = _stable_bucket(f"u:{token}", dim)
            vectors[row, bucket] += 1.0

        # Bigram features improve separation among similarly-worded candidates.
        for idx in range(len(tokens) - 1):
            pair = f"{tokens[idx]}::{tokens[idx + 1]}"
            bucket = _stable_bucket(f"b:{pair}", dim)
            vectors[row, bucket] += 0.8

        # Lightweight char n-grams preserve phrase-level differences.
        compact = re.sub(r"\s+", " ", " ".join(tokens))
        for idx in range(max(0, len(compact) - 4)):
            chunk = compact[idx : idx + 5]
            bucket = _stable_bucket(f"c:{chunk}", dim)
            vectors[row, bucket] += 0.25
        norm = np.linalg.norm(vectors[row])
        if norm > 0:
            vectors[row] = vectors[row] / norm
    return vectors


def compute_embeddings(texts: list[str], batch_size: int = 64) -> np.ndarray:
    if os.environ.get("VREDA_ENABLE_ST_EMBEDDINGS", "0") != "1":
        return _fallback_embeddings(texts)
    try:
        model = _get_model()
        return model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)
    except Exception as exc:  # pragma: no cover - depends on local model availability
        logger.warning("dedup.embedding_fallback", error=str(exc))
        return _fallback_embeddings(texts)


def deduplicate_by_cosine(
    texts: list[str],
    threshold: float = 0.85,
    batch_size: int = 64,
) -> tuple[list[str], list[int]]:
    """Remove near-duplicate texts based on cosine similarity.

    Returns: (unique_texts, kept_indices)
    """
    if len(texts) <= 1:
        return texts, list(range(len(texts)))

    use_threshold = threshold
    if os.environ.get("VREDA_ENABLE_ST_EMBEDDINGS", "0") != "1":
        use_threshold = min(0.97, threshold + 0.22)

    embeddings = compute_embeddings(texts, batch_size=batch_size)
    sim_matrix = embeddings @ embeddings.T

    kept: list[int] = []
    discarded: set[int] = set()
    for i in range(len(texts)):
        if i in discarded:
            continue
        kept.append(i)
        for j in range(i + 1, len(texts)):
            if j not in discarded and sim_matrix[i, j] > use_threshold:
                discarded.add(j)

    unique_texts = [texts[i] for i in kept]
    logger.info("dedup.complete", original=len(texts), unique=len(unique_texts), threshold=use_threshold)
    return unique_texts, kept


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b) + 1e-10)
    return float(np.dot(a_norm, b_norm))
