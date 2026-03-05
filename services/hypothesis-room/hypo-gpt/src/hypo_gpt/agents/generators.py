from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
import re

import structlog

from hypo_gpt.llm import LLMProvider
from hypo_gpt.models import MinimalTest, ResearchLandscape, ResearchSpaceMap, StructuredHypothesis

logger = structlog.get_logger(__name__)

STRATEGIES = [
    "assumption_challenger",
    "domain_bridge",
    "contradiction_resolver",
    "constraint_relaxer",
    "mechanism_extractor",
    "synthesis_catalyst",
    "falsification_designer",
]


_STRATEGY_GUIDANCE: dict[str, str] = {
    "assumption_challenger": "Target one dominant assumption and make it experimentally falsifiable.",
    "domain_bridge": "Transfer a mechanism from an adjacent domain and spell out the mapping.",
    "contradiction_resolver": "Unify two conflicting claims by introducing a missing variable.",
    "constraint_relaxer": "Relax one design/training constraint and predict a regime change.",
    "mechanism_extractor": "Isolate the hidden mechanism that explains observed gains.",
    "synthesis_catalyst": "Fuse complementary methods into one coherent intervention.",
    "falsification_designer": "Design a decisive experiment that can kill the dominant claim.",
}


def _clean_text(value: Any, fallback: str, max_chars: int = 300) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return fallback
    return cleaned[:max_chars]


def _gap_focus_phrase(statement: str, max_words: int = 5) -> str:
    words = re.findall(r"[A-Za-z0-9\-]+", statement)
    if not words:
        return "core gap"
    return " ".join(words[:max_words]).lower()


def _default_test_settings(domain: str) -> tuple[str, str, str]:
    if domain == "nlp":
        return ("MMLU + GSM8K transfer split", "instruction-tuned transformer baseline", "accuracy + macro-F1")
    if domain == "cv":
        return ("ImageNet-C + ImageNet-A", "ViT baseline under matched FLOPs", "top-1 accuracy + corruption error")
    if domain == "rl":
        return ("Atari-57 + ProcGen", "PPO baseline with equal environment steps", "human-normalized return")
    if domain == "biology":
        return ("OpenBioMed benchmark suite", "published SOTA baseline", "AUROC + calibration error")
    return ("OOD robustness benchmark", "strong baseline under equal compute", "primary task metric + robustness gap")


def _estimate_compute(domain: str, ordinal: int, impact: str) -> tuple[str, str]:
    if domain in {"nlp", "cv"}:
        compute = ["4xA100 for 18h", "8xA100 for 24h", "8xA100 for 36h"][ordinal % 3]
    elif domain == "rl":
        compute = ["8xA100 for 24h", "8xA100 for 36h", "16xA100 for 24h"][ordinal % 3]
    else:
        compute = ["4xA100 for 12h", "4xA100 for 18h", "8xA100 for 20h"][ordinal % 3]
    timeline = "2-3 weeks" if impact in {"high", "paradigm_shift"} else "1-2 weeks"
    return compute, timeline


def _prediction(metric: str, strategy: str, ordinal: int) -> str:
    base_gain = 4 + (ordinal % 4)
    robust_gain = 8 + ((ordinal + len(strategy)) % 5) * 2
    cal_gain = 10 + ((ordinal * 3) % 7)
    return (
        f"{metric} improves by >= {base_gain}% relative, "
        f"robustness stress score by >= {robust_gain}%, "
        f"and calibration error drops by >= {cal_gain}%."
    )


