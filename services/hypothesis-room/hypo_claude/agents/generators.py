"""Layer 2 agents — 7 hypothesis generation strategies."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.llm.prompts.strategies import STRATEGY_PROMPT_MAP, STRATEGY_ROLE_MAP
from hypo_claude.models import (
    GENERATION_STRATEGIES,
    ResearchLandscape,
    ResearchSpaceMap,
    StructuredHypothesis,
)

logger = structlog.get_logger(__name__)


class StrategyRunner:
    """Runs a single hypothesis generation strategy."""

    def __init__(self, llm: LLMProvider, strategy_name: str) -> None:
        self._llm = llm
        self.strategy_name = strategy_name
        self._prompt_fn = STRATEGY_PROMPT_MAP[strategy_name]
        role_token = STRATEGY_ROLE_MAP[strategy_name]
        if role_token in AgentRole.__members__:
            self._role = AgentRole[role_token]
        else:
            self._role = AgentRole(role_token.lower())

    async def generate(
        self,
        landscape: ResearchLandscape,
        space_map: ResearchSpaceMap,
        num_hypotheses: int = 5,
    ) -> list[StructuredHypothesis]:
        landscape_json = json.dumps(landscape.model_dump(), indent=1)

        # Focus on high-value gaps
        hvt_gaps = [g for g in space_map.all_gaps if g.gap_id in space_map.high_value_targets]
        if not hvt_gaps:
            hvt_gaps = space_map.all_gaps[:7]
        gaps_json = json.dumps([g.model_dump() for g in hvt_gaps], indent=1)

        system, user = self._prompt_fn(landscape_json, gaps_json, num_hypotheses)

        raw = await self._llm.generate(system, user, temperature=0.7, role=self._role)

        hypotheses = self._parse_hypotheses(raw)
        for h in hypotheses:
            h.generation_strategy = self.strategy_name

        logger.info(
            "strategy.done",
            strategy=self.strategy_name,
            n_hypotheses=len(hypotheses),
        )
        return hypotheses

    def _parse_hypotheses(self, raw: str) -> list[StructuredHypothesis]:
        """Parse LLM response into StructuredHypothesis list."""
        from hypo_claude.llm.provider import _extract_json

        try:
            data = _extract_json(raw)
        except ValueError:
            logger.warning("strategy.parse_fail", strategy=self.strategy_name)
            return []

        items: list[dict[str, Any]] = []
        if isinstance(data, dict):
            items = data.get("hypotheses", [])
            if not items and isinstance(data.get("items"), list):
                items = data["items"]
        elif isinstance(data, list):
            items = data

        results: list[StructuredHypothesis] = []
        for item in items:
            try:
                results.append(StructuredHypothesis.model_validate(item))
            except Exception as e:
                logger.warning("strategy.hypothesis_parse_fail", error=str(e)[:100])
                continue
        return results


class MultiStrategyGenerator:
    """Runs all 7 strategies in parallel and merges results."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._runners = {
            name: StrategyRunner(llm, name) for name in GENERATION_STRATEGIES
        }

    async def generate_all(
        self,
        landscape: ResearchLandscape,
        space_map: ResearchSpaceMap,
        num_per_strategy: int = 5,
        max_concurrent: int = 4,
    ) -> dict[str, list[StructuredHypothesis]]:
        """Run all 7 strategies with concurrency control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run(name: str, runner: StrategyRunner) -> tuple[str, list[StructuredHypothesis]]:
            async with semaphore:
                try:
                    hyps = await runner.generate(landscape, space_map, num_per_strategy)
                    return name, hyps
                except Exception as e:
                    logger.error("strategy.failed", strategy=name, error=str(e))
                    return name, []

        tasks = [_run(name, runner) for name, runner in self._runners.items()]
        results = await asyncio.gather(*tasks)

        strategy_outputs = dict(results)
        total = sum(len(v) for v in strategy_outputs.values())
        logger.info("generator.all_strategies_done", total_hypotheses=total)
        return strategy_outputs
