"""Cross-session hypothesis memory store.

In-memory implementation with optional pgvector persistence.
Stores hypothesis outcomes for negative blocking + positive building.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import structlog

from shared.dedup import compute_embeddings, cosine_similarity

logger = structlog.get_logger(__name__)


@dataclass
class MemoryRecord:
    """Internal storage record for a hypothesis outcome."""
    entry_id: str
    session_id: str
    hypothesis_title: str
    embedding: np.ndarray
    strategy: str
    composite_score: float
    panel_composite: float
    metric_delta: float | None
    failure_reason: str | None
    domain_tags: list[str]
    created_at: str


@dataclass
class HypothesisMemoryStore:
    """In-memory cross-session hypothesis memory with embedding-based retrieval.

    Two memory paths:
    1. Negative blocking: Retrieve failed hypotheses to prevent re-proposal
    2. Positive building: Retrieve successful hypotheses to build upon
    """

    _records: list[MemoryRecord] = field(default_factory=list)

    def store_outcome(
        self,
        entry_id: str,
        session_id: str,
        hypothesis_title: str,
        hypothesis_text: str,
        strategy: str,
        composite_score: float = 0.0,
        panel_composite: float = 0.0,
        metric_delta: float | None = None,
        failure_reason: str | None = None,
        domain_tags: list[str] | None = None,
    ) -> None:
        """Store a hypothesis outcome for future retrieval."""
        embedding = compute_embeddings([hypothesis_text])[0]
        record = MemoryRecord(
            entry_id=entry_id,
            session_id=session_id,
            hypothesis_title=hypothesis_title,
            embedding=embedding,
            strategy=strategy,
            composite_score=composite_score,
            panel_composite=panel_composite,
            metric_delta=metric_delta,
            failure_reason=failure_reason,
            domain_tags=domain_tags or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records.append(record)
        logger.info(
            "memory.stored",
            entry_id=entry_id,
            title=hypothesis_title[:50],
            panel_composite=panel_composite,
        )

    def retrieve_negatives(
        self,
        query_text: str,
        domain_tags: list[str] | None = None,
        top_k: int = 5,
        sim_threshold: float = 0.3,
    ) -> list[MemoryRecord]:
        """Retrieve failed hypotheses similar to the query for negative blocking."""
        negatives = [
            r for r in self._records
            if (r.metric_delta is not None and r.metric_delta < 0)
            or r.panel_composite < 0.4
        ]
        return self._retrieve_similar(negatives, query_text, domain_tags, top_k, sim_threshold)

    def retrieve_positives(
        self,
        query_text: str,
        domain_tags: list[str] | None = None,
        top_k: int = 5,
        sim_threshold: float = 0.3,
    ) -> list[MemoryRecord]:
        """Retrieve successful hypotheses for positive building."""
        positives = [
            r for r in self._records
            if (r.metric_delta is not None and r.metric_delta > 0.05)
            or r.panel_composite > 0.7
        ]
        return self._retrieve_similar(positives, query_text, domain_tags, top_k, sim_threshold)

    def should_block(self, hypothesis_text: str, threshold: float = 0.80) -> bool:
        """Check if a hypothesis is too similar to a known failure."""
        if not self._records:
            return False
        query_emb = compute_embeddings([hypothesis_text])[0]
        for r in self._records:
            is_negative = (r.metric_delta is not None and r.metric_delta < 0) or r.panel_composite < 0.4
            if is_negative:
                sim = cosine_similarity(query_emb, r.embedding)
                if sim > threshold:
                    logger.info(
                        "memory.blocked",
                        similar_to=r.hypothesis_title[:50],
                        similarity=round(sim, 3),
                    )
                    return True
        return False

    def _retrieve_similar(
        self,
        candidates: list[MemoryRecord],
        query_text: str,
        domain_tags: list[str] | None,
        top_k: int,
        sim_threshold: float,
    ) -> list[MemoryRecord]:
        """Retrieve similar records with optional domain tag filtering."""
        if not candidates:
            return []

        # Domain tag filtering
        if domain_tags:
            tag_set = set(domain_tags)
            candidates = [
                r for r in candidates
                if not r.domain_tags or tag_set.intersection(r.domain_tags)
            ]

        if not candidates:
            return []

        query_emb = compute_embeddings([query_text])[0]
        scored: list[tuple[float, MemoryRecord]] = []
        for r in candidates:
            sim = cosine_similarity(query_emb, r.embedding)
            if sim >= sim_threshold:
                scored.append((sim, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def build_memory_context(
        self,
        query_text: str,
        domain_tags: list[str] | None = None,
    ) -> dict[str, str]:
        """Build blocking/building text for injection into generation prompts."""
        negatives = self.retrieve_negatives(query_text, domain_tags)
        positives = self.retrieve_positives(query_text, domain_tags)

        blocking_text = ""
        if negatives:
            lines = [
                f"- {r.hypothesis_title} (failed: {r.failure_reason or 'low score'})"
                for r in negatives
            ]
            blocking_text = (
                "NEVER re-propose these failed directions:\n" + "\n".join(lines)
            )

        building_text = ""
        if positives:
            lines = [
                f"- {r.hypothesis_title} (score: {r.panel_composite:.1f})"
                for r in positives
            ]
            building_text = (
                "Successful directions to build on:\n" + "\n".join(lines)
            )

        return {
            "blocking_text": blocking_text,
            "building_text": building_text,
        }

    @property
    def size(self) -> int:
        return len(self._records)
