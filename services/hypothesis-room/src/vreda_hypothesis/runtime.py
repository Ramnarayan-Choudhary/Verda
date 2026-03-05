"""Shared runtime dependencies injected into pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass

from vreda_hypothesis.external import (
    ArxivClient,
    OpenAIWebSearchClient,
    PapersWithCodeClient,
    SemanticScholarClient,
    TavilySearchClient,
)
from vreda_hypothesis.knowledge import VectorStoreClient
from vreda_hypothesis.llm import LLMProvider


@dataclass
class PipelineRuntime:
    llm: LLMProvider
    arxiv: ArxivClient
    semantic_scholar: SemanticScholarClient
    paperswithcode: PapersWithCodeClient
    vector_store: VectorStoreClient
    tavily: TavilySearchClient | None = None
    openai_web_search: OpenAIWebSearchClient | None = None
