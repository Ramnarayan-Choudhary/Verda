"""Deep Research Agent — SciSpace-inspired iterative search-read-refine loop.

Iteratively searches for related literature, extracts intelligence from new papers,
updates the research landscape, and refines search queries based on identified gaps.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import structlog

from hypo_claude.agents.extractor import LandscapeSynthesizer, PaperIntelligenceExtractor
from hypo_claude.llm.provider import AgentRole, LLMProvider
from hypo_claude.models import (
    PaperIntelligence,
    ProgressEvent,
    ResearchLandscape,
)

logger = structlog.get_logger(__name__)

ProgressCallback = Callable[[ProgressEvent], None] | None


_QUERY_GENERATION_PROMPT = """\
You are a research librarian generating targeted search queries to find papers
that fill gaps in the current research landscape.

Given the current research landscape analysis and the gaps identified,
generate 3-5 specific search queries that would find papers addressing these gaps.

RULES:
1. Each query should target a SPECIFIC gap or contested claim
2. Use technical terminology from the domain (not general language)
3. Include key method names, dataset names, or technique names
4. Vary query specificity: some broad (find survey/review papers), some narrow (find specific results)
5. Avoid queries that would return the same papers we already have

Return valid JSON: {"queries": ["query 1", "query 2", ...]}"""


class DeepResearchAgent:
    """Iterative search-read-refine agent for comprehensive literature coverage.

    Implements a multi-round loop:
    1. Extract intelligence from initial papers
    2. Synthesize landscape and identify gaps
    3. Generate targeted search queries from gaps
    4. Fetch new papers via Semantic Scholar / arXiv
    5. Extract intelligence from new papers
    6. Update landscape with new evidence
    7. Repeat for N rounds
    """

    def __init__(
        self,
        llm: LLMProvider,
        extractor: PaperIntelligenceExtractor,
        synthesizer: LandscapeSynthesizer,
        progress_callback: ProgressCallback = None,
    ) -> None:
        self._llm = llm
        self._extractor = extractor
        self._synthesizer = synthesizer
        self._progress = progress_callback

    def _emit(self, message: str, current: int, total: int) -> None:
        if self._progress:
            self._progress(ProgressEvent(
                type="progress",
                step="deep_research",
                message=message,
                current=current,
                total=total,
            ))

    async def run(
        self,
        initial_intelligences: list[PaperIntelligence],
        initial_landscape: ResearchLandscape,
        *,
        rounds: int = 3,
        max_papers_per_round: int = 10,
        follow_citations: bool = True,
        domain: str = "",
    ) -> tuple[list[PaperIntelligence], ResearchLandscape]:
        """Run the iterative deep research loop.

        Returns:
            Updated (paper_intelligences, research_landscape) with new papers integrated.
        """
        all_intelligences = list(initial_intelligences)
        landscape = initial_landscape
        seen_titles: set[str] = {pi.title.lower().strip() for pi in all_intelligences}
        tried_queries: set[str] = set()

        for round_num in range(rounds):
            self._emit(
                f"Deep research round {round_num + 1}/{rounds}: generating search queries...",
                current=round_num, total=rounds,
            )

            # Step 1: Generate targeted search queries from gaps
            queries = await self._generate_queries(landscape, tried_queries)
            if not queries:
                logger.info("deep_research.no_new_queries", round=round_num + 1)
                break
            tried_queries.update(queries)

            # Step 2: Search for papers
            self._emit(
                f"Deep research round {round_num + 1}/{rounds}: searching {len(queries)} queries...",
                current=round_num, total=rounds,
            )
            new_papers = await self._search_papers(
                queries,
                seen_titles=seen_titles,
                max_papers=max_papers_per_round,
                follow_citations=follow_citations,
                seed_identifiers=[pi.paper_id for pi in initial_intelligences if pi.paper_id],
            )

            if not new_papers:
                logger.info("deep_research.no_new_papers", round=round_num + 1)
                break

            # Step 3: Extract intelligence from new papers
            self._emit(
                f"Deep research round {round_num + 1}/{rounds}: analyzing {len(new_papers)} new papers...",
                current=round_num, total=rounds,
            )
            new_intelligences = await self._extract_from_papers(new_papers, domain=domain)

            # Step 4: Update tracking
            for pi in new_intelligences:
                title_key = pi.title.lower().strip()
                if title_key not in seen_titles:
                    seen_titles.add(title_key)
                    all_intelligences.append(pi)

            # Step 5: Re-synthesize landscape with all evidence
            self._emit(
                f"Deep research round {round_num + 1}/{rounds}: updating landscape with {len(all_intelligences)} papers...",
                current=round_num, total=rounds,
            )
            landscape = await self._synthesizer.synthesize(all_intelligences, domain=domain)

            logger.info(
                "deep_research.round_complete",
                round=round_num + 1,
                new_papers=len(new_intelligences),
                total_papers=len(all_intelligences),
            )

        logger.info(
            "deep_research.complete",
            rounds_executed=min(rounds, len(tried_queries)),
            total_papers=len(all_intelligences),
            initial_papers=len(initial_intelligences),
            new_papers=len(all_intelligences) - len(initial_intelligences),
        )
        return all_intelligences, landscape

    async def _generate_queries(
        self, landscape: ResearchLandscape, tried_queries: set[str]
    ) -> list[str]:
        """Generate search queries from landscape gaps using LLM."""
        landscape_summary = json.dumps({
            "research_intent": landscape.research_intent,
            "open_problems": landscape.open_problems[:5],
            "methodological_gaps": landscape.methodological_gaps[:3],
            "bottleneck_hypothesis": landscape.bottleneck_hypothesis,
            "contested_claims": [
                {"claim": c.claim, "nature": c.nature}
                for c in landscape.contested_claims[:3]
            ],
        }, indent=1)

        tried_list = "\n".join(f"- {q}" for q in sorted(tried_queries)[:20])
        user_prompt = f"""\
