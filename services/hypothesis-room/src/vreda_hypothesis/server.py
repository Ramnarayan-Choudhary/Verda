"""FastAPI server exposing the hypothesis pipeline."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import structlog
import uvicorn

from vreda_hypothesis.config import settings
from vreda_hypothesis.llm import LLMProvider
from vreda_hypothesis.main import DEFAULT_STAGE_TIMEOUTS, generate_hypotheses
from vreda_hypothesis.models import GenerateRequest, ProgressEvent

logger = structlog.get_logger(__name__)
SERVER_STARTED_AT_EPOCH_S = time.time()
HEALTH_PROTOCOL_VERSION = 2

app = FastAPI(
    title="VREDA Hypothesis API",
    version="0.1.0",
    description="Multi-agent hypothesis generation pipeline (LangGraph).",
)


@app.get("/healthz")
async def healthcheck() -> dict:
    try:
        llm = LLMProvider()
        providers = llm.get_active_providers()
    except Exception:
        providers = {"error": "LLM provider initialization failed"}
    module_file = Path(__file__).resolve()
    return {
        "status": "ok",
        "active_providers": providers,
        "runtime": {
            "module_file": str(module_file),
            "cwd": os.getcwd(),
            "pythonpath": os.environ.get("PYTHONPATH", ""),
            "pid": os.getpid(),
            "started_at_epoch_s": SERVER_STARTED_AT_EPOCH_S,
            "health_protocol_version": HEALTH_PROTOCOL_VERSION,
            "llm_request_timeout_s": settings.llm.request_timeout_s,
            "llm_max_retries": settings.llm.max_retries,
            "default_stage_timeouts_s": DEFAULT_STAGE_TIMEOUTS,
        },
    }


@app.post("/generate")
async def generate_endpoint(request: GenerateRequest) -> StreamingResponse:
    if not request.arxiv_id and not request.pdf_path:
        raise HTTPException(status_code=400, detail="Provide arxiv_id or pdf_path.")

    queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()

    def _progress(event: ProgressEvent) -> None:
        queue.put_nowait(event)

    async def _runner() -> None:
        try:
            output = await generate_hypotheses(
                arxiv_id=request.arxiv_id,
                pdf_path=request.pdf_path,
                config=request.config,
                progress_callback=_progress,
            )
            queue.put_nowait(
                ProgressEvent(
                    type="complete",
                    step="pipeline",
                    message="Pipeline complete",
                    data={"output": output.model_dump()},
                )
            )
        except Exception as exc:  # pragma: no cover
            logger.exception("server.pipeline_failed", error=str(exc))
            queue.put_nowait(
                ProgressEvent(
                    type="error",
                    step="pipeline",
                    message=str(exc),
                )
            )
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
    """Entrypoint for `python -m vreda_hypothesis.server`."""
    uvicorn.run("vreda_hypothesis.server:app", host=settings.server.host, port=settings.server.port, reload=False)


if __name__ == "__main__":
    main()
