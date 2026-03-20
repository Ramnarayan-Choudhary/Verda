from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

import numpy as np

from hypo_gpt.models import HypothesisV2, MemoryEntry, PanelVerdict
from shared.dedup import compute_embeddings


@dataclass(frozen=True)
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


def _title_key(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return " ".join(normalized.split())[:90]


def _build_embeddings(hypotheses: dict[str, HypothesisV2]) -> dict[str, np.ndarray]:
    if not hypotheses:
        return {}
    hypo_ids = list(hypotheses.keys())
    texts = [f"{hypotheses[h].title} {hypotheses[h].core_claim} {hypotheses[h].causal_chain.intermediate}" for h in hypo_ids]
    vectors = compute_embeddings(texts)
    return {hypo_id: np.asarray(vectors[idx], dtype=np.float32) for idx, hypo_id in enumerate(hypo_ids)}


def _filter_for_slot(verdicts: list[PanelVerdict], slot: PortfolioSlot) -> list[PanelVerdict]:
    return [
        verdict
        for verdict in verdicts
        if verdict.novelty_mean >= slot.min_novelty
        and verdict.feasibility_mean >= slot.min_feasibility
        and verdict.coherence_mean >= slot.min_coherence
        and verdict.importance_mean >= slot.min_importance
    ]


def _remove_correlated(
    candidates: list[PanelVerdict],
    already_selected: list[PanelVerdict],
    embeddings: dict[str, np.ndarray],
    sim_threshold: float = 0.65,
) -> list[PanelVerdict]:
    if not already_selected:
        return candidates
    output: list[PanelVerdict] = []
    for candidate in candidates:
        c_emb = embeddings.get(candidate.hypo_id)
        if c_emb is None:
            output.append(candidate)
            continue
        correlated = False
        for selected in already_selected:
            s_emb = embeddings.get(selected.hypo_id)
            if s_emb is None:
                continue
            if _cosine(c_emb, s_emb) > sim_threshold:
                correlated = True
                break
        if not correlated:
            output.append(candidate)
    return output


def _overlaps_negative_memory(
    verdict: PanelVerdict,
    negatives: list[MemoryEntry],
    embeddings: dict[str, np.ndarray],
    threshold: float = 0.80,
) -> bool:
    c_emb = embeddings.get(verdict.hypo_id)
    if c_emb is None:
        return False
    for negative in negatives:
        if not negative.hypothesis_embedding:
            continue
        n_emb = np.asarray(negative.hypothesis_embedding, dtype=np.float32)
        if n_emb.size == 0:
            continue
        if _cosine(c_emb, n_emb) > threshold:
            return True
    return False


def _rebalance_strategy_diversity(
    portfolio: list[PanelVerdict],
    all_verdicts: list[PanelVerdict],
    used_ids: set[str],
    hypotheses: dict[str, HypothesisV2],
) -> None:
    while True:
        strategy_count = Counter(hypotheses[v.hypo_id].strategy for v in portfolio if v.hypo_id in hypotheses)
        over = [strategy for strategy, count in strategy_count.items() if count > 2]
        if not over:
            return

        changed = False
        for strategy in over:
            instances = [v for v in portfolio if hypotheses.get(v.hypo_id) and hypotheses[v.hypo_id].strategy == strategy]
            if len(instances) <= 2:
                continue
            worst = min(instances, key=lambda v: v.panel_composite)
            alternatives = [
                v
                for v in all_verdicts
                if v.hypo_id not in used_ids and hypotheses.get(v.hypo_id) and hypotheses[v.hypo_id].strategy != strategy
            ]
            if not alternatives:
                continue
            replacement = max(alternatives, key=lambda v: v.panel_composite)
            portfolio.remove(worst)
            used_ids.discard(worst.hypo_id)
            portfolio.append(replacement)
            used_ids.add(replacement.hypo_id)
            changed = True

        if not changed:
            return


def fill_portfolio(
    verdicts: list[PanelVerdict],
    hypotheses: dict[str, HypothesisV2],
    memory_negatives: list[MemoryEntry],
    *,
    ensure_minimum: int = 3,
) -> list[PanelVerdict]:
    """Fill a 3-5 hypothesis portfolio with slot/risk/diversity constraints."""
    if not verdicts or not hypotheses:
        return []

    verdicts = [v for v in verdicts if v.hypo_id in hypotheses]
    if not verdicts:
        return []

    embeddings = _build_embeddings(hypotheses)

    filtered = [v for v in verdicts if not _overlaps_negative_memory(v, memory_negatives, embeddings)]
    filtered.sort(key=lambda v: v.panel_composite, reverse=True)
    if not filtered:
        filtered = sorted(verdicts, key=lambda v: v.panel_composite, reverse=True)

    portfolio: list[PanelVerdict] = []
    used_ids: set[str] = set()
    used_title_keys: set[str] = set()

    for slot in PORTFOLIO_TEMPLATE:
        candidates = _filter_for_slot(filtered, slot)
        candidates = [c for c in candidates if c.hypo_id not in used_ids]
        candidates = [
            c
            for c in candidates
            if hypotheses.get(c.hypo_id) and _title_key(hypotheses[c.hypo_id].title) not in used_title_keys
        ]
        candidates = _remove_correlated(candidates, portfolio, embeddings)
        if not candidates:
            continue
        best = max(candidates, key=lambda c: c.panel_composite)
        portfolio.append(best)
        used_ids.add(best.hypo_id)
        if hypotheses.get(best.hypo_id):
            used_title_keys.add(_title_key(hypotheses[best.hypo_id].title))

    _rebalance_strategy_diversity(portfolio, filtered, used_ids, hypotheses)

    if len(portfolio) < ensure_minimum:
        for candidate in filtered:
            if candidate.hypo_id in used_ids:
                continue
            if hypotheses.get(candidate.hypo_id) and _title_key(hypotheses[candidate.hypo_id].title) in used_title_keys:
                continue
            candidate_emb = embeddings.get(candidate.hypo_id)
            if candidate_emb is not None:
                too_close = False
                for selected in portfolio:
                    selected_emb = embeddings.get(selected.hypo_id)
                    if selected_emb is not None and _cosine(candidate_emb, selected_emb) > 0.65:
                        too_close = True
                        break
                if too_close:
                    continue
            portfolio.append(candidate)
            used_ids.add(candidate.hypo_id)
            if hypotheses.get(candidate.hypo_id):
                used_title_keys.add(_title_key(hypotheses[candidate.hypo_id].title))
            if len(portfolio) >= ensure_minimum:
                break

    # Last-resort fill: if similarity constraints make slots sparse, prefer non-empty portfolio.
    if len(portfolio) < ensure_minimum:
        for candidate in filtered:
            if candidate.hypo_id in used_ids:
                continue
            if hypotheses.get(candidate.hypo_id) and _title_key(hypotheses[candidate.hypo_id].title) in used_title_keys:
                continue
            portfolio.append(candidate)
            used_ids.add(candidate.hypo_id)
            if hypotheses.get(candidate.hypo_id):
                used_title_keys.add(_title_key(hypotheses[candidate.hypo_id].title))
            if len(portfolio) >= ensure_minimum:
                break

    portfolio.sort(key=lambda v: v.panel_composite, reverse=True)
    return portfolio[:5]
