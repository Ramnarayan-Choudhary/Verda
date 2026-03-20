"""
Epistemic Pipeline — LangGraph 7-layer orchestrator.

Linear flow: START -> intelligence -> cartography -> generation ->
tribunal -> evaluation -> portfolio -> output -> END

Enhancements over v1:
- 5 critics + mechanism validator gate (3-cycle mutation targeting)
- IdeaTree with UCB1 for lineage tracking
- Controversy detection in panel evaluation
- 5-slot risk-tiered portfolio with correlation removal
- Cross-session memory (negative blocking + positive building)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Callable

import structlog
from langgraph.graph import END, START, StateGraph

from shared.memory_store import HypothesisMemoryStore

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
    MemoryContext,
    PipelineConfig,
    PipelineState,
    ProgressEvent,
    StageError,
    TokenUsage,
)

logger = structlog.get_logger(__name__)

# Singleton memory store — persists across pipeline runs within the same process
_global_memory_store = HypothesisMemoryStore()


class EpistemicPipeline:
    """Orchestrates the 7-layer hypothesis generation pipeline."""

    def __init__(self, memory_store: HypothesisMemoryStore | None = None) -> None:
        self._llm = LLMProvider()
        self._memory_store = memory_store or _global_memory_store
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
        """Wrap a layer function with timeout, error handling, progress, and checkpoint support."""
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

                # Emit checkpoint event if enabled for this stage
                if (
                    config.enable_checkpoints
                    and stage_name in (config.checkpoint_stages or [])
                    and progress_cb
                ):
                    checkpoint_data = self._build_checkpoint_data(stage_name, state)
                    await progress_cb(
                        "checkpoint",
                        f"Checkpoint after {stage_name}: {checkpoint_data.get('summary', '')}",
                        0, 0,
                    )

                return state

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.error("pipeline.stage_timeout", stage=stage_name, timeout=timeout)
                errors = state.get("errors", [])
                errors.append(StageError(stage=stage_name, message=f"Timeout after {timeout}s", recoverable=True))
                state["errors"] = errors

                # Provide safe defaults so downstream stages don't KeyError
                _STAGE_DEFAULTS: dict[str, dict[str, Any]] = {
                    "intelligence": {"paper_intelligences": [], "research_landscape": None, "text_chunks": []},
                    "cartography": {"research_space_map": None, "gap_analyses": []},
                    "generation": {"hypothesis_pool": [], "idea_tree": None},
                    "tribunal": {"tribunal_verdicts": {}, "refined_hypotheses": state.get("hypothesis_pool", []), "refinement_cycle": 0, "idea_tree": state.get("idea_tree")},
                    "evaluation": {"panel_scores": {}, "ranked_hypotheses": state.get("refined_hypotheses", []), "controversy_scores": {}},
                    "portfolio": {"research_portfolio": None},
                    "output": {"final_output": None},
                }
                defaults = _STAGE_DEFAULTS.get(stage_name, {})
                for key, default_val in defaults.items():
                    if key not in state:
                        state[key] = default_val

                return state

            except Exception as e:
                elapsed = time.monotonic() - start
                logger.error("pipeline.stage_failed", stage=stage_name, error=str(e), elapsed=f"{elapsed:.1f}s")
                errors = state.get("errors", [])
                errors.append(StageError(stage=stage_name, message=str(e), recoverable=False))
                state["errors"] = errors
                raise

        return _wrapped

    @staticmethod
    def _build_checkpoint_data(stage_name: str, state: dict[str, Any]) -> dict[str, Any]:
        """Build human-readable checkpoint summary for the given stage."""
        if stage_name == "intelligence":
            intelligences = state.get("paper_intelligences", [])
            landscape = state.get("research_landscape")
            return {
                "summary": f"Analyzed {len(intelligences)} paper(s)",
                "papers": [pi.title for pi in intelligences] if intelligences else [],
                "open_problems": landscape.open_problems[:3] if landscape else [],
                "shared_assumptions": landscape.shared_assumptions[:3] if landscape else [],
            }
        elif stage_name == "cartography":
            space_map = state.get("research_space_map")
            n_gaps = len(space_map.all_gaps) if space_map else 0
            return {
                "summary": f"Identified {n_gaps} research gaps",
                "high_value_targets": space_map.high_value_targets[:5] if space_map else [],
            }
        elif stage_name == "generation":
            pool = state.get("hypothesis_pool", [])
            strategies = {}
            for h in pool:
                s = h.generation_strategy or "unknown"
                strategies[s] = strategies.get(s, 0) + 1
            return {
                "summary": f"Generated {len(pool)} hypotheses across {len(strategies)} strategies",
                "strategy_counts": strategies,
                "hypothesis_titles": [h.title for h in pool[:10]],
            }
        return {"summary": f"Stage {stage_name} complete"}

    def _build_memory_context(self, config: PipelineConfig) -> MemoryContext | None:
        """Retrieve memory context for conditioning the pipeline."""
        if self._memory_store.size == 0:
            return None

        query = config.domain or "research"
        domain_tags = [config.domain] if config.domain and config.domain != "other" else None
        ctx = self._memory_store.build_memory_context(query, domain_tags)

        if ctx["blocking_text"] or ctx["building_text"]:
            logger.info(
                "pipeline.memory_loaded",
                blocking_entries=ctx["blocking_text"].count("\n") if ctx["blocking_text"] else 0,
                building_entries=ctx["building_text"].count("\n") if ctx["building_text"] else 0,
            )
            return MemoryContext(
                blocking_text=ctx["blocking_text"],
                building_text=ctx["building_text"],
            )
        return None

    async def generate(
        self,
        request: GenerateRequest,
        progress_callback: Callable | None = None,
    ) -> GeneratorOutput:
        """Run the full pipeline and return the final output."""
        session_id = uuid.uuid4().hex[:12]

        # Build memory context from previous sessions
        memory_context = self._build_memory_context(request.config)

        initial_state = {
            "arxiv_id": request.arxiv_id,
            "pdf_path": request.pdf_path,
            "arxiv_ids": request.arxiv_ids,
            "config": request.config,
            "progress_callback": progress_callback,
            "session_id": session_id,
            "memory_store": self._memory_store,
            "memory_context": memory_context,
            "errors": [],
        }

        logger.info(
            "pipeline.start",
            session_id=session_id,
            arxiv_id=request.arxiv_id,
            n_arxiv_ids=len(request.arxiv_ids),
            has_memory=memory_context is not None,
        )

        start = time.monotonic()
        final_state = await self._graph.ainvoke(initial_state)
        elapsed = time.monotonic() - start

        logger.info(
            "pipeline.complete",
            session_id=session_id,
            elapsed=f"{elapsed:.1f}s",
            token_usage=self._llm.token_usage.model_dump(),
            errors=len(final_state.get("errors", [])),
            memory_entries=self._memory_store.size,
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
            "memory_entries": self._memory_store.size,
        }
