"""Standalone FastAPI server for GPT hypothesis engine."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import AsyncIterator

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from hypo_gpt.config import settings
from hypo_gpt.llm import LLMProvider
from hypo_gpt.models import GenerateRequest, ProgressEvent
from hypo_gpt.pipeline import HypothesisPipeline

logger = structlog.get_logger(__name__)
SERVER_STARTED_AT_EPOCH_S = time.time()

app = FastAPI(
    title="VREDA Hypothesis GPT API",
    version="0.1.0",
    description="Standalone GPT hypothesis engine with 6-layer architecture.",
)


@app.get("/healthz")
async def healthcheck() -> dict:
    llm = LLMProvider()
    return {
        "status": "ok",
        "engine": "gpt",
        "active_providers": llm.get_active_provider(),
        "runtime": {
            "module_file": str(Path(__file__).resolve()),
            "cwd": os.getcwd(),
            "pid": os.getpid(),
            "started_at_epoch_s": SERVER_STARTED_AT_EPOCH_S,
            "health_protocol_version": 3,
        },
    }


@app.post("/generate")
async def generate_endpoint(request: GenerateRequest) -> StreamingResponse:
    if not request.input_documents and not request.arxiv_id and not request.pdf_path:
        raise HTTPException(status_code=400, detail="Provide input_documents, arxiv_id, or pdf_path.")

    queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()

    def _progress(event: ProgressEvent) -> None:
        queue.put_nowait(event)

    async def _runner() -> None:
        pipeline = HypothesisPipeline(progress_callback=_progress)
        try:
            await pipeline.run(request)
        except Exception as exc:
            logger.exception("hypo_gpt.pipeline_failed", error=str(exc))
            queue.put_nowait(ProgressEvent(type="error", step="pipeline", message=str(exc)))
        finally:
            queue.put_nowait(None)

    asyncio.create_task(_runner())

    async def event_stream() -> AsyncIterator[bytes]:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield (event.model_dump_json() + "\n").encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def main() -> None:
    uvicorn.run("hypo_gpt.server:app", host=settings.server.host, port=settings.server.port, reload=False)


if __name__ == "__main__":
    main()
