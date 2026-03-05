"""Layer 3 agent — Hypothesis evolution via critique-directed mutation."""

from __future__ import annotations

import json
import random

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.tribunal import evolve_hypothesis_prompt
from hypo_claude.models import MUTATION_STRATEGIES, StructuredHypothesis, TribunalVerdict

logger = structlog.get_logger(__name__)


class EvolverAgent:
    """Evolves hypotheses based on tribunal feedback using directed mutations."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def _select_mutation(self, verdict: TribunalVerdict) -> tuple[str, str]:
        """Select the best mutation strategy based on the tribunal's primary weakness."""
        weakness = verdict.primary_weakness.lower()

        # Map weaknesses to strategies
        if any(w in weakness for w in ("vague", "broad", "general", "scope")):
            key = "scope_reduction"
        elif any(w in weakness for w in ("mechanism", "causal", "how", "why")):
            key = "mechanism_deepening"
        elif any(w in weakness for w in ("predict", "quantit", "measur", "metric")):
            key = "prediction_sharpening"
        elif any(w in weakness for w in ("condition", "when", "context", "boundary")):
            key = "condition_specification"
        elif any(w in weakness for w in ("baseline", "compar", "threshold", "benchmark")):
            key = "baseline_anchoring"
        else:
            key = random.choice(list(MUTATION_STRATEGIES.keys()))

        return key, MUTATION_STRATEGIES[key]

    async def evolve(
        self, hypothesis: StructuredHypothesis, verdict: TribunalVerdict
    ) -> StructuredHypothesis:
        """Evolve a single hypothesis based on tribunal verdict."""
        mutation_key, mutation_desc = self._select_mutation(verdict)

        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        v_json = json.dumps(verdict.model_dump(), indent=1)

        system, user = evolve_hypothesis_prompt(h_json, v_json, mutation_key, mutation_desc)

        evolved = await self._llm.generate_json(
            system, user,
            model_class=StructuredHypothesis,
            temperature=0.5,
            role=AgentRole.EVOLVER,
        )

        # Preserve lineage
        evolved.generation_strategy = hypothesis.generation_strategy  # type: ignore[union-attr]
        evolved.source_gap_id = hypothesis.source_gap_id  # type: ignore[union-attr]

        logger.info(
            "evolver.evolved",
            original_id=hypothesis.id,
            mutation=mutation_key,
            new_id=evolved.id,  # type: ignore[union-attr]
        )
        return evolved  # type: ignore[return-value]
