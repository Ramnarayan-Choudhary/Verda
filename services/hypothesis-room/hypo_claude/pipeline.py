"""
Epistemic Pipeline — LangGraph 6-layer orchestrator.

Linear flow: START -> intelligence -> cartography -> generation ->
tribunal -> evaluation -> portfolio -> output -> END
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

import structlog
from langgraph.graph import END, START, StateGraph

from hypo_claude.config import DEFAULT_STAGE_TIMEOUTS, settings
from hypo_claude.layers import (
    layer0_intelligence,
    layer1_cartography,
    layer2_generation,
    layer3_tribunal,
    layer4_evaluation,
    layer5_portfolio,
    output,
)
from hypo_claude.llm.provider import LLMProvider
from hypo_claude.models import (
    GenerateRequest,
    GeneratorOutput,
    PipelineConfig,
    PipelineState,
    ProgressEvent,
    StageError,
    TokenUsage,
)

logger = structlog.get_logger(__name__)


class EpistemicPipeline:
    """Orchestrates the 6-layer hypothesis generation pipeline."""

    def __init__(self) -> None:
        self._llm = LLMProvider()
        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        graph = StateGraph(dict)

        graph.add_node("intelligence", self._wrap("intelligence", layer0_intelligence.run))
        graph.add_node("cartography", self._wrap("cartography", layer1_cartography.run))
        graph.add_node("generation", self._wrap("generation", layer2_generation.run))
        graph.add_node("tribunal", self._wrap("tribunal", layer3_tribunal.run))
        graph.add_node("evaluation", self._wrap("evaluation", layer4_evaluation.run))
        graph.add_node("portfolio", self._wrap("portfolio", layer5_portfolio.run))
        graph.add_node("output", self._wrap("output", output.run))

        graph.add_edge(START, "intelligence")
        graph.add_edge("intelligence", "cartography")
        graph.add_edge("cartography", "generation")
        graph.add_edge("generation", "tribunal")
        graph.add_edge("tribunal", "evaluation")
        graph.add_edge("evaluation", "portfolio")
        graph.add_edge("portfolio", "output")
        graph.add_edge("output", END)

        return graph.compile()

    def _wrap(self, stage_name: str, layer_fn: Callable) -> Callable:
        """Wrap a layer function with timeout, error handling, and progress."""
        llm = self._llm

        async def _wrapped(state: dict[str, Any]) -> dict[str, Any]:
            config: PipelineConfig = state.get("config", PipelineConfig())
            timeouts = {**DEFAULT_STAGE_TIMEOUTS, **(config.stage_timeouts or {})}
            timeout = timeouts.get(stage_name, 300)
            progress_cb = state.get("progress_callback")

            start = time.monotonic()
            logger.info("pipeline.stage_start", stage=stage_name)

            try:
                result = await asyncio.wait_for(
                    layer_fn(state, llm, progress=progress_cb),
                    timeout=timeout,
                )
                elapsed = time.monotonic() - start
                logger.info("pipeline.stage_done", stage=stage_name, elapsed=f"{elapsed:.1f}s")

                # Merge result into state
                state.update(result)
                return state

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.error("pipeline.stage_timeout", stage=stage_name, timeout=timeout)
                errors = state.get("errors", [])
                errors.append(StageError(stage=stage_name, message=f"Timeout after {timeout}s", recoverable=True))
                state["errors"] = errors
                return state

            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error("pipeline.stage_failed", stage=stage_name, error=str(e), elapsed=f"{elapsed:.1f}s")
                errors = state.get("errors", [])
                errors.append(StageError(stage=stage_name, message=str(e), recoverable=False))
                state["errors"] = errors
                raise

        return _wrapped

    async def generate(
        self,
        request: GenerateRequest,
        progress_callback: Callable | None = None,
    ) -> GeneratorOutput:
        """Run the full pipeline and return the final output."""

        initial_state = {
            "arxiv_id": request.arxiv_id,
            "pdf_path": request.pdf_path,
            "arxiv_ids": request.arxiv_ids,
            "config": request.config,
            "progress_callback": progress_callback,
            "errors": [],
        }

        logger.info(
            "pipeline.start",
            arxiv_id=request.arxiv_id,
            n_arxiv_ids=len(request.arxiv_ids),
        )

        start = time.monotonic()
        final_state = await self._graph.ainvoke(initial_state)
        elapsed = time.monotonic() - start

        logger.info(
            "pipeline.complete",
            elapsed=f"{elapsed:.1f}s",
            token_usage=self._llm.token_usage.model_dump(),
            errors=len(final_state.get("errors", [])),
        )

        output = final_state.get("final_output")
        if output is None:
            output = GeneratorOutput(
                hypotheses=[],
                reasoning_context="Pipeline completed with errors",
                generation_strategy="epistemic_engine",
                pipeline_version="v2",
            )

        return output

    def get_health_info(self) -> dict[str, Any]:
        return {
            "pipeline": "epistemic_engine_v2",
            "providers": self._llm.get_active_providers(),
            "token_usage": self._llm.token_usage.model_dump(),
        }
