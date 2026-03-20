from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

import numpy as np
import structlog

from hypo_gpt.assessment.assessment_agent import score_hypothesis_fast
from hypo_gpt.layer2_generation.idea_tree import (
    get_failed_nodes as tree_get_failed_nodes,
    get_frontier as tree_get_frontier,
    semantic_novelty_guard,
)
from hypo_gpt.layer2_generation.mcgs import MCGSEngine
from hypo_gpt.layer2_generation.operators import apply_operator
from hypo_gpt.layer2_generation.strategies import STRATEGY_BUILDERS
from hypo_gpt.llm import LLMProvider
from hypo_gpt.models import (
    CausalChain,
    ExperimentSketch,
    GapAnalysis,
    HypothesisV2,
    IdeaTree,
    IdeaTreeNode,
    MemoryEntry,
    ResearchLandscape,
    ResearchSpaceMap,
    StructuredHypothesis,
)
from shared.embedding import embed

logger = structlog.get_logger(__name__)

STRATEGIES = [
    "gap_fill",
    "cross_domain",
    "assumption_challenge",
    "method_recomb",
    "failure_inversion",
    "abductive",
    "constraint_relax",
]

LEGACY_MAPPING = {
    "gap_fill": "mechanism_extractor",
    "cross_domain": "domain_bridge",
    "assumption_challenge": "assumption_challenger",
    "method_recomb": "synthesis_catalyst",
    "failure_inversion": "falsification_designer",
    "abductive": "contradiction_resolver",
    "constraint_relax": "constraint_relaxer",
}


def _text_signature(hypothesis: HypothesisV2) -> str:
    return (
        f"{hypothesis.strategy}|{hypothesis.title}|{hypothesis.core_claim}|"
        f"{hypothesis.causal_chain.intermediate}|{hypothesis.experiment.design}|{hypothesis.falsification_criterion}"
    ).lower()


def _infer_time_horizon(round_index: int) -> str:
    if round_index <= 0:
        return "1_month"
    if round_index == 1:
        return "3_months"
    if round_index == 2:
        return "6_months"
    return "12months_plus"


def _round_focus(round_index: int) -> str:
    mapping = {
        0: "near-term validation under bounded compute",
        1: "mid-term generalization across stress splits",
        2: "longer-horizon scaling and robustness retention",
    }
    return mapping.get(round_index, "extended-horizon transfer and deployment reliability")


def _variant_focus(variant_index: int) -> tuple[str, str]:
    variants = [
        ("causal_mediator_probe", "explicit mediator instrumentation and factorized ablations"),
        ("distribution_shift_stress", "stress-suite validation across domain and covariate shifts"),
        ("resource_bounded_deploy", "deployment realism under strict latency/compute/data constraints"),
    ]
    return variants[variant_index % len(variants)]


def _clean_gap_topic(statement: str, max_len: int = 72) -> str:
    text = statement.strip()
    text = re.sub(r"^evidence on\s+'?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^causal mechanism for\s+'?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^unresolved theoretical bottleneck:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^assumption\s+'?", "", text, flags=re.IGNORECASE)
    text = text.strip(" '\".")
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0]
    return text


def _extract_topic_from_landscape(landscape: ResearchLandscape) -> str:
    intent = landscape.research_intent or ""
    m = re.search(r"paper:\s*([^|]+)", intent, flags=re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if 4 <= len(candidate) <= 80:
            return candidate

    merged = " ".join([*landscape.established_facts[:3], *landscape.open_problems[:2], intent])
    tokens = [t for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", merged.lower()) if t not in {
        "paper", "domain", "known", "limitations", "objective", "generate", "high", "quality",
        "under", "with", "from", "this", "that", "which", "mechanism", "distribution", "deployment"
    }]
    if not tokens:
        return "target task"
    phrase = " ".join(tokens[:3]).strip()
    return phrase[:64]