CURRENT LANDSCAPE:
{landscape_summary}

ALREADY TRIED QUERIES (do NOT repeat these):
{tried_list if tried_list else "(none yet)"}

Generate 3-5 NEW targeted search queries."""

        try:
            raw = await self._llm.generate(
                _QUERY_GENERATION_PROMPT, user_prompt,
                temperature=0.4, role=AgentRole.PAPER_EXTRACTOR,
            )
            parsed = json.loads(raw) if isinstance(raw, str) else {}
            queries = parsed.get("queries", [])
            # Filter out already-tried queries
            return [q for q in queries if q.lower().strip() not in {t.lower() for t in tried_queries}][:5]
        except Exception as exc:
            logger.warning("deep_research.query_gen_failed", error=str(exc)[:200])
            return []

    async def _search_papers(
        self,
        queries: list[str],
        *,
        seen_titles: set[str],
        max_papers: int = 10,
        follow_citations: bool = True,
        seed_identifiers: list[str] | None = None,
    ) -> list[dict]:
        """Search for papers via Semantic Scholar, deduplicated against seen titles."""
        try:
            from shared.external import SemanticScholarClient, CitationNetworkExplorer
        except ImportError:
            logger.warning("deep_research.import_failed", msg="shared.external not available")
            return []

        s2 = SemanticScholarClient()
        papers: dict[str, dict] = {}

        try:
            # Keyword search for each query
            search_tasks = [s2.keyword_search(q, limit=5) for q in queries]
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue
                for paper in result:
                    title_key = paper.title.lower().strip()
                    if title_key not in seen_titles and title_key != "unknown":
                        papers[title_key] = {
                            "title": paper.title,
                            "abstract": paper.abstract or "",
                            "arxiv_id": paper.arxiv_id,
                            "year": paper.year,
                        }

            # Citation network exploration
            if follow_citations and seed_identifiers:
                explorer = CitationNetworkExplorer(s2)
                cited_papers = await explorer.explore(
                    seed_identifiers[:3],
                    max_per_seed=10,
                    follow_second_degree=False,
                )
                for paper in cited_papers:
                    title_key = paper.title.lower().strip()
                    if title_key not in seen_titles and title_key != "unknown" and title_key not in papers:
                        papers[title_key] = {
                            "title": paper.title,
                            "abstract": paper.abstract or "",
                            "arxiv_id": paper.arxiv_id,
                            "year": paper.year,
                        }

        except Exception as exc:
            logger.warning("deep_research.search_failed", error=str(exc)[:200])
        finally:
            await s2.close()

        # Return top papers (prioritize those with abstracts)
        sorted_papers = sorted(
            papers.values(),
            key=lambda p: len(p.get("abstract", "")),
            reverse=True,
        )
        return sorted_papers[:max_papers]

    async def _extract_from_papers(
        self, papers: list[dict], domain: str = ""
    ) -> list[PaperIntelligence]:
        """Extract intelligence from paper abstracts (lightweight extraction for deep research)."""
        intelligences: list[PaperIntelligence] = []

        for paper in papers:
            text = paper.get("abstract", "")
            title = paper.get("title", "Unknown")
            if not text or len(text) < 50:
                continue

            # Use abstract + title as source text for extraction
            paper_text = f"Title: {title}\n\nAbstract: {text}"
            try:
                intel = await self._extractor.extract(paper_text, paper_id=title, domain=domain)
                intel.title = title
                intel.year = paper.get("year")
                intelligences.append(intel)
            except Exception as exc:
                logger.warning("deep_research.extract_failed", title=title[:60], error=str(exc)[:200])

        return intelligences
