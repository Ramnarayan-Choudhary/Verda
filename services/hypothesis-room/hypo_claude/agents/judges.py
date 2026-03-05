"""Layer 4 agents — 3-judge panel evaluation."""

from __future__ import annotations

import asyncio
import json

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.judges import (
    conservative_judge_prompt,
    generalist_judge_prompt,
    practitioner_judge_prompt,
)
from hypo_claude.models import JudgeScore, StructuredHypothesis, TribunalVerdict

logger = structlog.get_logger(__name__)


class JudgePanel:
    """3-judge panel that scores hypotheses on 7 dimensions."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def evaluate(
        self, hypothesis: StructuredHypothesis, verdict: TribunalVerdict
    ) -> list[JudgeScore]:
        """Run all 3 judges in parallel for one hypothesis."""
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        v_json = json.dumps(verdict.model_dump(), indent=1)

        conservative, generalist, practitioner = await asyncio.gather(
            self._judge(conservative_judge_prompt, h_json, v_json, AgentRole.CONSERVATIVE_JUDGE),
            self._judge(generalist_judge_prompt, h_json, v_json, AgentRole.GENERALIST_JUDGE),
            self._judge(practitioner_judge_prompt, h_json, v_json, AgentRole.PRACTITIONER_JUDGE),
        )

        scores = [conservative, generalist, practitioner]
        composites = [s.scores.composite for s in scores]
        logger.info(
            "judges.scored",
            hypothesis_id=hypothesis.id,
            composites=composites,
        )
        return scores

    async def _judge(
        self,
        prompt_fn,
        hypothesis_json: str,
        verdict_json: str,
        role: AgentRole,
    ) -> JudgeScore:
        system, user = prompt_fn(hypothesis_json, verdict_json)
        return await self._llm.generate_json(  # type: ignore[return-value]
            system, user,
            model_class=JudgeScore,
            temperature=0.2,
            role=role,
        )
