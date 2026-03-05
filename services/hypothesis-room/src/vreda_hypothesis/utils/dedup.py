"""
Embedding-based deduplication — arXiv:2409.04109 Section 3.

Uses Sentence-Transformers (all-MiniLM-L6-v2) to compute cosine similarity
between hypothesis seeds and discard near-duplicates (cosine > threshold).

The model auto-downloads on first use (~80MB).
"""

from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Lazy-loaded singleton
_model = None


def _get_model():
    """Lazy-load the sentence-transformers model on first use."""
    global _model
    if _model is None:
        logger.info("dedup.loading_model", model="all-MiniLM-L6-v2")
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("dedup.model_loaded", dim=_model.get_sentence_embedding_dimension())
    return _model


def compute_embeddings(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Compute 384-dim embeddings for a list of texts.

    Returns:
        np.ndarray of shape (len(texts), 384)
    """
    model = _get_model()
    return model.encode(texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True)


def deduplicate_by_cosine(
    texts: list[str],
    threshold: float = 0.85,
    batch_size: int = 64,
) -> tuple[list[str], list[int]]:
    """Remove near-duplicate texts based on cosine similarity.

    Args:
        texts: List of text strings to deduplicate.
        threshold: Cosine similarity threshold above which texts are considered duplicates.
        batch_size: Batch size for embedding computation.

    Returns:
        Tuple of (unique_texts, kept_indices).
    """
    if len(texts) <= 1:
        return texts, list(range(len(texts)))

    embeddings = compute_embeddings(texts, batch_size=batch_size)

    # Cosine similarity matrix (embeddings are already normalized)
    sim_matrix = embeddings @ embeddings.T

    # Greedy dedup: keep first occurrence, discard later duplicates
    kept: list[int] = []
    discarded: set[int] = set()

    for i in range(len(texts)):
        if i in discarded:
            continue
        kept.append(i)
        # Mark all similar items after i as duplicates
        for j in range(i + 1, len(texts)):
            if j not in discarded and sim_matrix[i, j] > threshold:
                discarded.add(j)

    unique_texts = [texts[i] for i in kept]
    logger.info(
        "dedup.complete",
        original=len(texts),
        unique=len(unique_texts),
        removed=len(texts) - len(unique_texts),
        threshold=threshold,
    )
    return unique_texts, kept


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    b_norm = b / (np.linalg.norm(b) + 1e-10)
    return float(np.dot(a_norm, b_norm))