def _strategy_gap_pool(strategy: str, research_space_map: ResearchSpaceMap):
    if strategy == "assumption_challenger":
        return research_space_map.assumption_gaps or research_space_map.knowledge_gaps
    if strategy == "domain_bridge":
        return research_space_map.method_gaps or research_space_map.theoretical_gaps
    if strategy == "contradiction_resolver":
        return research_space_map.knowledge_gaps or research_space_map.assumption_gaps
    if strategy == "constraint_relaxer":
        return research_space_map.method_gaps or research_space_map.assumption_gaps
    if strategy == "mechanism_extractor":
        return research_space_map.theoretical_gaps or research_space_map.knowledge_gaps
    if strategy == "synthesis_catalyst":
        return research_space_map.method_gaps + research_space_map.knowledge_gaps
    return research_space_map.theoretical_gaps + research_space_map.assumption_gaps


def _strategy_type(strategy: str) -> str:
    mapping = {
        "assumption_challenger": "failure_mode_analysis",
        "domain_bridge": "cross_domain_transfer",
        "contradiction_resolver": "theoretical_extension",
        "constraint_relaxer": "constraint_relaxation",
        "mechanism_extractor": "architecture_ablation",
        "synthesis_catalyst": "combination",
        "falsification_designer": "failure_mode_analysis",
    }
    return mapping.get(strategy, "combination")


def _canonical_signature(hypothesis: StructuredHypothesis) -> str:
    return " | ".join(
        [
            hypothesis.generation_strategy,
            hypothesis.source_gap_id,
            hypothesis.intervention.lower()[:140],
            hypothesis.prediction.lower()[:120],
        ]
    )