def _strategy_fallback_title(strategy: str, topic: str) -> str:
    templates = {
        "gap_fill": f"Mechanism Probe for {topic}",
        "cross_domain": f"Cross-domain Mechanism Transfer for {topic}",
        "assumption_challenge": f"Assumption Stress-Test for {topic}",
        "method_recomb": f"Hybrid Intervention Stack for {topic}",
        "failure_inversion": f"Failure-Signal Inversion for {topic}",
        "abductive": f"Anomaly Explanation for {topic}",
        "constraint_relax": f"Relaxed-Constraint Regime for {topic}",
    }
    return templates.get(strategy, f"Hypothesis for {topic}")


def _strategy_fallback_condition(strategy: str, topic: str) -> str:
    templates = {
        "gap_fill": f"a missing causal mechanism limits robustness for {topic}",
        "cross_domain": f"single-domain methods for {topic} plateau under distribution shift",
        "assumption_challenge": f"current assumptions for {topic} fail under deployment constraints",
        "method_recomb": f"individual methods for {topic} underperform without coordinated interventions",
        "failure_inversion": f"known failure patterns for {topic} can be inverted into training signals",
        "abductive": f"anomalous behavior in {topic} remains unexplained by current mechanisms",
        "constraint_relax": f"hard constraints cap performance for {topic} under bounded compute",
    }
    return templates.get(strategy, f"{topic} requires a clearer, testable intervention")


def _extract_paper_ids(landscape: ResearchLandscape) -> list[str]:
    pool = [item.strip() for item in landscape.established_facts if item.strip()]
    if len(pool) < 2:
        synthetic_sources = [
            landscape.research_intent,
            landscape.intent_domain,
            landscape.intent_subdomain,
            *(landscape.open_problems[:3]),
        ]
        for idx, source in enumerate(synthetic_sources, start=1):
            token = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")
            if token:
                pool.append(f"{token[:32]}_{idx}")
            if len(pool) >= 3:
                break
        if len(pool) < 2:
            pool.extend(["landscape_ref_1", "landscape_ref_2"])
    return pool[:6]


def _evidence_anchor(landscape: ResearchLandscape) -> tuple[str, str]:
    method = landscape.methodological_consensus[0] if landscape.methodological_consensus else "equal-compute ablation"
    problem = (
        landscape.open_problems[0]
        if landscape.open_problems
        else (landscape.bottleneck_hypothesis or "deployment-shift robustness")
    )
    method = " ".join(method.split())[:80]
    problem = " ".join(problem.split())[:120]
    return method, problem


def _has_numeric_comparison(text: str) -> bool:
    lowered = text.lower()
    return bool(re.search(r"\d", text)) and any(token in lowered for token in ("<", ">", "below", "above", "under", "over"))


