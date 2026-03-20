from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from hypo_gpt.models import (
    DimensionScores,
    HypothesisV2,
    PanelVerdict,
    PortfolioHypothesis,
    ResearchPortfolio,
    ResourceSummary,
    StructuredHypothesis,
    TribunalVerdict,
)
from shared.dedup import compute_embeddings


@dataclass
class PortfolioSlot:
    slot_id: str
    risk_tier: str
    time_horizon: str
    min_novelty: float
    min_feasibility: float
    min_coherence: float
    min_importance: float


PORTFOLIO_TEMPLATE = [
    PortfolioSlot("A", "safe", "1_month", 0.30, 0.80, 0.65, 0.00),
    PortfolioSlot("B", "safe", "3_months", 0.40, 0.65, 0.70, 0.00),
    PortfolioSlot("C", "balanced", "3_months", 0.65, 0.55, 0.60, 0.30),
    PortfolioSlot("D", "moonshot", "6_months", 0.80, 0.30, 0.55, 0.70),
    PortfolioSlot("E", "moonshot", "12months_plus", 0.75, 0.25, 0.50, 0.60),
]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))


class PortfolioConstructor:
    def _filter_for_slot(self, verdicts: list[PanelVerdict], slot: PortfolioSlot) -> list[PanelVerdict]:
        return [
            verdict
            for verdict in verdicts
            if verdict.novelty_mean >= slot.min_novelty
            and verdict.feasibility_mean >= slot.min_feasibility
            and verdict.coherence_mean >= slot.min_coherence
            and verdict.importance_mean >= slot.min_importance
        ]

    def _remove_correlated(
        self,
        candidates: list[PanelVerdict],
        already_selected: list[PanelVerdict],
        embeddings: dict[str, np.ndarray],
        sim_threshold: float = 0.65,
    ) -> list[PanelVerdict]:
        if not already_selected:
            return candidates
        result: list[PanelVerdict] = []
        for candidate in candidates:
            c_emb = embeddings.get(candidate.hypo_id)
            if c_emb is None:
                result.append(candidate)
                continue
            too_similar = False
            for selected in already_selected:
                s_emb = embeddings.get(selected.hypo_id)
                if s_emb is None:
                    continue
                if _cosine(c_emb, s_emb) > sim_threshold:
                    too_similar = True
                    break
            if not too_similar:
                result.append(candidate)
        return result

    def _overlaps_negative_memory(
        self,
        verdict: PanelVerdict,
        memory_negatives: list,
        embeddings: dict[str, np.ndarray],
        threshold: float = 0.80,
    ) -> bool:
        c_emb = embeddings.get(verdict.hypo_id)
        if c_emb is None:
            return False
        for item in memory_negatives:
            emb = np.asarray(getattr(item, "hypothesis_embedding", []), dtype=np.float32)
            if emb.size == 0:
                continue
            if _cosine(c_emb, emb) > threshold:
                return True
        return False

    def _rebalance_strategy_diversity(
        self,
        portfolio: list[PanelVerdict],
        all_verdicts: list[PanelVerdict],
        used_ids: set[str],
        strategies: dict[str, str],
    ) -> None:
        strategy_counts = Counter(strategies.get(item.hypo_id, "unknown") for item in portfolio)
        for strategy, count in strategy_counts.items():
            if count <= 2:
                continue
            worst = min(
                [item for item in portfolio if strategies.get(item.hypo_id, "unknown") == strategy],
                key=lambda item: item.panel_composite,
            )
            alternatives = [
                item
                for item in all_verdicts
                if item.hypo_id not in used_ids and strategies.get(item.hypo_id, "unknown") != strategy
            ]
            if not alternatives:
                continue
            replacement = max(alternatives, key=lambda item: item.panel_composite)
            portfolio.remove(worst)
            portfolio.append(replacement)
            used_ids.add(replacement.hypo_id)

    def fill_v2(
        self,
        verdicts: list[PanelVerdict],
        hypotheses: dict[str, HypothesisV2],
        memory_negatives: list,
    ) -> list[PanelVerdict]:
        if not verdicts:
            return []

        texts = [f"{hypotheses[item.hypo_id].title} {hypotheses[item.hypo_id].core_claim}" for item in verdicts if item.hypo_id in hypotheses]
        vectors = compute_embeddings(texts)
        embeddings: dict[str, np.ndarray] = {}
        vector_index = 0
        for verdict in verdicts:
            if verdict.hypo_id not in hypotheses:
                continue
            embeddings[verdict.hypo_id] = np.asarray(vectors[vector_index], dtype=np.float32)
            vector_index += 1

        filtered = [item for item in verdicts if not self._overlaps_negative_memory(item, memory_negatives, embeddings)]
        filtered.sort(key=lambda item: item.panel_composite, reverse=True)

        portfolio: list[PanelVerdict] = []
        used_ids: set[str] = set()
        for slot in PORTFOLIO_TEMPLATE:
            candidates = self._filter_for_slot(filtered, slot)
            candidates = [item for item in candidates if item.hypo_id not in used_ids]
            candidates = self._remove_correlated(candidates, portfolio, embeddings)
            if not candidates:
                continue
            best = max(candidates, key=lambda item: item.panel_composite)
            portfolio.append(best)
            used_ids.add(best.hypo_id)

        strategies = {hypothesis.hypo_id: hypothesis.strategy for hypothesis in hypotheses.values()}
        self._rebalance_strategy_diversity(portfolio, filtered, used_ids, strategies)

        if len(portfolio) < 3:
            for candidate in filtered:
                if candidate.hypo_id in used_ids:
                    continue
                portfolio.append(candidate)
                used_ids.add(candidate.hypo_id)
                if len(portfolio) >= 3:
                    break

        return portfolio[:5]

    def build(
        self,
        ranked: list[StructuredHypothesis],
        scores: dict[str, DimensionScores],
        verdicts: dict[str, TribunalVerdict],
    ) -> ResearchPortfolio:
        if not ranked:
            return ResearchPortfolio(portfolio_rationale="No ranked hypotheses available.")

        diverse_ranked: list[StructuredHypothesis] = []
        seen_strategy: set[str] = set()
        for hypothesis in ranked:
            if hypothesis.generation_strategy in seen_strategy:
                continue
            diverse_ranked.append(hypothesis)
            seen_strategy.add(hypothesis.generation_strategy)
        for hypothesis in ranked:
            if hypothesis.id not in {item.id for item in diverse_ranked}:
                diverse_ranked.append(hypothesis)

        safe: list[StructuredHypothesis] = []
        medium: list[StructuredHypothesis] = []
        moonshot: list[StructuredHypothesis] = []

        for hypothesis in diverse_ranked:
            score = scores.get(hypothesis.id)
            if not score:
                continue
            if score.feasibility >= 7.0 and len(safe) < 2:
                safe.append(hypothesis)
            elif score.scientific_impact >= 7.0 and len(medium) < 2:
                medium.append(hypothesis)
            elif score.creativity >= 7.5 and len(moonshot) < 1:
                moonshot.append(hypothesis)

        selected = safe + medium + moonshot
        if len(selected) < 4:
            for hypothesis in diverse_ranked:
                if hypothesis.id not in {item.id for item in selected}:
                    selected.append(hypothesis)
                if len(selected) >= 5:
                    break

        portfolio_hypotheses: list[PortfolioHypothesis] = []
        for hypothesis in selected[:5]:
            if hypothesis in safe:
                slot = "safe"
            elif hypothesis in medium:
                slot = "medium"
            elif hypothesis in moonshot:
                slot = "moonshot"
            else:
                slot = "medium"

            score = scores.get(hypothesis.id) or DimensionScores()
            verdict = verdicts.get(hypothesis.id)
            if verdict is None:
                continue

            portfolio_hypotheses.append(
                PortfolioHypothesis(
                    hypothesis=hypothesis,
                    portfolio_slot=slot,
                    dimension_scores=score,
                    tribunal_verdict=verdict,
                    portfolio_position_rationale=f"Placed in {slot} slot based on impact-feasibility profile.",
                    suggested_timeline=hypothesis.minimum_viable_test.estimated_timeline,
                    dependencies=[],
                    success_definition=hypothesis.minimum_viable_test.success_threshold,
                    failure_learning=hypothesis.expected_outcome_if_false,
                )
            )

        execution_order = [item.hypothesis.id for item in sorted(portfolio_hypotheses, key=lambda item: item.suggested_timeline)]
        compute_hours = 12.0 * len(portfolio_hypotheses)

        return ResearchPortfolio(
            hypotheses=portfolio_hypotheses,
            portfolio_rationale="Balanced across feasibility, impact, and creative upside.",
            suggested_execution_order=execution_order,
            resource_summary=ResourceSummary(
                estimated_compute_hours=compute_hours,
                timeline_summary="Execute safe hypotheses first, then medium, then moonshot validation.",
                data_dependencies=[item.hypothesis.minimum_viable_test.dataset for item in portfolio_hypotheses],
            ),
        )