class StrategyGenerator:
    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm or LLMProvider()

    async def generate(
        self,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        per_strategy: int = 3,
    ) -> dict[str, list[StructuredHypothesis]]:
        heuristic = self._generate_heuristic(landscape, research_space_map, per_strategy=per_strategy)
        if not self.llm.is_configured:
            return heuristic

        generated = await self._generate_with_llm(landscape, research_space_map, per_strategy=per_strategy)
        if not generated:
            return heuristic

        # Merge with heuristic to backfill missing strategies and guarantee count.
        merged: dict[str, list[StructuredHypothesis]] = {k: list(v) for k, v in generated.items()}
        seen = {h.id for items in merged.values() for h in items}
        for strategy in STRATEGIES:
            merged.setdefault(strategy, [])
            for candidate in heuristic.get(strategy, []):
                if len(merged[strategy]) >= per_strategy:
                    break
                if candidate.id in seen:
                    continue
                merged[strategy].append(candidate)
                seen.add(candidate.id)
        return merged

    async def _generate_with_llm(
        self,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        per_strategy: int,
    ) -> dict[str, list[StructuredHypothesis]]:
        all_gaps = (
            research_space_map.assumption_gaps
            + research_space_map.method_gaps
            + research_space_map.knowledge_gaps
            + research_space_map.theoretical_gaps
        )
        if not all_gaps:
            return {}

        gap_payload = [
            {
                "gap_id": g.gap_id,
                "gap_type": g.gap_type,
                "statement": g.statement,
                "why_it_matters": g.why_it_matters,
                "expected_impact": g.expected_impact,
                "nearest_prior_work": g.nearest_prior_work,
            }
            for g in all_gaps[:18]
        ]

        system_prompt = (
            "You are a principal research scientist generating state-of-the-art, novel, testable hypotheses. "
            "Return only valid JSON. Avoid generic claims. Use concrete interventions, named benchmarks, "
            "numeric thresholds, and a mechanism that is falsifiable."
        )
        user_prompt = (
            "Generate hypotheses as JSON object with key `hypotheses`.\n"
            "Each item MUST include keys: generation_strategy, source_gap_id, title, condition, intervention, "
            "prediction, mechanism, falsification_criterion, minimum_viable_test, closest_existing_work, "
            "novelty_claim, expected_outcome_if_true, expected_outcome_if_false, theoretical_basis.\n"
            "minimum_viable_test must include dataset, baseline, primary_metric, success_threshold, estimated_compute, estimated_timeline.\n"
            f"Create exactly {per_strategy} hypotheses per strategy for strategies: {', '.join(STRATEGIES)}.\n"
            "Use short unique titles (<=14 words). Each strategy must be materially different.\n\n"
            f"Research Intent:\n{landscape.research_intent}\n\n"
            f"Landscape JSON:\n{json.dumps(landscape.model_dump(mode='json'), ensure_ascii=True)[:5000]}\n\n"
            f"Gaps JSON:\n{json.dumps(gap_payload, ensure_ascii=True)}"
        )
        payload = await self.llm.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.35,
            max_output_tokens=3200,
        )
        if not payload:
            return {}

        items = payload.get("hypotheses")
        if not isinstance(items, list):
            logger.warning("hypo_gpt.layer2.llm_invalid_shape")
            return {}

        gap_by_id = {g.gap_id: g for g in all_gaps}
        result: dict[str, list[StructuredHypothesis]] = defaultdict(list)
        signatures: set[str] = set()

        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            strategy = _clean_text(raw.get("generation_strategy"), "", 80).lower()
            if strategy not in STRATEGIES:
                continue
            hypothesis = self._from_raw(raw, strategy, landscape, research_space_map, gap_by_id, idx)
            if not hypothesis:
                continue
            signature = _canonical_signature(hypothesis)
            if signature in signatures:
                continue
            if len(result[strategy]) >= per_strategy:
                continue
            signatures.add(signature)
            result[strategy].append(hypothesis)

        return dict(result)

    def _from_raw(
        self,
        raw: dict[str, Any],
        strategy: str,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        gap_by_id: dict[str, Any],
        ordinal: int,
    ) -> StructuredHypothesis | None:
        default_pool = _strategy_gap_pool(strategy, research_space_map)
        if not default_pool:
            return None
        fallback_gap = default_pool[ordinal % len(default_pool)]

        source_gap_id = _clean_text(raw.get("source_gap_id"), fallback_gap.gap_id, 40)
        gap = gap_by_id.get(source_gap_id, fallback_gap)
        dataset, baseline, metric = _default_test_settings(landscape.intent_domain)
        compute, timeline = _estimate_compute(landscape.intent_domain, ordinal, gap.expected_impact)

        mvt_raw = raw.get("minimum_viable_test")
        mvt = mvt_raw if isinstance(mvt_raw, dict) else {}
        try:
            return StructuredHypothesis(
                generation_strategy=strategy,
                source_gap_id=gap.gap_id,
                title=_clean_text(
                    raw.get("title"),
                    f"{strategy.replace('_', ' ').title()}: {_gap_focus_phrase(gap.statement).title()}",
                    110,
                ),
                condition=_clean_text(raw.get("condition"), f"Under conditions where {gap.statement.lower()}", 220),
                intervention=_clean_text(raw.get("intervention"), f"Intervene on {gap.statement.lower()} with explicit mechanism controls.", 360),
                prediction=_clean_text(raw.get("prediction"), _prediction(metric, strategy, ordinal), 260),
                mechanism=_clean_text(raw.get("mechanism"), f"The intervention addresses {gap.statement.lower()} by introducing a causal control pathway.", 420),
                falsification_criterion=_clean_text(
                    raw.get("falsification_criterion"),
                    "Reject if improvements fail under matched compute and out-of-distribution stress tests.",
                    260,
                ),
                minimum_viable_test=MinimalTest(
                    dataset=_clean_text(mvt.get("dataset"), dataset, 120),
                    baseline=_clean_text(mvt.get("baseline"), baseline, 160),
                    primary_metric=_clean_text(mvt.get("primary_metric"), metric, 90),
                    success_threshold=_clean_text(mvt.get("success_threshold"), ">=4% relative gain and better robustness", 110),
                    estimated_compute=_clean_text(mvt.get("estimated_compute"), compute, 90),
                    estimated_timeline=_clean_text(mvt.get("estimated_timeline"), timeline, 60),
                ),
                closest_existing_work=_clean_text(raw.get("closest_existing_work"), gap.nearest_prior_work or "current SOTA baseline", 200),
                novelty_claim=_clean_text(raw.get("novelty_claim"), f"Moves beyond prior work by targeting {gap.gap_type} gap {gap.gap_id}.", 240),
                expected_outcome_if_true=_clean_text(raw.get("expected_outcome_if_true"), "Higher robustness and more stable performance under distribution shift.", 220),
                expected_outcome_if_false=_clean_text(raw.get("expected_outcome_if_false"), "Indicates dominant assumptions are still valid and mechanism is insufficient.", 220),
                theoretical_basis=_clean_text(raw.get("theoretical_basis"), "causal mechanism design + robust optimization", 160),
            )
        except Exception:  # noqa: BLE001
            return None

    def _generate_heuristic(
        self,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        per_strategy: int = 3,
    ) -> dict[str, list[StructuredHypothesis]]:
        gap_order = (
            research_space_map.assumption_gaps
            + research_space_map.method_gaps
            + research_space_map.knowledge_gaps
            + research_space_map.theoretical_gaps
        )
        if not gap_order:
            return {strategy: [] for strategy in STRATEGIES}

        dataset, baseline, primary_metric = _default_test_settings(landscape.intent_domain)
        strategy_output: dict[str, list[StructuredHypothesis]] = defaultdict(list)
        signatures: set[str] = set()

        for strategy_index, strategy in enumerate(STRATEGIES):
            pool = _strategy_gap_pool(strategy, research_space_map) or gap_order
            for i in range(per_strategy):
                gap = pool[(strategy_index + i) % len(pool)]
                ordinal = strategy_index * per_strategy + i
                compute, timeline = _estimate_compute(landscape.intent_domain, ordinal, gap.expected_impact)
                focus = _gap_focus_phrase(gap.statement).title()
                title = (
                    f"{strategy.replace('_', ' ').title()}: {focus}"
                )
                condition = (
                    f"Under deployment-like shift where {gap.statement.lower()}, "
                    f"especially around {gap.why_it_matters.lower()}"
                )
                intervention = (
                    f"{_STRATEGY_GUIDANCE[strategy]} Build intervention around gap {gap.gap_id}: "
                    f"{gap.statement}. Use explicit controls against {gap.nearest_prior_work or 'standard baseline behavior'}."
                )
                prediction = _prediction(primary_metric, strategy, ordinal)
                mechanism = (
                    f"Mechanistically, the intervention targets the failure mode behind '{gap.statement}' "
                    f"and introduces a measurable causal pathway that can be isolated via ablation and stress tests."
                )
                hypothesis = StructuredHypothesis(
                    generation_strategy=strategy,
                    source_gap_id=gap.gap_id,
                    title=title,
                    condition=condition,
                    intervention=intervention,
                    prediction=prediction,
                    mechanism=mechanism,
                    falsification_criterion=(
                        "Reject if gains disappear under equal-compute ablations or OOD stress benchmark."
                    ),
                    minimum_viable_test=MinimalTest(
                        dataset=dataset,
                        baseline=baseline,
                        primary_metric=primary_metric,
                        success_threshold=">=4% relative gain with stronger robustness metrics",
                        estimated_compute=compute,
                        estimated_timeline=timeline,
                    ),
                    closest_existing_work=gap.nearest_prior_work,
                    novelty_claim=(
                        f"Novel because it treats {gap.gap_type} gap {gap.gap_id} as the primary optimization target, "
                        f"not a post-hoc evaluation artifact."
                    ),
                    expected_outcome_if_true="Stronger generalization with clearer mechanism attribution.",
                    expected_outcome_if_false="Current paradigm assumptions remain valid under this regime.",
                    theoretical_basis="causal inference + distributional robustness + constrained optimization",
                )
                signature = _canonical_signature(hypothesis)
                if signature in signatures:
                    continue
                signatures.add(signature)
                strategy_output[strategy].append(hypothesis)

        return dict(strategy_output)
