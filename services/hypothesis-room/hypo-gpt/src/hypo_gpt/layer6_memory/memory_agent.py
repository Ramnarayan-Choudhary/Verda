from __future__ import annotations

from dataclasses import dataclass

from hypo_gpt.layer6_memory.memory_store import InMemoryMemoryStore, MemoryBackend, make_memory_entry
from hypo_gpt.models import MemoryEntry, PanelVerdict


@dataclass
class MemoryAgentFacade:
    backend: MemoryBackend

    def retrieve_context(self, query_text: str, domain_tags: list[str]) -> tuple[str, list[MemoryEntry], list[MemoryEntry]]:
        negatives = self.backend.retrieve_negatives(query_text, domain_tags, top_k=5)
        positives = self.backend.retrieve_positives(query_text, domain_tags, top_k=5)
        context = InMemoryMemoryStore.build_memory_context(negatives, positives)
        return context, negatives, positives

    def store_portfolio(
        self,
        *,
        session_id: str,
        domain_tags: list[str],
        verdicts: list[PanelVerdict],
        hypothesis_text_by_id: dict[str, str],
        strategy_by_id: dict[str, str],
    ) -> list[MemoryEntry]:
        return self.store_panel_outcomes(
            session_id=session_id,
            domain_tags=domain_tags,
            verdicts=verdicts,
            selected_hypo_ids={v.hypo_id for v in verdicts},
            hypothesis_text_by_id=hypothesis_text_by_id,
            strategy_by_id=strategy_by_id,
        )

    def store_panel_outcomes(
        self,
        *,
        session_id: str,
        domain_tags: list[str],
        verdicts: list[PanelVerdict],
        selected_hypo_ids: set[str],
        hypothesis_text_by_id: dict[str, str],
        strategy_by_id: dict[str, str],
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for verdict in verdicts:
            hypothesis_text = hypothesis_text_by_id.get(verdict.hypo_id, "")
            metric_delta = verdict.panel_composite - 0.5

            failure_reason: str | None = None
            if verdict.panel_composite < 0.40:
                failure_reason = "panel composite below 0.40"
            elif verdict.hypo_id not in selected_hypo_ids:
                failure_reason = "not selected into portfolio"

            entry = make_memory_entry(
                session_id=session_id,
                hypothesis_title=hypothesis_text[:140] or verdict.hypo_id,
                hypothesis_text=hypothesis_text,
                strategy=strategy_by_id.get(verdict.hypo_id, "unknown"),
                composite_score=verdict.panel_composite,
                panel_composite=verdict.panel_composite,
                metric_delta=metric_delta,
                failure_reason=failure_reason,
                domain_tags=domain_tags,
            )
            entries.append(entry)
        self.backend.store_entries(entries)
        return entries


memory_agent = MemoryAgentFacade(backend=InMemoryMemoryStore())
