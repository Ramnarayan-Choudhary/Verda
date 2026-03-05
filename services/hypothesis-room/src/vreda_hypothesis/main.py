"""LangGraph-orchestrated hypothesis generation pipeline."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from langgraph.graph import END, START, StateGraph

from vreda_hypothesis.external import (
    ArxivClient,
    OpenAIWebSearchClient,
    PapersWithCodeClient,
    SemanticScholarClient,
    TavilySearchClient,
)
from vreda_hypothesis.llm import LLMProvider
from vreda_hypothesis.models import (
    GeneratorOutput,
    PipelineConfig,
    PipelineState,
    ProgressEvent,
    StageError,
)
from vreda_hypothesis.runtime import PipelineRuntime
from vreda_hypothesis.stages import (
    filtering,
    grounding,
    ingestion,
    output,
    overgeneration,
    portfolio_audit,
    refinement,
    tournament,
)

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[ProgressEvent], None]


# Per-stage timeout defaults (seconds). Override via PipelineConfig as needed.
DEFAULT_STAGE_TIMEOUTS: dict[str, int] = {
    "ingestion": 120,        # PDF download + extraction + LLM summary + ResearchFrame
    "grounding": 210,        # External APIs + iterative gap synthesis (best-effort, degradable)
    "overgeneration": 180,   # Archetype-mapped seed generation batches
    "filtering": 120,        # Parallel LLM verifiability + concreteness checks
    "refinement": 300,       # Multi-cycle propose/critique/evolve loop
    "tournament": 120,       # Parallel pairwise judging
    "portfolio_audit": 30,   # Coverage check + redundancy detection (pure computation)
    "output": 10,            # Pure computation, no I/O
}


def resolve_stage_timeouts(config: PipelineConfig | None = None) -> dict[str, int]:
    """Merge default stage timeouts with per-request overrides."""
    resolved = dict(DEFAULT_STAGE_TIMEOUTS)
    overrides = (config.stage_timeouts_seconds if config else {}) or {}
    for stage, timeout_s in overrides.items():
        if stage in resolved:
            resolved[stage] = timeout_s
    return resolved


class HypothesisPipeline:
    """Builds and executes the 8-stage LangGraph pipeline."""

    def __init__(self, runtime: PipelineRuntime, progress_callback: ProgressCallback | None = None) -> None:
        self.runtime = runtime
        self.progress_callback = progress_callback
        self.total_steps = 8
        self.app = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(dict)

        graph.add_node("ingestion", self._wrap_stage(ingestion.run, "Paper Ingestion", 1, "ingestion"))
        graph.add_node("grounding", self._wrap_stage(grounding.run, "External Grounding", 2, "grounding"))
        graph.add_node(
            "overgeneration",
            self._wrap_stage(overgeneration.run, "Archetype Seed Generation", 3, "overgeneration"),
        )
        graph.add_node("filtering", self._wrap_stage(filtering.run, "MVE Filtering", 4, "filtering"))
        graph.add_node("refinement", self._wrap_stage(refinement.run, "Debate-Evolve Refinement", 5, "refinement"))
        graph.add_node("tournament", self._wrap_stage(tournament.run, "Tournament Ranking", 6, "tournament"))
        graph.add_node(
            "portfolio_audit",
            self._wrap_stage(portfolio_audit.run, "Portfolio Audit", 7, "portfolio_audit"),
        )
        graph.add_node("output", self._wrap_stage(output.run, "Structured Output", 8, "output"))

        graph.add_edge(START, "ingestion")
        graph.add_edge("ingestion", "grounding")
        graph.add_edge("grounding", "overgeneration")
        graph.add_edge("overgeneration", "filtering")
        graph.add_edge("filtering", "refinement")
        graph.add_edge("refinement", "tournament")
        graph.add_edge("tournament", "portfolio_audit")
        graph.add_edge("portfolio_audit", "output")
        graph.add_edge("output", END)

        return graph.compile()

    def _wrap_stage(
        self,
        stage_callable: Callable[..., Any],
        label: str,
        step_index: int,
        stage_key: str,
    ) -> Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]:
        async def _node(state_dict: dict[str, Any]) -> dict[str, Any]:
            pipeline_state = PipelineState(**state_dict)
            timeout_seconds = resolve_stage_timeouts(pipeline_state.config).get(stage_key, 120)
            self._emit_progress("progress", label, f"{label} starting...", step_index)
            try:
                needs_runtime = "runtime" in inspect.signature(stage_callable).parameters
                result = (
                    stage_callable(pipeline_state, self.runtime)
                    if needs_runtime
                    else stage_callable(pipeline_state)
                )
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout=timeout_seconds)
                self._emit_progress("progress", label, f"{label} complete", step_index)
                if pipeline_state.errors:
                    self._emit_progress("warning", label, f"{len(pipeline_state.errors)} warnings", step_index)
                return result or {}
            except TimeoutError:
                logger.error("pipeline.stage_timeout", stage=label, timeout=timeout_seconds)
                if stage_key == "grounding":
                    warning_message = (
                        f"{label} timed out after {timeout_seconds}s; "
                        "continuing with reduced grounding context"
                    )
                    pipeline_state.errors.append(StageError(stage=stage_key, message=warning_message, recoverable=True))
                    self._emit_progress("warning", label, warning_message, step_index)
                    return {"errors": pipeline_state.errors, "related_papers": [], "meta_gaps": []}
                self._emit_progress("error", label, f"{label} timed out after {timeout_seconds}s", step_index)
                raise RuntimeError(f"Stage '{label}' timed out after {timeout_seconds} seconds")
            except Exception as exc:
                logger.exception("pipeline.stage_failed", stage=label, error=str(exc))
                self._emit_progress("error", label, str(exc), step_index)
                raise

        return _node

    def _emit_progress(self, event_type: str, step: str, message: str, current: int) -> None:
        if not self.progress_callback:
            return
        event = ProgressEvent(
            type=event_type,
            step=step,
            message=message,
            current=current,
            total=self.total_steps,
        )
        try:
            self.progress_callback(event)
        except Exception as exc:  # pragma: no cover
            logger.warning("progress.emit_failed", error=str(exc))

    async def run(self, initial_state: PipelineState) -> PipelineState:
        """Execute the LangGraph pipeline and return the final state."""
        state_dict = initial_state.model_dump()
        result_state = await self.app.ainvoke(state_dict)
        self._emit_progress("complete", "Pipeline", "Hypothesis generation complete", self.total_steps)
        return PipelineState(**result_state)


async def generate_hypotheses(
    arxiv_id: str | None = None,
    pdf_path: str | None = None,
    config: PipelineConfig | None = None,
    llm_provider: LLMProvider | None = None,
    progress_callback: ProgressCallback | None = None,
) -> GeneratorOutput:
    """Public entry point used by FastAPI + external integrations."""
    if not arxiv_id and not pdf_path:
        raise ValueError("generate_hypotheses requires arxiv_id or pdf_path.")

    llm = llm_provider or LLMProvider()
    vector_store = __create_vector_store()
    tavily = TavilySearchClient()
    openai_web_search = OpenAIWebSearchClient()
    runtime = PipelineRuntime(
        llm=llm,
        arxiv=ArxivClient(),
        semantic_scholar=SemanticScholarClient(),
        paperswithcode=PapersWithCodeClient(),
        vector_store=vector_store,
        tavily=tavily if tavily.is_configured else None,
        openai_web_search=openai_web_search if openai_web_search.is_configured else None,
    )

    pipeline = HypothesisPipeline(runtime, progress_callback=progress_callback)
    initial_state = PipelineState(
        arxiv_id=arxiv_id,
        pdf_path=pdf_path,
        config=config or PipelineConfig(),
        knowledge_graph=None,
        vector_store_client=runtime.vector_store,
        progress_callback=progress_callback,
    )

    final_state = await pipeline.run(initial_state)
    final_state.token_usage = llm.token_usage

    logger.info(
        "pipeline.token_usage",
        prompt_tokens=llm.token_usage.prompt_tokens,
        completion_tokens=llm.token_usage.completion_tokens,
        total_tokens=llm.token_usage.total_tokens,
        estimated_cost_usd=round(llm.token_usage.estimated_cost_usd, 4),
    )

    if not final_state.final_output or not final_state.final_output.hypotheses:
        existing_count = len(final_state.final_output.hypotheses) if final_state.final_output else 0
        logger.warning(
            "pipeline.final_output_missing_fallback",
            has_final_output=bool(final_state.final_output),
            existing_hypotheses=existing_count,
        )
        recovered = output.run(final_state).get("final_output")
        if isinstance(recovered, GeneratorOutput) and recovered.hypotheses:
            final_state.final_output = recovered
            logger.info("pipeline.final_output_recovered", hypotheses=len(recovered.hypotheses))
        else:
            raise RuntimeError("Pipeline completed without producing hypotheses.")
    return final_state.final_output


def __create_vector_store():
    from vreda_hypothesis.knowledge import VectorStoreClient

    return VectorStoreClient()
