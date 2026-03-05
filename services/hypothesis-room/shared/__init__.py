"""Shared utilities for VREDA hypothesis generation engines."""

from shared.cache import AsyncTTLCache, paper_cache, search_cache
from shared.dedup import cosine_similarity, deduplicate_by_cosine
from shared.pdf import chunk_text, download_arxiv_pdf, extract_text
from shared.rate_limiter import (
    AsyncRateLimiter,
    arxiv_limiter,
    paperswithcode_limiter,
    semantic_scholar_limiter,
    web_search_limiter,
)
from shared.vector_store import VectorStoreClient

__all__ = [
    "AsyncTTLCache",
    "AsyncRateLimiter",
    "VectorStoreClient",
    "download_arxiv_pdf",
    "extract_text",
    "chunk_text",
    "deduplicate_by_cosine",
    "cosine_similarity",
    "paper_cache",
    "search_cache",
    "arxiv_limiter",
    "semantic_scholar_limiter",
    "paperswithcode_limiter",
    "web_search_limiter",
]
