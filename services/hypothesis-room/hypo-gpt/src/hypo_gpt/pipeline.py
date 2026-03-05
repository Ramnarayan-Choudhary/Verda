"""Standalone 6-layer hypothesis pipeline for the GPT engine."""

from __future__ import annotations

from collections.abc import Callable

import structlog

from hypo_gpt.layers import (
    run_layer0,
    run_layer1,
    run_layer2,
    run_layer3,
    run_layer4,
    run_layer5,
    to_generator_output,
)
from hypo_gpt.models import GenerateRequest, GeneratorOutput, InputDocument, PipelineState, ProgressEvent

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[ProgressEvent], None]


class HypothesisPipeline:
    def __init__(self, progress_callback: ProgressCallback | None = None) -> None:
        self.progress_callback = progress_callback
        self.total_steps = 6

    def _emit(self, event_type: str, step: str, message: str, current: int, data: dict | None = None) -> None:
        if not self.progress_callback:
            return
        self.progress_callback(
            ProgressEvent(
                type=event_type, step=step, message=message, current=current, total=self.total_steps, data=data
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

    async def run(self, req: GenerateRequest) -> GeneratorOutput:
        input_docs = self._normalize_documents(req)
        if not input_docs:
            raise ValueError("Provide arxiv_id, pdf_path, or input_documents")

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

        self._emit("progress", "Layer 2", "Multi-strategy generation started", 3)
        state = await run_layer2(state)
        self._emit("progress", "Layer 2", "Multi-strategy generation complete", 3)

        self._emit("progress", "Layer 3", "Adversarial tribunal started", 4)
        state = await run_layer3(state)
        self._emit("progress", "Layer 3", "Adversarial tribunal complete", 4)

        self._emit("progress", "Layer 4", "Panel evaluation started", 5)
        state = await run_layer4(state)
        self._emit("progress", "Layer 4", "Panel evaluation complete", 5)

        self._emit("progress", "Layer 5", "Portfolio construction started", 6)
        state = await run_layer5(state)
        self._emit("progress", "Layer 5", "Portfolio construction complete", 6)

        output = to_generator_output(state)
        self._emit("complete", "pipeline", "GPT hypothesis pipeline complete", self.total_steps, data={"output": output.model_dump()})
        logger.info("hypo_gpt.pipeline.complete", hypotheses=len(output.hypotheses))
        return output
