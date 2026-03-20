from __future__ import annotations

import asyncio
import re

import structlog

from hypo_gpt.config import settings
from shared.external import OpenAIWebSearchClient, SemanticScholarClient, WebSearchClient
from shared.external.types import PaperMetadata, WebSearchResult

logger = structlog.get_logger(__name__)

ACADEMIC_WEB_DOMAINS = [
    "arxiv.org",
    "openreview.net",
    "aclanthology.org",
    "proceedings.mlr.press",
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "nature.com",
    "science.org",
]

_STOPWORDS = {
    "paper",
    "domain",
    "known",
    "limitations",
    "objective",
    "task",
    "generate",
    "specific",
    "testable",
    "non",
    "generic",
    "hypotheses",
    "research",
    "under",
    "with",
    "this",
    "that",
}


def _focus_terms(text: str, limit: int = 4) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{4,}", (text or "").lower())
    out: list[str] = []
    for token in tokens:
        if token in _STOPWORDS:
            continue
        if token.startswith("vreda_hyp"):
            continue
        if re.search(r"[0-9a-f]{8,}", token):
            continue
        if token in out:
            continue
        out.append(token)
        if len(out) >= limit:
            break
    return out


def _title_key(title: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def _looks_like_temp_title(title: str) -> bool:
    lowered = title.lower()
    if lowered.startswith("vreda_hyp_"):
        return True
    if re.search(r"[0-9a-f]{24,}", lowered):
        return True
    if len(lowered) > 90 and "_" in lowered:
        return True
    return False


def _extract_title_from_intent(research_intent: str) -> str | None:
    match = re.search(r"paper:\s*([^|]+)", research_intent or "", flags=re.IGNORECASE)
    if not match:
        return None
    title = " ".join(match.group(1).split()).strip()
    if len(title) < 6 or _looks_like_temp_title(title):
        return None
    return title


class ExternalGrounder:
    def __init__(self) -> None:
        self.semantic = SemanticScholarClient()
        self.tavily = WebSearchClient()
        self.openai_web = OpenAIWebSearchClient(
            api_key=settings.openai.api_key,
            base_url=settings.openai.base_url,
            model=settings.openai.websearch_model or settings.openai.model,
            timeout_s=settings.openai.websearch_timeout_s,
            context_size=settings.openai.websearch_context_size,
            max_results=settings.openai.websearch_max_results,
        )

    @property
    def has_any_provider(self) -> bool:
        return bool(self.tavily.is_configured or self.openai_web.is_configured)

    async def gather_documents(
        self,
        *,
        primary_title: str,
        research_intent: str,
        domain: str,
        arxiv_id: str | None = None,
    ) -> list[tuple[str, str, int | None]]:
        if not settings.runtime.enable_external_grounding:
            return []

        inferred_title = _extract_title_from_intent(research_intent)
        normalized_title = inferred_title or primary_title
        if _looks_like_temp_title(normalized_title):
            normalized_title = "uploaded research paper"

        queries = self._build_queries(primary_title=normalized_title, research_intent=research_intent, domain=domain)
        tasks: list[asyncio.Future] = []

        tasks.append(asyncio.ensure_future(self.semantic.keyword_search(normalized_title, limit=6)))
        if arxiv_id:
            tasks.append(asyncio.ensure_future(self.semantic.fetch_related(arxiv_id, limit=10)))
        else:
            tasks.append(asyncio.ensure_future(self.semantic.fetch_related(normalized_title, limit=10)))

        if self.tavily.is_configured:
            for idx, query in enumerate(queries):
                allowed = ACADEMIC_WEB_DOMAINS if idx < 2 else None
                tasks.append(asyncio.ensure_future(self.tavily.search(query, max_results=3, allowed_domains=allowed)))

        if self.openai_web.is_configured:
            for idx, query in enumerate(queries):
                allowed = ACADEMIC_WEB_DOMAINS if idx < 2 else None
                tasks.append(
                    asyncio.ensure_future(
                        self.openai_web.search(query, max_results=min(3, settings.openai.websearch_max_results), allowed_domains=allowed)
                    )
                )

        if not tasks:
            return []

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=float(settings.runtime.external_grounding_timeout_s),
            )
        except TimeoutError:
            logger.warning(
                "hypo_gpt.layer0.external_grounding_timeout",
                timeout_s=settings.runtime.external_grounding_timeout_s,
                query_count=len(queries),
            )
            return []

        papers: list[PaperMetadata] = []
        web_hits: list[WebSearchResult] = []
        for result in results:
            if isinstance(result, Exception):
                logger.debug("hypo_gpt.layer0.external_grounding_query_failed", error=str(result))
                continue
            if not isinstance(result, list):
                continue
            for item in result:
                if isinstance(item, PaperMetadata):
                    papers.append(item)
                elif isinstance(item, WebSearchResult):
                    web_hits.append(item)

        documents: list[tuple[str, str, int | None]] = []
        seen: set[str] = set()

        for paper in papers:
            title = (paper.title or "").strip()
            abstract = (paper.abstract or "").strip()
            if not title or not abstract:
                continue
            key = _title_key(title)
            if not key or key in seen:
                continue
            seen.add(key)
            snippet = f"{abstract} Citation_count={paper.citation_count}. Venue={paper.venue or 'unknown'}."
            documents.append((title, snippet[:1600], paper.year))
            if len(documents) >= settings.runtime.external_grounding_max_docs:
                break

        for hit in web_hits:
            if len(documents) >= settings.runtime.external_grounding_max_docs:
                break
            title = (hit.title or "").strip()
            content = (hit.content or "").strip()
            if not title or not content:
                continue
            key = _title_key(title)
            if not key or key in seen:
                continue
            seen.add(key)
            content_text = f"{content} Source={hit.url or 'web'}"
            documents.append((title, content_text[:1400], None))

        logger.info(
            "hypo_gpt.layer0.external_grounding_complete",
            normalized_title=normalized_title,
            queries=len(queries),
            papers=len(papers),
            web_hits=len(web_hits),
            documents=len(documents),
            tavily=self.tavily.is_configured,
            openai_web_search=self.openai_web.is_configured,
        )
        return documents

    @staticmethod
    def _build_queries(*, primary_title: str, research_intent: str, domain: str) -> list[str]:
        focus = _focus_terms(research_intent, limit=4)
        focus_suffix = " ".join(focus)
        primary = primary_title if primary_title and primary_title != "uploaded research paper" else f"{domain} research paper"
        queries = [
            f"{primary} related work 2024 2025",
            f"{primary} limitations failure mode analysis",
            f"{domain} distribution shift robustness benchmark",
        ]
        if focus_suffix:
            queries.append(f"{focus_suffix} ablation benchmark comparison")
        deduped: list[str] = []
        seen: set[str] = set()
        for query in queries:
            cleaned = " ".join(query.split())
            if cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            deduped.append(cleaned)
        return deduped[:4]

    async def close(self) -> None:
        await asyncio.gather(
            self.semantic.close(),
            self.tavily.close(),
            self.openai_web.close(),
            return_exceptions=True,
        )