def _is_generic_text(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    if len(lowered) > 96:
        return True
    generic_markers = [
        "mechanistic uncertainty under distribution shift",
        "unresolved theoretical bottleneck",
        "mechanistic attribution gap for",
        "factorized ablation protocol to isolate claimed causal components",
        "causal component interactions",
        "conflicting evidence around",
        "principles into",
        "training distribution approximates deployment distribution",
        "control theory techniques are underused in nlp training loops",
        "improves performance and robustness",
        "state-of-the-art",
    ]
    if any(marker in lowered for marker in generic_markers):
        return True
    if len(lowered.split()) < 6:
        return True
    return False


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(np.dot(a, b) / denom)


def _strategy_pool(strategy: str, space_map: ResearchSpaceMap) -> list[GapAnalysis]:
    if strategy == "gap_fill":
        return space_map.knowledge_gaps + space_map.theoretical_gaps
    if strategy == "cross_domain":
        return space_map.method_gaps
    if strategy == "assumption_challenge":
        return space_map.assumption_gaps
    if strategy == "method_recomb":
        return space_map.method_gaps + space_map.knowledge_gaps
    if strategy == "failure_inversion":
        return space_map.theoretical_gaps + space_map.knowledge_gaps
    if strategy == "abductive":
        return space_map.knowledge_gaps + space_map.assumption_gaps
    return space_map.theoretical_gaps + space_map.assumption_gaps


class StrategyGenerator:
    def __init__(self) -> None:
        self.novelty_threshold = 0.85
        self.llm = LLMProvider()
        self._strategy_seed_cache: dict[str, dict[str, str]] = {}
        self._llm_failures = 0

    async def _seed_payload_from_llm(
        self,
        *,
        strategy: str,
        gap: GapAnalysis,
        landscape: ResearchLandscape,
        map_: ResearchSpaceMap,
    ) -> dict[str, str] | None:
        if not self.llm.is_configured:
            return None

        strategy_contract = {
            "gap_fill": "close a concrete mechanism gap with measurable mediators",
            "cross_domain": "transfer a mechanism from another domain with explicit mapping",
            "assumption_challenge": "invert a hidden assumption and test boundary conditions",
            "method_recomb": "combine complementary methods with factorized ablations",
            "failure_inversion": "turn known failure patterns into intervention signals",
            "abductive": "explain an anomaly using a minimal additional mediator",
            "constraint_relax": "relax one limiting constraint while bounding risk",
        }.get(strategy, "propose a testable hypothesis")
        method_anchor, problem_anchor = _evidence_anchor(landscape)

        system = (
            "You are a principal AI research scientist. Generate one high-quality, paper-grounded hypothesis seed. "
            "Avoid generic words like 'optimization improvements'. Be domain-specific, concrete, and falsifiable."
        )
        user = (
            f"Research intent: {landscape.research_intent}\n"
            f"Domain: {landscape.intent_domain}/{landscape.intent_subdomain}\n"
            f"Gap statement: {gap.statement}\n"
            f"Gap importance: {gap.why_it_matters}\n"
            f"SOTA bottleneck: {map_.sota_structural_reason}\n"
            f"Failed approaches: {', '.join(map_.failed_approaches_analysis[:2])}\n"
            f"Strategy: {strategy} ({strategy_contract})\n\n"
            f"Evidence anchors: method={method_anchor}; open_problem={problem_anchor}\n"
            "Return strict JSON object with keys:\n"
            "title_seed, condition, core_claim, mechanism_bias, outcome, falsification, design, success_threshold\n"
            "Constraints:\n"
            "- title_seed <= 90 chars, no brackets\n"
            "- falsification must include numeric threshold and baseline comparison\n"
            "- design must include ablation and stress evaluation\n"
            "- success_threshold must be quantitative\n"
        )
        payload = await self.llm.complete_json(
            system_prompt=system,
            user_prompt=user,
            temperature=0.3,
            max_output_tokens=600,
            json_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title_seed": {"type": "string", "minLength": 12, "maxLength": 90},
                    "condition": {"type": "string", "minLength": 12},
                    "core_claim": {"type": "string", "minLength": 24},
                    "mechanism_bias": {"type": "string", "minLength": 20},
                    "outcome": {"type": "string", "minLength": 16},
                    "falsification": {"type": "string", "minLength": 20},
                    "design": {"type": "string", "minLength": 20},
                    "success_threshold": {"type": "string", "minLength": 8},
                },
                "required": [
                    "title_seed",
                    "condition",
                    "core_claim",
                    "mechanism_bias",
                    "outcome",
                    "falsification",
                    "design",
                    "success_threshold",
                ],
            },
        )
        if not isinstance(payload, dict):
            self._llm_failures += 1
            return None

        required_keys = {
            "title_seed",
            "condition",
            "core_claim",
            "mechanism_bias",
            "outcome",
            "falsification",
            "design",
            "success_threshold",
        }
        if not required_keys.issubset(payload.keys()):
            self._llm_failures += 1
            return None

        seed: dict[str, str] = {}
        for key in required_keys:
            value = str(payload.get(key, "")).strip()
            if len(value) < 8:
                self._llm_failures += 1
                return None
            seed[key] = value
        if not self._seed_quality(seed):
            self._llm_failures += 1
            return None
        self._llm_failures = 0
        return seed

    @staticmethod
    def _seed_quality(payload: dict[str, str]) -> bool:
        if _is_generic_text(payload.get("title_seed", "")):
            return False
        if _is_generic_text(payload.get("core_claim", "")):
            return False
        if not _has_numeric_comparison(payload.get("falsification", "")):
            return False
        design = payload.get("design", "").lower()
        if "ablation" not in design or "compute" not in design:
            return False
        return True

    def _compose_payload(
        self,
        *,
        strategy: str,
        gap: GapAnalysis,
        landscape: ResearchLandscape,
        topic: str,
        base_payload: dict[str, str],
        llm_payload: dict[str, str] | None,
    ) -> dict[str, str]:
        payload = dict(base_payload)
        if llm_payload:
            for key, value in llm_payload.items():
                if isinstance(value, str) and len(value.strip()) >= 8:
                    payload[key] = value.strip()

        method_anchor, problem_anchor = _evidence_anchor(landscape)
        fallback_title = _strategy_fallback_title(strategy, topic)
        fallback_condition = _strategy_fallback_condition(strategy, topic)

        if _is_generic_text(payload.get("title_seed", "")):
            payload["title_seed"] = fallback_title
        if _is_generic_text(payload.get("condition", "")):
            payload["condition"] = fallback_condition

        if _is_generic_text(payload.get("core_claim", "")):
            payload["core_claim"] = (
                f"Address {gap.gap_id} by integrating {method_anchor} with explicit mediator tracking around {problem_anchor}."
            )
        if "mediator" not in payload.get("mechanism_bias", "").lower():
            payload["mechanism_bias"] = (
                f"{payload.get('mechanism_bias', '').strip()} Use explicit mediator readouts and factorized ablation checks."
            ).strip()
        if "ablation" not in payload.get("design", "").lower():
            payload["design"] = f"{payload.get('design', '').strip()} Include factorized ablation matrix."
        if "compute" not in payload.get("design", "").lower():
            payload["design"] = f"{payload['design']} Enforce equal-compute controls."

        if not _has_numeric_comparison(payload.get("falsification", "")):
            payload["falsification"] = (
                "Disproved if shifted-split primary metric is < 1.03x baseline under equal-compute stress evaluation."
            )
        if not re.search(r"\d", payload.get("success_threshold", "")):
            payload["success_threshold"] = ">=3% shifted-split gain with <=1% robustness variance increase"
        return payload

    async def generate(
        self,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        per_strategy: int = 3,
    ) -> dict[str, list[StructuredHypothesis]]:
        hypotheses = await self.generate_hypotheses(landscape, research_space_map, per_strategy=per_strategy, round_index=0)
        grouped: dict[str, list[StructuredHypothesis]] = defaultdict(list)
        for item in hypotheses:
            grouped[LEGACY_MAPPING[item.strategy]].append(item.to_structured())
        return dict(grouped)

    async def generate_hypotheses(
        self,
        landscape: ResearchLandscape,
        research_space_map: ResearchSpaceMap,
        *,
        per_strategy: int,
        round_index: int,
        skip_strategies: Iterable[str] | None = None,
    ) -> list[HypothesisV2]:
        skip = set(skip_strategies or [])
        papers = _extract_paper_ids(landscape)
        topic = _extract_topic_from_landscape(landscape)

        outputs: list[HypothesisV2] = []
        for strategy in STRATEGIES:
            if strategy in skip:
                continue
            pool = _strategy_pool(strategy, research_space_map)
            if not pool:
                continue

            if strategy not in self._strategy_seed_cache:
                llm_seed = None
                if self._llm_failures < 6:
                    llm_seed = await self._seed_payload_from_llm(
                        strategy=strategy,
                        gap=pool[0],
                        landscape=landscape,
                        map_=research_space_map,
                    )
                if llm_seed is not None:
                    self._strategy_seed_cache[strategy] = llm_seed

            for idx in range(per_strategy):
                gap = pool[(round_index + idx) % len(pool)]
                base_payload = STRATEGY_BUILDERS[strategy](gap, round_index=round_index)
                strategy_payload = self._compose_payload(
                    strategy=strategy,
                    gap=gap,
                    landscape=landscape,
                    topic=topic,
                    base_payload=base_payload,
                    llm_payload=self._strategy_seed_cache.get(strategy),
                )
                variant_tag, variant_focus = _variant_focus(idx)
                round_focus = _round_focus(round_index)
                bridge = research_space_map.cross_domain_bridges[0].source_domain if research_space_map.cross_domain_bridges else None
                challenged = research_space_map.contestable_assumptions[0].assumption if research_space_map.contestable_assumptions else None
                fallback_title = _strategy_fallback_title(strategy, topic)
                title_seed = strategy_payload.get("title_seed", fallback_title).strip()
                if len(title_seed) < 10 or _is_generic_text(title_seed):
                    title_seed = fallback_title
                condition_seed = strategy_payload.get("condition", "")
                if _is_generic_text(condition_seed):
                    condition_seed = _strategy_fallback_condition(strategy, topic)

                hypothesis = HypothesisV2(
                    title=title_seed[:120],
                    strategy=strategy,
                    problem_being_solved=(
                        f"{condition_seed}. Focus: {round_focus}."
                    ),
                    core_claim=(
                        f"{strategy_payload['core_claim']} Variant emphasis: {variant_focus}."
                    ),
                    causal_chain=CausalChain(
                        intervention=(
                            f"Apply targeted intervention for {gap.gap_id} under strict equal-compute controls. "
                            f"{strategy_payload['mechanism_bias']} This variant prioritizes {variant_focus}."
                        ),
                        intermediate=(
                            f"{strategy_payload['mechanism_bias']} The intervention introduces a measurable mediator pathway that "
                            f"decouples performance from spurious correlations and stabilizes dynamics under stress conditions. "
                            f"Evaluation focus: {round_focus}."
                        ),
                        outcome=strategy_payload["outcome"],
                        conditions=[strategy_payload["condition"], round_focus],
                        breaks_when=["causal ablation removes effect", "improvement disappears under equal compute"],
                    ),
                    falsification_criterion=(
                        f"{strategy_payload['falsification']} Variant {variant_tag} fails if gain is < 1.01x baseline."
                    ),
                    grounding_paper_ids=papers[:2],
                    challenged_assumption=challenged if strategy == "assumption_challenge" else None,
                    source_domain_bridge=bridge if strategy == "cross_domain" else None,
                    anomaly_being_explained=gap.statement if strategy == "abductive" else None,
                    experiment=ExperimentSketch(
                        design=f"{strategy_payload['design']} Focus path: {variant_focus}. Gap: {gap.gap_id}.",
                        baseline="Best reported baseline under identical compute and data budget.",
                        primary_metric="robustness-adjusted primary metric",
                        success_threshold=strategy_payload["success_threshold"],
                        compute_estimate=("4xA100 for 18h" if idx % 2 == 0 else "2xA100 for 24h"),
                        time_horizon=_infer_time_horizon(round_index),
                        required_data="Public benchmark with shift splits and documented baselines",
                    ),
                    generation_round=round_index,
                )
                scored = score_hypothesis_fast(hypothesis, landscape)
                outputs.append(scored)

        deduped: list[HypothesisV2] = []
        signatures: set[str] = set()
        for hypothesis in outputs:
            sig = _text_signature(hypothesis)
            if sig in signatures:
                continue
            signatures.add(sig)
            deduped.append(hypothesis)
        return deduped

    def score_hypothesis(self, hypothesis: HypothesisV2) -> HypothesisV2:
        # Kept for backward compatibility in call sites; prefers assessment_agent contract.
        dummy_landscape = ResearchLandscape(research_intent="generated")
        return score_hypothesis_fast(hypothesis, dummy_landscape)

    async def build_tree(
        self,
        *,
        research_query: str,
        landscape: ResearchLandscape,
        space_map: ResearchSpaceMap,
        per_strategy: int,
        max_rounds: int,
        skip_strategies: list[str] | None = None,
        memory_negatives: list[MemoryEntry] | None = None,
    ) -> tuple[IdeaTree, list[str]]:
        tree = IdeaTree(research_query=research_query)
        skip = set(skip_strategies or [])
        self._strategy_seed_cache = {}
        self._llm_failures = 0

        for round_index in range(max_rounds):
            candidates = await self.generate_hypotheses(
                landscape,
                space_map,
                per_strategy=per_strategy,
                round_index=round_index,
                skip_strategies=skip,
            )

            if not tree.nodes:
                inserted = await self._insert_roots(tree, candidates, memory_negatives=memory_negatives or [])
            else:
                inserted = await self._expand(
                    tree,
                    candidates,
                    landscape=landscape,
                    space_map=space_map,
                    memory_negatives=memory_negatives or [],
                )

            for strategy in MCGSEngine.blocked_strategies(tree, threshold=0.40):
                skip.add(strategy)

            logger.info(
                "hypo_gpt.layer2.round",
                round=round_index + 1,
                candidates=len(candidates),
                inserted=inserted,
                tree_nodes=len(tree.nodes),
                llm_seeded_strategies=len(self._strategy_seed_cache),
                llm_seed_failures=self._llm_failures,
                blocked_strategies=sorted(skip),
            )

        if tree.nodes:
            tree.best_node_id = max(tree.nodes.values(), key=lambda item: item.hypothesis.composite_score).node_id
        return tree, sorted(skip)

    async def _insert_roots(
        self,
        tree: IdeaTree,
        candidates: list[HypothesisV2],
        *,
        memory_negatives: list[MemoryEntry],
    ) -> int:
        insertions: list[tuple[HypothesisV2, np.ndarray]] = []
        for hypothesis in candidates:
            emb = await embed(_text_signature(hypothesis))
            insertions.append((hypothesis, np.asarray(emb, dtype=np.float32)))

        inserted = 0
        for hypothesis, emb in insertions:
            if hypothesis.composite_score < 0.35:
                continue
            if not self._is_novel(tree, emb, memory_negatives=memory_negatives):
                continue
            node_id = f"n{len(tree.nodes)}"
            hypothesis.tree_node_id = node_id
            node = IdeaTreeNode(node_id=node_id, hypothesis=hypothesis, embedding=emb.tolist())
            tree.nodes[node_id] = node
            tree.root_ids.append(node_id)
            inserted += 1
        return inserted

    async def _expand(
        self,
        tree: IdeaTree,
        candidates: list[HypothesisV2],
        *,
        landscape: ResearchLandscape,
        space_map: ResearchSpaceMap,
        memory_negatives: list[MemoryEntry],
    ) -> int:
        inserted = 0
        for hypothesis in candidates:
            if hypothesis.composite_score < 0.35:
                continue

            candidate_emb = np.asarray(await embed(_text_signature(hypothesis)), dtype=np.float32)
            if not self._is_novel(tree, candidate_emb, memory_negatives=memory_negatives):
                continue

            parent_ids = self._select_parent_ids(tree, strategy=hypothesis.strategy)
            parent_b = tree.nodes[parent_ids[1]].hypothesis if len(parent_ids) > 1 else None
            chosen_operator = self._pick_operator(hypothesis)
            mutated = apply_operator(chosen_operator, hypothesis, space_map, parent_b=parent_b)
            mutated = score_hypothesis_fast(mutated, landscape)
            if mutated.composite_score < 0.35:
                continue

            node_id = f"n{len(tree.nodes)}"
            mutated.tree_node_id = node_id
            mutated.parent_hypo_ids = [tree.nodes[pid].hypothesis.hypo_id for pid in parent_ids]

            node = IdeaTreeNode(
                node_id=node_id,
                hypothesis=mutated,
                parent_ids=parent_ids,
                mutation_operator=chosen_operator,
                embedding=candidate_emb.tolist(),
            )
            tree.nodes[node_id] = node
            for parent_id in parent_ids:
                tree.nodes[parent_id].child_ids.append(node_id)
            self._backpropagate(tree, node_id, mutated.composite_score)
            inserted += 1
        return inserted

    def _is_novel(
        self,
        tree: IdeaTree,
        candidate_embedding: np.ndarray,
        *,
        memory_negatives: list[MemoryEntry],
    ) -> bool:
        threshold = 0.90 if len(self._strategy_seed_cache) >= 4 else 0.97
        if not semantic_novelty_guard(tree, candidate_embedding, threshold=threshold):
            return False
        for negative in memory_negatives:
            if not negative.hypothesis_embedding:
                continue
            neg = np.asarray(negative.hypothesis_embedding, dtype=np.float32)
            if neg.size == 0:
                continue
            if _cosine(candidate_embedding, neg) > 0.80:
                return False
        return True

    def _select_parent_ids(self, tree: IdeaTree, *, strategy: str) -> list[str]:
        frontier = self.get_frontier(tree)
        if not frontier:
            return []
        ranked = sorted(frontier, key=lambda item: item.ucb_score(tree.total_visits + 1), reverse=True)
        primary = ranked[0].node_id
        if strategy == "method_recomb" and len(ranked) > 1:
            secondary = ranked[1].node_id
            if secondary != primary:
                emb_a = np.asarray(tree.nodes[primary].embedding, dtype=np.float32)
                emb_b = np.asarray(tree.nodes[secondary].embedding, dtype=np.float32)
                if emb_a.size and emb_b.size and _cosine(emb_a, emb_b) < 0.5:
                    return [primary, secondary]
        return [primary]

    @staticmethod
    def _pick_operator(hypothesis: HypothesisV2) -> str:
        if hypothesis.mechanism_coherence < 0.7:
            return "deepen_mechanism"
        if hypothesis.feasibility < 0.6:
            return "narrow_scope"
        if hypothesis.novelty < 0.5:
            return "broaden_claim"
        if hypothesis.strategy == "cross_domain" and not hypothesis.source_domain_bridge:
            return "inject_analogy"
        if hypothesis.strategy == "assumption_challenge":
            return "challenge_assume"
        if hypothesis.strategy == "method_recomb":
            return "recombine"
        if re.search(r"\d", hypothesis.falsification_criterion) is None:
            return "sharpen_falsify"
        return "none"

    @staticmethod
    def _backpropagate(tree: IdeaTree, node_id: str, value: float, decay: float = 0.7, max_depth: int = 10) -> None:
        queue: list[tuple[str, float, int]] = [(node_id, value, 0)]
        visited: set[tuple[str, int]] = set()

        while queue:
            current_id, current_value, depth = queue.pop(0)
            key = (current_id, depth)
            if key in visited:
                continue
            visited.add(key)

            node = tree.nodes[current_id]
            node.visit_count += 1
            node.total_value += current_value
            tree.total_visits += 1

            if depth >= max_depth:
                continue
            for parent_id in node.parent_ids:
                if parent_id in tree.nodes:
                    queue.append((parent_id, current_value * decay, depth + 1))

    @staticmethod
    def get_frontier(tree: IdeaTree, min_score: float = 0.4) -> list[IdeaTreeNode]:
        return tree_get_frontier(tree, min_score=min_score)

    @staticmethod
    def get_failed_nodes(tree: IdeaTree) -> list[IdeaTreeNode]:
        return tree_get_failed_nodes(tree)
