from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

import numpy as np

from hypo_gpt.models import MemoryEntry, PanelVerdict
from shared.embedding import embed


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))


@dataclass
class InMemoryMemoryBackend:
    entries: list[MemoryEntry] = field(default_factory=list)

    async def retrieve_negatives(self, query_embedding: np.ndarray, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self.entries:
            if entry.metric_delta is not None and entry.metric_delta >= 0:
                continue
            if entry.panel_composite is not None and entry.panel_composite >= 0.4:
                continue
            if domain_tags and not set(domain_tags).intersection(entry.domain_tags):
                continue
            emb = np.asarray(entry.hypothesis_embedding, dtype=np.float32)
            if emb.size == 0:
                continue
            scored.append((_cosine(query_embedding, emb), entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    async def retrieve_positives(self, query_embedding: np.ndarray, domain_tags: list[str], top_k: int = 5) -> list[MemoryEntry]:
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in self.entries:
            if entry.metric_delta is not None and entry.metric_delta <= 0.05:
                continue
            if entry.panel_composite is not None and entry.panel_composite <= 0.7:
                continue
            if domain_tags and not set(domain_tags).intersection(entry.domain_tags):
                continue
            emb = np.asarray(entry.hypothesis_embedding, dtype=np.float32)
            if emb.size == 0:
                continue
            scored.append((_cosine(query_embedding, emb), entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    async def store_entries(self, entries: list[MemoryEntry]) -> None:
        self.entries.extend(entries)


class MemoryAgent:
    def __init__(self, backend: InMemoryMemoryBackend | None = None) -> None:
        self.backend = backend or InMemoryMemoryBackend()

    async def retrieve_context(self, query: str, domain_tags: list[str]) -> tuple[str, list[MemoryEntry], list[MemoryEntry]]:
        query_embedding = await embed(query)
        negatives = await self.backend.retrieve_negatives(query_embedding, domain_tags)
        positives = await self.backend.retrieve_positives(query_embedding, domain_tags)

        lines: list[str] = []
        if positives:
            lines.append("## Successful directions to build on:")
            for entry in positives:
                score = entry.panel_composite if entry.panel_composite is not None else entry.composite_score
                lines.append(f"+ {entry.hypothesis_title} (score={score:.2f})")
        if negatives:
            lines.append("## Avoid repeating failed directions:")
            for entry in negatives:
                reason = entry.failure_reason or "historically weak panel outcome"
                lines.append(f"- {entry.hypothesis_title} ({reason})")

        return "\n".join(lines), negatives, positives

    async def store_portfolio(
        self,
        *,
        session_id: str,
        domain_tags: list[str],
        verdicts: list[PanelVerdict],
        hypothesis_text_by_id: dict[str, str],
        strategy_by_id: dict[str, str],
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for verdict in verdicts:
            hypothesis_text = hypothesis_text_by_id.get(verdict.hypo_id, "")
            emb = await embed(hypothesis_text)
            entry = MemoryEntry(
                entry_id=f"mem-{uuid.uuid4().hex[:10]}",
                session_id=session_id,
                hypothesis_title=hypothesis_text[:140] or verdict.hypo_id,
                hypothesis_embedding=emb.tolist(),
                strategy=strategy_by_id.get(verdict.hypo_id, "unknown"),
                composite_score=verdict.panel_composite,
                panel_composite=verdict.panel_composite,
                metric_delta=max(0.0, verdict.panel_composite - 0.5),
                failure_reason=None if verdict.panel_composite >= 0.55 else "panel composite below confidence band",
                domain_tags=domain_tags,
            )
            entries.append(entry)

        await self.backend.store_entries(entries)
        return entries


memory_agent = MemoryAgent()
