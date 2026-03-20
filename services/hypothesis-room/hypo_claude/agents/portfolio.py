"""Layer 5 agent — Portfolio construction."""

from __future__ import annotations

import json

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.portfolio import portfolio_construction_prompt
from hypo_claude.models import (
    DimensionScores,
    JudgeScore,
    PipelineConfig,
    ResearchPortfolio,
    StructuredHypothesis,
    TribunalVerdict,
    compute_panel_composite,
)

logger = structlog.get_logger(__name__)


class PortfolioConstructor:
    """Constructs a strategic research portfolio from ranked hypotheses."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def construct(
        self,
        ranked_hypotheses: list[StructuredHypothesis],
        panel_scores: dict[str, list[JudgeScore]],
        verdicts: dict[str, TribunalVerdict],
        config: PipelineConfig,
    ) -> ResearchPortfolio:
        # Build SIMPLIFIED ranked list — avoid sending full verdict/score objects
        # (which causes the LLM to hallucinate invalid TribunalVerdict literals)
        ranked_data = []
        for h in ranked_hypotheses:
            scores = panel_scores.get(h.id, [])
            composite = compute_panel_composite(scores)
            verdict = verdicts.get(h.id)

            # Extract only simple verdict summary fields
            verdict_info: dict = {}
            if verdict:
                verdict_info = {
                    "overall": verdict.overall_verdict,
                    "primary_weakness": verdict.primary_weakness,
                    "revision_directive": verdict.revision_directive,
                }
                if verdict.mechanism_validation:
                    verdict_info["mechanism_score"] = verdict.mechanism_validation.logical_score
                if verdict.resource_reality:
                    verdict_info["feasibility_score"] = verdict.resource_reality.feasibility_score

            ranked_data.append({
                "id": h.id,
                "title": h.title,
                "condition": h.condition,
                "intervention": h.intervention,
                "prediction": h.prediction,
                "mechanism": h.mechanism,
                "generation_strategy": h.generation_strategy,
                "falsification_criterion": h.falsification_criterion,
                "novelty_claim": h.novelty_claim,
                "panel_composite": round(composite, 1),
                "verdict": verdict_info,
                "judge_scores": {
                    js.judge_persona: js.scores.composite for js in scores
                } if scores else {},
            })

        ranked_json = json.dumps(ranked_data, indent=1)
        config_json = json.dumps(config.model_dump(), indent=1)

        # Pass empty strings for scores/verdicts — they're already embedded in ranked_data
        system, user = portfolio_construction_prompt(
            ranked_json, "", "", config_json
        )

        portfolio = await self._llm.generate_json(
            system, user,
            model_class=ResearchPortfolio,
            temperature=0.3,
            role=AgentRole.PORTFOLIO_CONSTRUCTOR,
        )

        # Fill in panel_composite for each portfolio hypothesis
        for ph in portfolio.hypotheses:  # type: ignore[union-attr]
            hid = ph.hypothesis.id
            if hid in panel_scores:
                ph.panel_composite = compute_panel_composite(panel_scores[hid])

        n = len(portfolio.hypotheses)  # type: ignore[union-attr]
        logger.info("portfolio.constructed", n_hypotheses=n)
        return portfolio  # type: ignore[return-value]
