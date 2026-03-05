"""
FastAPI server for the hypo-claude Epistemic Engine.

Endpoints:
  GET  /healthz   — Health check + provider info
  POST /generate  — Run full pipeline with NDJSON streaming
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from hypo_claude.config import settings
from hypo_claude.models import GenerateRequest, GeneratorOutput, ProgressEvent
from hypo_claude.pipeline import EpistemicPipeline

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="VREDA Hypothesis Engine (Claude)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEALTH_PROTOCOL_VERSION = 2

# Lazy-init pipeline (expensive — creates LLM clients)
_pipeline: EpistemicPipeline | None = None


def _get_pipeline() -> EpistemicPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = EpistemicPipeline()
    return _pipeline


@app.get("/healthz")
async def healthz():
    try:
        pipeline = _get_pipeline()
        info = pipeline.get_health_info()
        return {
            "status": "ok",
            "protocol_version": HEALTH_PROTOCOL_VERSION,
            "engine": "hypo-claude",
            **info,
        }
    except Exception as e:
        return {
            "status": "error",
            "protocol_version": HEALTH_PROTOCOL_VERSION,
            "engine": "hypo-claude",
            "error": str(e),
        }


@app.post("/generate")
async def generate(request: GenerateRequest):
    """Run the epistemic pipeline with NDJSON streaming progress."""

    if not request.arxiv_id and not request.arxiv_ids and not request.pdf_path:
        raise HTTPException(400, "Provide arxiv_id, arxiv_ids, or pdf_path")

    pipeline = _get_pipeline()
    queue: asyncio.Queue[ProgressEvent | GeneratorOutput | None] = asyncio.Queue()

    async def progress_callback(step: str, message: str, current: int | None = None, total: int | None = None):
        event = ProgressEvent(type="progress", step=step, message=message, current=current, total=total)
        await queue.put(event)

    async def _run():
        try:
            result = await pipeline.generate(request, progress_callback=progress_callback)
            await queue.put(result)
        except Exception as e:
            logger.error("generate.failed", error=str(e))
            await queue.put(ProgressEvent(type="error", message=str(e)))
        finally:
            await queue.put(None)

    async def _stream():
        task = asyncio.create_task(_run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break

                if isinstance(item, ProgressEvent):
                    yield json.dumps(item.model_dump(), default=str) + "\n"
                elif isinstance(item, GeneratorOutput):
                    final_event = ProgressEvent(
                        type="complete",
                        message="Pipeline complete",
                        data=item.model_dump(),
                    )
                    yield json.dumps(final_event.model_dump(), default=str) + "\n"
        except asyncio.CancelledError:
            task.cancel()
            raise

    return StreamingResponse(
        _stream(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff"},
    )


def main():
    """Entry point for `python -m hypo_claude.server`."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )
    logger.info("server.starting", host=settings.server.host, port=settings.server.port)
    uvicorn.run(
        "hypo_claude.server:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
