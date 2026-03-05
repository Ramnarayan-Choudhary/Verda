"""Shared typed payloads for literature providers."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperMetadata(BaseModel):
    title: str = ""
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    citation_count: int = 0
    venue: str = ""
    url: str = ""


class WebSearchResult(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    published_date: str | None = None
    source: str = ""
