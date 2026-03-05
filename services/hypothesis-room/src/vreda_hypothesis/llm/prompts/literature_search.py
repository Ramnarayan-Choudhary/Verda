"""Prompts for LLM-driven literature search — targeted query generation.

AI-Scientist-v2 pattern: Instead of only fetching related papers from S2 references/citations,
the LLM generates targeted search queries based on the paper's operators, mechanisms, and gaps.
This discovers papers the citation graph might miss.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import PaperSummary, ResearchFrame


def search_query_generation_prompt(
    summary: PaperSummary,
    research_frame: ResearchFrame | None,
    existing_paper_titles: list[str],
) -> tuple[str, str]:
    """Generate targeted Semantic Scholar search queries to find papers
    the citation graph missed.

    Returns (system, user) prompt pair.
    """
    system = dedent(
        """\
        You are a research librarian generating precise search queries for
        Semantic Scholar API. Your goal: find papers that the citation graph
        MISSED but are highly relevant to the paper's operators and gaps.

        Query design rules:
        - Each query must be 3-8 words — specific enough to find relevant papers
        - Target: named techniques, specific operators, exact methodologies
        - Mix query types:
          * OPERATOR queries: search for the paper's core operators in other contexts
          * GAP queries: search for work that might fill the paper's gaps
          * COMPETITOR queries: search for alternative approaches to the same problem
          * CROSS-DOMAIN queries: search for the same operator used in different domains
        - Avoid generic terms like "deep learning" or "neural network"
        - Use real method names: "LoRA fine-tuning", "flash attention", "contrastive loss"

        Return JSON: {"queries": [{"query": "...", "intent": "operator|gap|competitor|cross_domain"}]}
        Generate exactly 4 queries."""
    )

    existing_titles = "\n".join(f"- {t}" for t in existing_paper_titles[:10])

    frame_block = ""
    if research_frame:
        frame_block = dedent(
            f"""
            RESEARCH FRAME:
            - Core operators: {', '.join(research_frame.core_operators) or 'not_stated'}
            - Core mechanism: {research_frame.core_mechanism or 'not_stated'}
            - Missing baselines: {', '.join(research_frame.missing_baselines) or 'not_stated'}
            - Untested axes: {', '.join(research_frame.untested_axes) or 'not_stated'}
            - Implicit limits: {', '.join(research_frame.implicit_limits) or 'not_stated'}
            """
        )

    user = dedent(
        f"""\
        PAPER: {summary.title}
        Domain: {summary.domain}
        Methods: {', '.join(summary.methods)}
        Limitations: {', '.join(summary.limitations) or 'None stated'}
        {frame_block}
        PAPERS WE ALREADY HAVE (don't search for these):
        {existing_titles or 'None yet'}

        Generate 4 targeted search queries to find papers we're missing.
        Focus on the paper's specific operators and gaps, NOT generic topics."""
    )
    return system, user


def novelty_search_prompt(
    seed_text: str,
    search_results: list[dict],
) -> tuple[str, str]:
    """Check if a hypothesis seed is novel given search results from S2.

    Returns (system, user) prompt pair for novelty assessment.
    """
    system = dedent(
        """\
        You are a novelty assessor. Given a hypothesis seed and papers from
        Semantic Scholar, determine:

        1. is_novel (bool): Does ANY paper already propose or test this exact idea?
        2. overlap_score (0.0-1.0): How much overlap with existing work?
           - 0.0 = completely novel, no related work found
           - 0.5 = related work exists but the specific combination/application is new
           - 1.0 = this exact idea has been published
        3. closest_paper: Title of the most related paper found
        4. differentiation: What makes this seed different from closest_paper (1 sentence)

        RULES:
        - A seed is NOT novel if it merely applies an existing technique to a standard dataset
        - A seed IS novel if it combines operators in a new way, even if individual parts exist
        - Partial overlap (0.3-0.7) is expected and OK — pure novelty is rare

        Return JSON: {"is_novel": bool, "overlap_score": float,
        "closest_paper": str, "differentiation": str}"""
    )

    papers_block = "\n".join(
        f"- {p.get('title', 'Unknown')}: {p.get('abstract', '')[:250]}"
        for p in search_results[:8]
    )

    user = dedent(
        f"""\
        HYPOTHESIS SEED:
        {seed_text}

        SEMANTIC SCHOLAR RESULTS:
        {papers_block or 'No papers found for this query.'}

        Assess novelty of the seed against these papers."""
    )
    return system, user
