"""Stage 2 — External Grounding & Iterative Gap Synthesis.

Enhanced with:
1. LLM-driven targeted search (AI-Scientist-v2 pattern): LLM generates
   specific search queries based on ResearchFrame operators + gaps
2. Deep paper reading: full abstracts, not truncated
3. 3-round iterative gap validation (open_deep_research pattern)
4. Expanded literature pool: citation graph + targeted search + keyword search
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Any

import structlog
from pydantic import BaseModel, Field

from vreda_hypothesis.knowledge import PaperKnowledgeGraph
from vreda_hypothesis.llm import AgentRole
from vreda_hypothesis.llm.prompts import gap_analysis_prompts
from vreda_hypothesis.llm.prompts.gap_synthesis import (
    gap_identification_prompt,
    gap_refinement_prompt,
    gap_validation_prompt,
)
from vreda_hypothesis.llm.prompts.literature_search import search_query_generation_prompt
from vreda_hypothesis.models import (
    GapAnalysis,
    MetaGap,
    PaperMetadata,
    PipelineState,
    ProgressEvent,
    StageError,
)
from vreda_hypothesis.runtime import PipelineRuntime

logger = structlog.get_logger(__name__)

MAX_TARGETED_QUERIES = 4
MAX_RELATED_PAPERS = 20
VECTOR_ENRICH_TIMEOUT_S = 10
ITERATIVE_GAP_TIMEOUT_S = 140
GAP_ANALYSIS_TIMEOUT_S = 45
QUERY_GENERATION_TIMEOUT_S = 15
TARGETED_SEARCH_TIMEOUT_S = 20
WEB_SEARCH_TIMEOUT_S = 30

ACADEMIC_WEB_DOMAINS = [
    "arxiv.org",
    "openreview.net",
    "semanticscholar.org",
    "paperswithcode.com",
    "proceedings.neurips.cc",
    "proceedings.mlr.press",
    "aclanthology.org",
    "huggingface.co",
    "github.com",
    "ieeexplore.ieee.org",
    "dl.acm.org",
]


# LLM output schemas
class GapIdentificationOutput(BaseModel):
    gaps: list[MetaGap] = Field(default_factory=list)


class GapRefinementOutput(BaseModel):
    gaps: list[MetaGap] = Field(default_factory=list)
    landscape_summary: str = ""
    dominant_trends: list[str] = Field(default_factory=list)
    underexplored_areas: list[str] = Field(default_factory=list)
    iterations_completed: int = 3


class SearchQuery(BaseModel):
    query: str
    intent: str = "operator"


class SearchQueryBatch(BaseModel):
    queries: list[SearchQuery] = Field(default_factory=list)


def _emit_grounding_activity(state: PipelineState, message: str, data: dict[str, Any] | None = None) -> None:
    state.grounding_activity.append(message)
    callback = state.progress_callback
    if not callback:
        return
    try:
        callback(
            ProgressEvent(
                type="progress",
                step="External Grounding",
                message=message,
                data=data or {},
            )
        )
    except Exception as exc:  # pragma: no cover
        logger.debug("grounding.progress_emit_failed", error=str(exc))


async def run(state: PipelineState, runtime: PipelineRuntime) -> dict[str, Any]:
    if not state.paper_metadata or not state.paper_summary:
        return {}

    graph: PaperKnowledgeGraph = state.knowledge_graph or PaperKnowledgeGraph()

    try:
        # Use arXiv ID when available; fall back to paper title for keyword-based discovery.
        # Never pass garbage identifiers (temp file stems, UUIDs) to S2 API.
        arxiv_id = state.paper_metadata.arxiv_id or None
        paper_title = state.paper_summary.title or state.paper_metadata.title or ""

        # For fetch_related: prefer arXiv ID → fall back to paper title (triggers keyword search in S2 client)
        related_identifier = arxiv_id or paper_title

        # Phase 1: Parallel fetch — citation graph + datasets + repos
        related_task = asyncio.create_task(runtime.semantic_scholar.fetch_related(related_identifier, limit=MAX_RELATED_PAPERS))
        dataset_task = asyncio.create_task(
            runtime.paperswithcode.fetch_datasets(state.paper_summary.title or "", limit=5)
        )
        repo_task = asyncio.create_task(
            runtime.paperswithcode.fetch_repositories(state.paper_summary.title or "", limit=5)
        )

        related_papers, datasets, repos = await asyncio.gather(
            related_task, dataset_task, repo_task, return_exceptions=True
        )
        related_list: list[PaperMetadata] = []
        if isinstance(related_papers, Exception):
            logger.warning("grounding.related_failed", error=str(related_papers))
        else:
            related_list = related_papers
            for paper in related_list:
                graph.add_paper(paper, source="related")

        if isinstance(datasets, Exception):
            logger.warning("grounding.datasets_failed", error=str(datasets))
            datasets = []
        if isinstance(repos, Exception):
            logger.warning("grounding.repos_failed", error=str(repos))
            repos = []
        _emit_grounding_activity(
            state,
            f"External retrieval: papers={len(related_list)} datasets={len(datasets)} repos={len(repos)}",
            {
                "papers": len(related_list),
                "datasets": len(datasets),
                "repos": len(repos),
            },
        )

        # Phase 2: LLM-driven targeted search (AI-Scientist-v2 pattern)
        # LLM generates specific search queries based on operators, mechanisms, gaps
        try:
            targeted_papers = await asyncio.wait_for(
                _llm_driven_literature_search(state, runtime, [p.title for p in related_list]),
                timeout=TARGETED_SEARCH_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("grounding.targeted_search_timeout", timeout_seconds=TARGETED_SEARCH_TIMEOUT_S)
            state.errors.append(StageError(stage="grounding", message="Targeted Semantic Scholar search timed out"))
            targeted_papers = []
        _emit_grounding_activity(
            state,
            f"Targeted search: queries={MAX_TARGETED_QUERIES}, papers={len(targeted_papers)}",
            {
                "queries": MAX_TARGETED_QUERIES,
                "papers_found": len(targeted_papers),
            },
        )
        # Merge targeted papers with citation graph papers (dedup by title)
        seen_titles = {p.title.lower().strip() for p in related_list if p.title}
        for paper in targeted_papers:
            if paper.title and paper.title.lower().strip() not in seen_titles:
                related_list.append(paper)
                graph.add_paper(paper, source="targeted_search")
                seen_titles.add(paper.title.lower().strip())

        # Phase 2.5: Web search via Tavily (AI-Researcher HKUDS pattern)
        # Discovers papers, blog posts, and technical content that APIs miss
        web_snippets: list[str] = []
        tavily_client = getattr(runtime, "tavily", None)
        openai_web_client = getattr(runtime, "openai_web_search", None)
        if (
            (tavily_client and tavily_client.is_configured)
            or (openai_web_client and openai_web_client.is_configured)
        ):
            try:
                web_snippets = await asyncio.wait_for(
                    _web_literature_search(state, runtime, seen_titles),
                    timeout=WEB_SEARCH_TIMEOUT_S,
                )
            except TimeoutError:
                logger.warning("grounding.web_search_timeout", timeout_seconds=WEB_SEARCH_TIMEOUT_S)
                state.errors.append(StageError(stage="grounding", message="Web literature search timed out"))
                web_snippets = []
        if web_snippets:
            sample_sources = [snippet[:220] for snippet in web_snippets[:3]]
            preview = sample_sources[0][:120] if sample_sources else ""
            _emit_grounding_activity(
                state,
                f"Web search evidence collected: {len(web_snippets)} snippets. {preview}",
                {
                    "snippets_found": len(web_snippets),
                    "sample_sources": sample_sources,
                },
            )
        else:
            _emit_grounding_activity(
                state,
                "Web search evidence collected: 0 snippets",
                {"snippets_found": 0},
            )

        logger.info(
            "grounding.literature_expanded",
            citation_graph=len(related_papers) if not isinstance(related_papers, Exception) else 0,
            targeted_search=len(targeted_papers),
            web_search=len(web_snippets),
            web_provider_tavily=bool(tavily_client and tavily_client.is_configured),
            web_provider_openai=bool(openai_web_client and openai_web_client.is_configured),
            total_unique=len(related_list),
        )

        # Phase 3: Build deep snippets — full abstracts, not truncated
        snippets: list[str] = []
        for paper in related_list[:20]:  # More papers, fuller abstracts
            abstract = paper.abstract or ""
            snippet = f"{paper.title} ({paper.year}, {paper.citation_count} citations): {abstract}"
            snippets.append(snippet)

        dataset_snippets = [
            f"Dataset: {item.get('name')} — {item.get('description', '')[:200]}"
            for item in datasets
        ]
        repo_snippets = [
            f"Repo: {item.get('name')} ({item.get('framework')}) {item.get('url')}"
            for item in repos
        ]
        snippets.extend(dataset_snippets)
        snippets.extend(repo_snippets)
        snippets.extend(web_snippets)

        rag_texts: list[str] = []
        # Vector enrichment is helpful but non-essential. Keep it best-effort and bounded.
        try:
            await asyncio.wait_for(
                runtime.vector_store.add_chunks(arxiv_id or paper_title or "paper", snippets),
                timeout=VECTOR_ENRICH_TIMEOUT_S,
            )
            rag_hits = await asyncio.wait_for(
                runtime.vector_store.similarity_search(
                    state.paper_summary.abstract or state.paper_text, k=12
                ),
                timeout=VECTOR_ENRICH_TIMEOUT_S,
            )
            rag_texts = [hit.get("text", "") for hit in rag_hits if hit.get("text")]
        except Exception as exc:
            logger.warning("grounding.vector_context_failed", error=str(exc))

        if not rag_texts:
            rag_texts = snippets[:12]

        # Phase 4: Legacy gap analysis (backward compat)
        system, user = gap_analysis_prompts(state.paper_summary, related_list, rag_texts)
        try:
            gap_analysis = await asyncio.wait_for(
                runtime.llm.generate_json(
                    system, user, GapAnalysis,
                    temperature=0.35,
                    role=AgentRole.GAP_ANALYSIS,
                ),
                timeout=GAP_ANALYSIS_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("grounding.gap_analysis_timeout", timeout_seconds=GAP_ANALYSIS_TIMEOUT_S)
            state.errors.append(
                StageError(
                    stage="grounding",
                    message=f"Gap analysis timed out after {GAP_ANALYSIS_TIMEOUT_S}s",
                )
            )
            gap_analysis = GapAnalysis()
        except Exception as exc:
            logger.warning("grounding.gap_analysis_failed", error=str(exc))
            state.errors.append(
                StageError(
                    stage="grounding",
                    message=f"Gap analysis failed, continuing with empty gaps: {exc}",
                )
            )
            gap_analysis = GapAnalysis()

        # Phase 5: Iterative gap synthesis — 3 rounds
        used_heuristic_meta_gap_fallback = False
        try:
            meta_gaps = await asyncio.wait_for(
                _iterative_gap_synthesis(
                    state, runtime, related_list, rag_texts,
                    iterations=state.config.gap_synthesis_iterations,
                ),
                timeout=ITERATIVE_GAP_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("grounding.iterative_gap_timeout", timeout_seconds=ITERATIVE_GAP_TIMEOUT_S)
            state.errors.append(
                StageError(
                    stage="grounding",
                    message=f"Iterative gap synthesis timed out after {ITERATIVE_GAP_TIMEOUT_S}s",
                )
            )
            meta_gaps = []
        if not meta_gaps:
            meta_gaps = _heuristic_meta_gaps(state, related_list, rag_texts)
            if meta_gaps:
                used_heuristic_meta_gap_fallback = True
                logger.warning(
                    "grounding.meta_gap_fallback_used",
                    generated=len(meta_gaps),
                )
        _emit_grounding_activity(
            state,
            f"Gap synthesis complete: meta_gaps={len(meta_gaps)} legacy_gaps={len(gap_analysis.gaps)}",
            {
                "legacy_gap_count": len(gap_analysis.gaps),
                "meta_gap_count": len(meta_gaps),
                "used_heuristic_fallback": used_heuristic_meta_gap_fallback,
            },
        )

        logger.info(
            "stage.grounding.complete",
            related=len(related_list),
            datasets=len(datasets),
            repos=len(repos),
            legacy_gaps=len(gap_analysis.gaps),
            meta_gaps=len(meta_gaps),
        )
        return {
            "related_papers": related_list,
            "gap_analysis": gap_analysis,
            "meta_gaps": meta_gaps,
            "grounding_activity": state.grounding_activity,
            "knowledge_graph": graph,
        }

    except Exception as exc:
        logger.exception("stage.grounding.error", error=str(exc))
        state.errors.append(StageError(stage="grounding", message=str(exc)))
        return {"errors": state.errors}


async def _web_literature_search(
    state: PipelineState,
    runtime: PipelineRuntime,
    seen_titles: set[str],
) -> list[str]:
    """AI-Researcher (HKUDS) pattern: use web search providers (Tavily/OpenAI)
    to discover papers and technical content that academic APIs miss.

    Searches for: the paper's core operators in broader web context,
    related blog posts, workshop papers, and cross-domain applications.

    Returns snippets (not PaperMetadata) since web results have different structure.
    """
    assert state.paper_summary is not None

    tavily_client = getattr(runtime, "tavily", None)
    openai_web_client = getattr(runtime, "openai_web_search", None)
    tavily_enabled = bool(tavily_client and tavily_client.is_configured)
    openai_enabled = bool(openai_web_client and openai_web_client.is_configured)
    if not tavily_enabled and not openai_enabled:
        return []

    try:
        # Generate targeted web search queries.
        queries = []

        # Query 1: Core paper topic + recent work
        queries.append(f"{state.paper_summary.title} related work 2024 2025")

        # Query 2: Core operators / methods
        if state.research_frame and state.research_frame.core_operators:
            operators = " ".join(state.research_frame.core_operators[:3])
            queries.append(f"{operators} benchmark comparison results")
        elif state.paper_summary.methods:
            methods = " ".join(state.paper_summary.methods[:3])
            queries.append(f"{methods} benchmark comparison results")

        # Query 3: Limitations / gaps (broad web search)
        if state.research_frame and state.research_frame.untested_axes:
            axes = " ".join(state.research_frame.untested_axes[:3])
            queries.append(f"{state.paper_summary.domain} {axes} recent research")
        elif state.paper_summary.limitations:
            limits = " ".join(state.paper_summary.limitations[:2])
            queries.append(f"{state.paper_summary.domain} {limits[:80]} follow-up research")

        # Query 4: Cross-domain (broad search)
        if state.research_frame and state.research_frame.core_mechanism:
            queries.append(
                f"{state.research_frame.core_mechanism[:50]} alternative approaches"
            )
        elif state.paper_summary.contributions:
            queries.append(f"{state.paper_summary.contributions[0][:70]} alternative approaches")

        # Always run at least 3 queries for adequate grounding coverage.
        if len(queries) < 3:
            queries.extend(
                [
                    f"{state.paper_summary.domain} operator ablation study recent",
                    f"{state.paper_summary.title} failure mode analysis",
                ]
            )
        queries = queries[:4]

        # Execute searches in parallel across providers.
        task_specs: list[tuple[str, Awaitable[list[dict[str, Any]]]]] = []

        if tavily_enabled and tavily_client:
            paper_tasks = [tavily_client.search_papers(q, max_results=3) for q in queries[:2]]
            broad_tasks = [tavily_client.search_broad(q, max_results=3) for q in queries[2:]]
            for task in paper_tasks:
                task_specs.append(("tavily", task))
            for task in broad_tasks:
                task_specs.append(("tavily", task))

        if openai_enabled and openai_web_client:
            academic_queries = queries[:2]
            broad_queries = queries[2:]
            for query in academic_queries:
                task_specs.append(
                    (
                        "openai_web_search",
                        openai_web_client.search(
                            query,
                            max_results=3,
                            allowed_domains=ACADEMIC_WEB_DOMAINS,
                        ),
                    )
                )
            for query in broad_queries:
                task_specs.append(
                    ("openai_web_search", openai_web_client.search(query, max_results=3))
                )

        all_snippets: list[str] = []
        results = await asyncio.gather(
            *[task for _, task in task_specs], return_exceptions=True
        )

        for (provider_name, _), result in zip(task_specs, results, strict=False):
            if isinstance(result, Exception):
                logger.debug("grounding.web_search_query_failed", provider=provider_name, error=str(result))
                continue
            for item in result:
                title = item.get("title", "")
                content = item.get("content", "")
                url = item.get("url", "")

                # Skip if we already have this paper
                if title.lower().strip() in seen_titles:
                    continue

                snippet = f"[Web/{provider_name}] {title}: {content[:500]} (source: {url})"
                all_snippets.append(snippet)

        logger.info(
            "grounding.web_search_complete",
            queries=len(queries),
            providers={
                "tavily": tavily_enabled,
                "openai_web_search": openai_enabled,
            },
            snippets_found=len(all_snippets),
        )
        return all_snippets

    except Exception as exc:
        logger.warning("grounding.web_search_error", error=str(exc))
        return []


async def _llm_driven_literature_search(
    state: PipelineState,
    runtime: PipelineRuntime,
    existing_titles: list[str],
) -> list[PaperMetadata]:
    """AI-Scientist-v2 pattern: LLM generates targeted search queries,
    then we search Semantic Scholar for each query.

    This discovers papers the citation graph misses — competitors,
    cross-domain applications, alternative approaches.
    """
    assert state.paper_summary is not None

    try:
        # Step 1: LLM generates targeted search queries
        system, user = search_query_generation_prompt(
            state.paper_summary, state.research_frame, existing_titles
        )
        try:
            query_batch = await asyncio.wait_for(
                runtime.llm.generate_json(
                    system, user, SearchQueryBatch,
                    temperature=0.3,
                    role=AgentRole.GAP_ANALYSIS,
                ),
                timeout=QUERY_GENERATION_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning(
                "grounding.query_generation_timeout",
                timeout_seconds=QUERY_GENERATION_TIMEOUT_S,
            )
            return []

        queries = query_batch.queries[:MAX_TARGETED_QUERIES]
        if not queries:
            return []

        # Step 2: Execute searches in parallel (batches of 4 to respect rate limits)
        all_papers: list[PaperMetadata] = []
        seen: set[str] = set()

        for chunk_start in range(0, len(queries), 2):
            chunk = queries[chunk_start:chunk_start + 2]
            results = await asyncio.gather(
                *[
                    runtime.semantic_scholar.keyword_search(q.query, limit=5)
                    for q in chunk
                ],
                return_exceptions=True,
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(
                        "grounding.targeted_search_failed",
                        query=chunk[i].query,
                        error=str(result),
                    )
                    continue
                for paper in result:
                    key = (paper.title or "").lower().strip()
                    if key and key not in seen:
                        all_papers.append(paper)
                        seen.add(key)

        logger.info(
            "grounding.targeted_search_complete",
            queries=len(queries),
            papers_found=len(all_papers),
            intents=[q.intent for q in queries],
        )
        return all_papers

    except Exception as exc:
        logger.warning("grounding.targeted_search_error", error=str(exc))
        return []


async def _iterative_gap_synthesis(
    state: PipelineState,
    runtime: PipelineRuntime,
    related_papers: list[PaperMetadata],
    rag_texts: list[str],
    iterations: int = 3,
) -> list[MetaGap]:
    """Run 3-round iterative gap synthesis: identify → validate → refine."""
    assert state.paper_summary is not None

    try:
        # Round 1: Identify 8-10 candidate gaps
        r1_system, r1_user = gap_identification_prompt(
            state.paper_summary, state.research_frame, related_papers, rag_texts
        )
        r1_output = await runtime.llm.generate_json(
            r1_system, r1_user, GapIdentificationOutput,
            temperature=0.4,
            role=AgentRole.GAP_ANALYSIS,
        )
        candidate_gaps = r1_output.gaps
        logger.info("gap_synthesis.round1", candidates=len(candidate_gaps))

        if not candidate_gaps:
            return []

        # Round 2: Validate against literature
        r2_system, r2_user = gap_validation_prompt(candidate_gaps, related_papers, rag_texts)
        r2_output = await runtime.llm.generate_json(
            r2_system, r2_user, GapIdentificationOutput,
            temperature=0.2,
            role=AgentRole.GAP_ANALYSIS,
        )
        validated_gaps = [g for g in r2_output.gaps if not g.already_solved]
        solved_count = len(r2_output.gaps) - len(validated_gaps)
        logger.info("gap_synthesis.round2", surviving=len(validated_gaps), solved=solved_count)

        if not validated_gaps:
            return []

        # Round 3: Refine and sharpen
        r3_system, r3_user = gap_refinement_prompt(validated_gaps, state.research_frame)
        r3_output = await runtime.llm.generate_json(
            r3_system, r3_user, GapRefinementOutput,
            temperature=0.3,
            role=AgentRole.GAP_ANALYSIS,
        )
        final_gaps = [g for g in r3_output.gaps if not g.already_solved]
        logger.info("gap_synthesis.round3", final=len(final_gaps))

        return final_gaps

    except Exception as exc:
        logger.warning("gap_synthesis.failed", error=str(exc))
        state.errors.append(StageError(stage="grounding", message=f"Iterative gap synthesis failed: {exc}"))
        return []


def _heuristic_meta_gaps(
    state: PipelineState,
    related_papers: list[PaperMetadata],
    rag_texts: list[str],
) -> list[MetaGap]:
    """Generate structured meta-gaps from local paper signals when LLM/API grounding fails.

    This keeps downstream archetype seeding high-quality even under rate limits.
    """
    if not state.paper_summary:
        return []

    summary = state.paper_summary
    methods = [m.strip() for m in summary.methods if m.strip()] or [summary.model_architecture or "core method"]
    datasets = [d.strip() for d in summary.datasets if d.strip()] or ["the primary benchmark dataset"]
    limitations = [l.strip() for l in summary.limitations if l.strip()]
    if not limitations:
        limitations = [
            "robustness under distribution shift was not comprehensively validated",
            "scaling behavior across regimes was not explicitly characterized",
        ]

    untested_axes = (
        [a.strip() for a in (state.research_frame.untested_axes if state.research_frame else []) if a.strip()]
        or ["distribution shift", "compute-constrained setting", "cross-domain transfer"]
    )
    missing_baselines = (
        [b.strip() for b in (state.research_frame.missing_baselines if state.research_frame else []) if b.strip()]
        or ["strong contemporary baseline families"]
    )
    nearest_prior = related_papers[0].title if related_papers else "nearest related work could not be fetched due API limits"
    context_hint = rag_texts[0][:140] if rag_texts else "evidence inferred from extracted paper text"

    candidates: list[MetaGap] = [
        MetaGap(
            gap_type="robustness",
            statement=(
                f"No controlled study tests whether {methods[0]} remains effective under "
                f"{untested_axes[0]} on {datasets[0]}."
            ),
            why_it_matters=(
                f"The paper claims strong gains, but {limitations[0]} suggests external validity is unresolved."
            ),
            nearest_prior_work=nearest_prior,
            iteration_history=[f"heuristic: grounded from limitation and axis ({context_hint})"],
        ),
        MetaGap(
            gap_type="scaling",
            statement=(
                f"The scaling response of {methods[0]} across sparsity or compute regimes is under-specified."
            ),
            why_it_matters=(
                "Deployment decisions depend on whether gains hold when model size, budget, or sparsity target changes."
            ),
            nearest_prior_work=nearest_prior,
            iteration_history=["heuristic: inferred from method + missing scaling characterization"],
        ),
        MetaGap(
            gap_type="empirical",
            statement=(
                f"Critical baseline closure is missing against {missing_baselines[0]} for {datasets[0]}."
            ),
            why_it_matters=(
                "Without baseline closure, the mechanism-level contribution cannot be isolated from implementation effects."
            ),
            nearest_prior_work=nearest_prior,
            iteration_history=["heuristic: inferred from missing baselines"],
        ),
        MetaGap(
            gap_type="application",
            statement=(
                f"{methods[0]} has not been tested in a transfer setting beyond {datasets[0]} "
                "despite architecture-level portability claims."
            ),
            why_it_matters=(
                "Cross-domain validation can reveal whether the claimed operator is broadly causal or narrowly tuned."
            ),
            nearest_prior_work=nearest_prior,
            iteration_history=["heuristic: inferred from transfer/generalization gap"],
        ),
        MetaGap(
            gap_type="theoretical",
            statement=(
                f"No mechanistic attribution study isolates why {methods[0]} drives gains on {datasets[0]} "
                "versus confounding optimization effects."
            ),
            why_it_matters=(
                "Without mechanism attribution, empirical gains remain descriptive rather than causal."
            ),
            nearest_prior_work=nearest_prior,
            iteration_history=["heuristic: inferred from missing causal attribution test"],
        ),
    ]

    unique: list[MetaGap] = []
    seen: set[str] = set()
    for gap in candidates:
        key = gap.statement.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(gap)

    return unique[:5]
