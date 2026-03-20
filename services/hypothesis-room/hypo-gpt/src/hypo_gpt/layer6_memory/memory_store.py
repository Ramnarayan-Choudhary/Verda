from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from hypo_gpt.models import MemoryEntry
from shared.dedup import compute_embeddings, cosine_similarity


class MemoryBackend(Protocol):
    def retrieve_negatives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]: ...

    def retrieve_positives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]: ...

    def store_entries(self, entries: list[MemoryEntry]) -> None: ...


@dataclass
class InMemoryMemoryStore:
    """Layer6 in-memory store with negative blocking + positive building."""

    entries: list[MemoryEntry] = field(default_factory=list)

    def _similar(
        self,
        query_text: str,
        candidates: list[MemoryEntry],
        domain_tags: list[str],
        top_k: int,
        sim_threshold: float = 0.30,
    ) -> list[MemoryEntry]:
        if not candidates:
            return []
        query_emb = compute_embeddings([query_text])[0]

        scored: list[tuple[float, MemoryEntry]] = []
        for entry in candidates:
            # Strict domain overlap when query tags are provided.
            if domain_tags and not set(domain_tags).intersection(entry.domain_tags):
                continue
            if not entry.hypothesis_embedding:
                continue
            emb = np.asarray(entry.hypothesis_embedding, dtype=np.float32)
            if emb.size == 0:
                continue
            score = cosine_similarity(query_emb, emb)
            if score >= sim_threshold:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def retrieve_negatives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        candidates = [
            entry
            for entry in self.entries
            if (entry.metric_delta is not None and entry.metric_delta < 0) or (entry.panel_composite is not None and entry.panel_composite < 0.4)
        ]
        return self._similar(query_text, candidates, domain_tags, top_k, sim_threshold=0.30)

    def retrieve_positives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        candidates = [
            entry
            for entry in self.entries
            if (entry.metric_delta is not None and entry.metric_delta > 0.05)
            or (entry.panel_composite is not None and entry.panel_composite > 0.7)
        ]
        return self._similar(query_text, candidates, domain_tags, top_k, sim_threshold=0.30)

    def retrieve_with_domain_filter(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        query_emb = compute_embeddings([query_text])[0]
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self.entries:
            if domain_tags and not set(domain_tags).intersection(entry.domain_tags):
                continue
            if not entry.hypothesis_embedding:
                continue
            emb = np.asarray(entry.hypothesis_embedding, dtype=np.float32)
            if emb.size == 0:
                continue
            scored.append((cosine_similarity(query_emb, emb), entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def store_entries(self, entries: list[MemoryEntry]) -> None:
        self.entries.extend(entries)

    @staticmethod
    def build_memory_context(negatives: list[MemoryEntry], positives: list[MemoryEntry]) -> str:
        lines: list[str] = []
        if positives:
            lines.append("## Successful directions to build on:")
            for entry in positives:
                score = entry.panel_composite if entry.panel_composite is not None else entry.composite_score
                lines.append(f"+ {entry.hypothesis_title} (score={score:.2f})")
        if negatives:
            lines.append("## NEVER re-propose these failed directions:")
            for entry in negatives:
                lines.append(f"- {entry.hypothesis_title}")
                if entry.failure_reason:
                    lines.append(f"  Reason: {entry.failure_reason}")
        return "\n".join(lines)


class PgVectorMemoryStore:
    """Stub for pgvector-backed storage; interface compatible with MemoryBackend."""

    def retrieve_negatives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        return []

    def retrieve_positives(self, query_text: str, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        return []

    def store_entries(self, entries: list[MemoryEntry]) -> None:
        _ = entries



def make_memory_entry(
    *,
    session_id: str,
    hypothesis_title: str,
    hypothesis_text: str,
    strategy: str,
    composite_score: float,
    panel_composite: float,
    metric_delta: float | None,
    failure_reason: str | None,
    domain_tags: list[str],
) -> MemoryEntry:
    embedding = compute_embeddings([hypothesis_text])[0].tolist()
    normalized_tags = sorted({tag.strip().lower() for tag in domain_tags if tag and tag.strip()})
    return MemoryEntry(
        session_id=session_id,
        hypothesis_title=hypothesis_title,
        hypothesis_embedding=embedding,
        strategy=strategy,
        composite_score=composite_score,
        panel_composite=panel_composite,
        metric_delta=metric_delta,
        failure_reason=failure_reason,
        domain_tags=normalized_tags,
    )
