"""Standalone layered hypothesis pipeline for the GPT engine."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import structlog

from hypo_gpt.layer6_memory.memory_agent import memory_agent
from hypo_gpt.layers import (
    run_layer0,
    run_layer1,
    run_layer2,
    run_layer3,
    run_layer4,
    run_layer5,
    to_generator_output,
    to_generator_output_v2,
)
from hypo_gpt.models import GenerateRequest, GeneratorOutput, GeneratorOutputV2, InputDocument, PipelineState, ProgressEvent

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[ProgressEvent], None]


class HypothesisPipeline:
    def __init__(self, progress_callback: ProgressCallback | None = None) -> None:
        self.progress_callback = progress_callback
        self.total_steps = 8

    def _emit(self, event_type: str, step: str, message: str, current: int, data: dict | None = None) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            ProgressEvent(
                type=event_type,
                step=step,
                message=message,
                current=current,
                total=self.total_steps,
                data=data,
            )
        )

    @staticmethod
    def _normalize_documents(req: GenerateRequest) -> list[InputDocument]:
        if req.input_documents:
            return req.input_documents

        docs: list[InputDocument] = []
        if req.arxiv_id:
            docs.append(InputDocument(type="arxiv", arxiv_id=req.arxiv_id, title=req.arxiv_id))
        if req.pdf_path:
            docs.append(InputDocument(type="pdf", pdf_path=req.pdf_path))
        return docs

    async def run(self, req: GenerateRequest) -> GeneratorOutput | GeneratorOutputV2:
        input_docs = self._normalize_documents(req)
        if not input_docs:
            raise ValueError("Provide arxiv_id, pdf_path, or input_documents")
        use_v2 = req.config.pipeline_version == "v2"
        self.total_steps = 8 if use_v2 else 6
        step_layer2 = 4 if use_v2 else 3
        step_layer3 = step_layer2 + 1
        step_layer4 = step_layer3 + 1
        step_layer5 = step_layer4 + 1
        step_memory_store = step_layer5 + 1

        state = PipelineState(
            research_intent=req.research_intent or "Generate state-of-the-art research hypotheses",
            input_documents=input_docs,
            config=req.config,
        )

        self._emit("progress", "Layer 0", "Multi-document intelligence started", 1)
        state = await run_layer0(state)
        self._emit("progress", "Layer 0", "Multi-document intelligence complete", 1)

        self._emit("progress", "Layer 1", "Research space cartography started", 2)
        state = await run_layer1(state)
        self._emit("progress", "Layer 1", "Research space cartography complete", 2)

        if use_v2 and req.config.enable_memory:
            self._emit("progress", "Layer 6", "Memory retrieval started", 3)
            domain_tags = []
            if state.research_landscape is not None:
                domain_tags = [state.research_landscape.intent_domain, state.research_landscape.intent_subdomain]
            context, negatives, positives = memory_agent.retrieve_context(state.research_intent, domain_tags)
            state.memory_context = context
            state.memory_entries = negatives
            self._emit(
                "progress",
                "Layer 6",
                "Memory retrieval complete",
                3,
                data={"negatives": len(negatives), "positives": len(positives)},
            )

        self._emit("progress", "Layer 2", "MCGS strategic generation started", step_layer2)
        state = await run_layer2(state)
        self._emit("progress", "Layer 2", "MCGS strategic generation complete", step_layer2)

        self._emit("progress", "Layer 3", "5-critic tribunal started", step_layer3)
        state = await run_layer3(state)
        self._emit("progress", "Layer 3", "5-critic tribunal complete", step_layer3)

        self._emit("progress", "Layer 4", "3-judge panel started", step_layer4)
        state = await run_layer4(state)
        self._emit("progress", "Layer 4", "3-judge panel complete", step_layer4)

        self._emit("progress", "Layer 5", "Portfolio constructor started", step_layer5)
        state = await run_layer5(state)
        self._emit("progress", "Layer 5", "Portfolio constructor complete", step_layer5)

        if use_v2 and req.config.enable_memory and state.final_portfolio_v2:
            self._emit("progress", "Layer 6", "Memory store started", step_memory_store)
            session_id = req.session_id or f"session-{uuid.uuid4().hex[:10]}"
            domain_tags = []
            if state.research_landscape is not None:
                domain_tags = [state.research_landscape.intent_domain, state.research_landscape.intent_subdomain]

            text_by_id = {
                item.hypo_id: (
                    f"{item.title}. {item.core_claim}. "
                    f"Mechanism: {item.causal_chain.intermediate}. "
                    f"Outcome: {item.causal_chain.outcome}. "
                    f"Falsification: {item.falsification_criterion}"
                )
                for item in state.refined_hypotheses_v2
            }
            strategy_by_id = {item.hypo_id: item.strategy for item in state.refined_hypotheses_v2}
            selected_ids = {item.hypo_id for item in state.final_portfolio_v2}
            stored = memory_agent.store_panel_outcomes(
                session_id=session_id,
                domain_tags=domain_tags,
                verdicts=list(state.panel_verdicts.values()),
                selected_hypo_ids=selected_ids,
                hypothesis_text_by_id=text_by_id,
                strategy_by_id=strategy_by_id,
            )
            state.memory_entries.extend(stored)
            self._emit("progress", "Layer 6", "Memory store complete", step_memory_store, data={"stored": len(stored)})

        if use_v2 and req.config.output_schema == "v2":
            output_v2 = to_generator_output_v2(state)
            self._emit("complete", "pipeline", "GPT hypothesis pipeline complete", self.total_steps, data={"output": output_v2.model_dump()})
            logger.info("hypo_gpt.pipeline.complete.v2", hypotheses=len(output_v2.hypotheses))
            return output_v2

        output = to_generator_output(state)
        self._emit("complete", "pipeline", "GPT hypothesis pipeline complete", self.total_steps, data={"output": output.model_dump()})
        logger.info("hypo_gpt.pipeline.complete", hypotheses=len(output.hypotheses))
        return output
