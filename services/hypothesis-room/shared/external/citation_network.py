"""Citation network exploration — follows citation chains for deep research.

Uses Semantic Scholar API to explore forward citations, backward references,
and second-degree connections for comprehensive literature coverage.
"""

from __future__ import annotations

import asyncio

import structlog

from shared.external.semantic_scholar import SemanticScholarClient
from shared.external.types import PaperMetadata

logger = structlog.get_logger(__name__)


class CitationNetworkExplorer:
    """Explores citation networks around seed papers for deep research."""

    def __init__(self, s2_client: SemanticScholarClient | None = None) -> None:
        self._s2 = s2_client or SemanticScholarClient()

    async def explore(
        self,
        seed_identifiers: list[str],
        *,
        max_per_seed: int = 15,
        follow_second_degree: bool = False,
        max_second_degree: int = 5,
    ) -> list[PaperMetadata]:
        """Explore citation network around seed papers.

        Returns deduplicated list of related papers from:
        1. Forward citations (papers citing the seed)
        2. Backward references (papers cited by the seed)
        3. Optionally, second-degree connections (co-cited papers)
        """
        all_papers: dict[str, PaperMetadata] = {}

        # First degree: citations + references for each seed
        tasks = [
            self._s2.fetch_related(identifier, limit=max_per_seed)
            for identifier in seed_identifiers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("citation_network.fetch_failed", error=str(result)[:200])
                continue
            for paper in result:
                key = self._paper_key(paper)
                if key and key not in all_papers:
                    all_papers[key] = paper

        # Second degree: find papers cited alongside the seeds (co-citation)
        if follow_second_degree and all_papers:
            top_cited = sorted(
                all_papers.values(),
                key=lambda p: p.citation_count or 0,
                reverse=True,
            )[:max_second_degree]

            second_tasks = []
            for paper in top_cited:
                identifier = paper.arxiv_id or paper.semantic_scholar_id or ""
                if identifier:
                    second_tasks.append(self._s2.fetch_related(identifier, limit=5))

            if second_tasks:
                second_results = await asyncio.gather(*second_tasks, return_exceptions=True)
                for result in second_results:
                    if isinstance(result, Exception):
                        continue
                    for paper in result:
                        key = self._paper_key(paper)
                        if key and key not in all_papers:
                            all_papers[key] = paper

        logger.info(
            "citation_network.explored",
            seeds=len(seed_identifiers),
            papers_found=len(all_papers),
            second_degree=follow_second_degree,
        )
        return list(all_papers.values())

    @staticmethod
    def _paper_key(paper: PaperMetadata) -> str:
        """Generate a dedup key for a paper."""
        if paper.arxiv_id:
            return f"arxiv:{paper.arxiv_id.lower()}"
        if paper.semantic_scholar_id:
            return f"s2:{paper.semantic_scholar_id.lower()}"
        if paper.title and paper.title != "Unknown":
            return f"title:{paper.title.lower().strip()}"
        return ""

    async def close(self) -> None:
        await self._s2.close()
