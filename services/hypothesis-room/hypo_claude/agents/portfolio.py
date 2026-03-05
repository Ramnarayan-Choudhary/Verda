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
        # Build ranked list with scores
        ranked_data = []
        for h in ranked_hypotheses:
            scores = panel_scores.get(h.id, [])
            composite = compute_panel_composite(scores)
            verdict = verdicts.get(h.id)
            ranked_data.append({
                "hypothesis": h.model_dump(),
                "panel_composite": composite,
                "verdict_summary": verdict.overall_verdict if verdict else "unknown",
                "scores_summary": {
                    js.judge_persona: js.scores.composite for js in scores
                } if scores else {},
            })

        ranked_json = json.dumps(ranked_data, indent=1)
        scores_json = json.dumps(
            {hid: [js.model_dump() for js in jsl] for hid, jsl in panel_scores.items()},
            indent=1,
        )
        verdicts_json = json.dumps(
            {hid: v.model_dump() for hid, v in verdicts.items()},
            indent=1,
        )
        config_json = json.dumps(config.model_dump(), indent=1)

        system, user = portfolio_construction_prompt(
            ranked_json, scores_json, verdicts_json, config_json
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
