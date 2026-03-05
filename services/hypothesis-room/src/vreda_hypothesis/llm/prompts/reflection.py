"""Prompts for hypothesis reflection — multi-round refinement with literature.

AI-Scientist-v2 pattern: After initial hypothesis generation, the LLM reflects
on the hypothesis against live search results, strengthening novelty claims,
sharpening the experiment design, and addressing competitor work.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import EnhancedHypothesis, PaperMetadata


def reflection_prompt(
    hypothesis: EnhancedHypothesis,
    search_results: list[PaperMetadata],
    reflection_round: int,
) -> tuple[str, str]:
    """Generate reflection prompt — the LLM improves the hypothesis
    after seeing related papers from live S2 search.

    Returns (system, user) prompt pair.
    """
    system = dedent(
        """\
        You are a senior researcher performing a REFLECTION pass on a hypothesis.
        You have just received search results from Semantic Scholar showing the
        closest existing work to this hypothesis.

        Your job is to IMPROVE the hypothesis by:
        1. DIFFERENTIATION: If a close paper exists, sharpen what makes this hypothesis
           different. Cite the competitor paper explicitly.
        2. EXPERIMENT STRENGTHENING: If the competitor used certain baselines or datasets,
           ensure our hypothesis accounts for them (compare against, not just ignore).
        3. NOVELTY CLAIM ADJUSTMENT: If overlap_ratio > 0.5 with any found paper,
           pivot the hypothesis to focus on the genuinely novel aspect.
        4. RELATED WORK UPDATE: Add the most relevant found papers to related_work_summary.

        Return JSON with updated fields:
        - title: str (keep or improve)
        - statement: str (the IF/THEN/BECAUSE — sharpen based on what you learned)
        - description: str (updated with competitor awareness)
        - related_work_summary: str (add the most relevant found papers)
        - novelty_assessment: dict with "what_is_new" reflecting the refined novelty claim
        - testable_prediction: str (sharpen if needed)
        - risk_factors: list[str] (add risks from competitor work)"""
    )

    papers_block = "\n".join(
        f"- {p.title} ({p.year}, {p.citation_count} cit.): {p.abstract[:300]}"
        for p in search_results[:8]
    ) or "No closely related papers found — the hypothesis appears genuinely novel."

    user = dedent(
        f"""\
        REFLECTION ROUND: {reflection_round}

        CURRENT HYPOTHESIS:
        Title: {hypothesis.title}
        Archetype: {hypothesis.archetype.value if hypothesis.archetype else 'N/A'}
        Statement: {hypothesis.statement or hypothesis.short_hypothesis}
        Description: {hypothesis.description}
        Prediction: {hypothesis.testable_prediction}
        Related Work: {hypothesis.related_work_summary}

        LIVE SEARCH RESULTS FROM SEMANTIC SCHOLAR:
        {papers_block}

        Improve the hypothesis based on what you learned from these papers.
        Make the novelty claim STRONGER by explicitly contrasting with the closest work.
        If a competitor paper does something similar, pivot or sharpen — don't ignore it."""
    )
    return system, user
