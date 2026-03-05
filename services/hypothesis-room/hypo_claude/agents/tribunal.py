"""Layer 3 agents — 4 critics + mechanism validator."""

from __future__ import annotations

import asyncio
import json

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.tribunal import (
    devils_advocate_prompt,
    domain_critic_prompt,
    mechanism_validation_prompt,
    methodology_critic_prompt,
    resource_realist_prompt,
    tribunal_synthesis_prompt,
)
from hypo_claude.models import (
    DevilsAdvocateCritique,
    DomainCritique,
    MechanismValidation,
    MethodologyCritique,
    ResearchLandscape,
    ResourceCritique,
    StructuredHypothesis,
    TribunalVerdict,
)

logger = structlog.get_logger(__name__)


class DomainCriticAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def critique(self, hypothesis: StructuredHypothesis, landscape: ResearchLandscape) -> DomainCritique:
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        l_json = json.dumps(landscape.model_dump(), indent=1)
        system, user = domain_critic_prompt(h_json, l_json)
        return await self._llm.generate_json(system, user, DomainCritique, temperature=0.2, role=AgentRole.DOMAIN_CRITIC)  # type: ignore[return-value]


class MethodologyCriticAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def critique(self, hypothesis: StructuredHypothesis) -> MethodologyCritique:
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        system, user = methodology_critic_prompt(h_json)
        return await self._llm.generate_json(system, user, MethodologyCritique, temperature=0.2, role=AgentRole.METHODOLOGY_CRITIC)  # type: ignore[return-value]


class DevilsAdvocateAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def critique(self, hypothesis: StructuredHypothesis) -> DevilsAdvocateCritique:
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        system, user = devils_advocate_prompt(h_json)
        return await self._llm.generate_json(system, user, DevilsAdvocateCritique, temperature=0.3, role=AgentRole.DEVILS_ADVOCATE)  # type: ignore[return-value]


class ResourceRealistAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def critique(self, hypothesis: StructuredHypothesis) -> ResourceCritique:
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        system, user = resource_realist_prompt(h_json)
        return await self._llm.generate_json(system, user, ResourceCritique, temperature=0.2, role=AgentRole.RESOURCE_CRITIC)  # type: ignore[return-value]


class MechanismValidatorAgent:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def validate(self, hypothesis: StructuredHypothesis) -> MechanismValidation:
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        system, user = mechanism_validation_prompt(h_json)
        return await self._llm.generate_json(system, user, MechanismValidation, temperature=0.2, role=AgentRole.MECHANISM_VALIDATOR)  # type: ignore[return-value]


class TribunalPanel:
    """Orchestrates all 4 critics + mechanism validator for one hypothesis."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._domain = DomainCriticAgent(llm)
        self._methodology = MethodologyCriticAgent(llm)
        self._devils = DevilsAdvocateAgent(llm)
        self._resource = ResourceRealistAgent(llm)
        self._mechanism = MechanismValidatorAgent(llm)

    async def evaluate(
        self, hypothesis: StructuredHypothesis, landscape: ResearchLandscape
    ) -> TribunalVerdict:
        """Run all critics in parallel, then synthesize into a verdict."""
        domain, methodology, devils, resource, mechanism = await asyncio.gather(
            self._domain.critique(hypothesis, landscape),
            self._methodology.critique(hypothesis),
            self._devils.critique(hypothesis),
            self._resource.critique(hypothesis),
            self._mechanism.validate(hypothesis),
        )

        # Synthesize into verdict
        h_json = json.dumps(hypothesis.model_dump(), indent=1)
        system, user = tribunal_synthesis_prompt(
            h_json,
            json.dumps(domain.model_dump()),
            json.dumps(methodology.model_dump()),
            json.dumps(devils.model_dump()),
            json.dumps(resource.model_dump()),
            json.dumps(mechanism.model_dump()),
        )

        verdict = await self._llm.generate_json(
            system, user,
            model_class=TribunalVerdict,
            temperature=0.2,
            role=AgentRole.DOMAIN_CRITIC,
        )
        verdict.hypothesis_id = hypothesis.id  # type: ignore[union-attr]
        verdict.domain_validity = domain  # type: ignore[union-attr]
        verdict.methodology = methodology  # type: ignore[union-attr]
        verdict.devils_advocate = devils  # type: ignore[union-attr]
        verdict.resource_reality = resource  # type: ignore[union-attr]
        verdict.mechanism_validation = mechanism  # type: ignore[union-attr]

        logger.info(
            "tribunal.verdict",
            hypothesis_id=hypothesis.id,
            verdict=verdict.overall_verdict,  # type: ignore[union-attr]
        )
        return verdict  # type: ignore[return-value]
