"""Prompts for archetype-mapped seed generation.

Instead of random diversity brainstorming, each gap gets matched to its
best-fit archetype and seeds are generated as structured IF/THEN/BECAUSE.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import (
    ARCHETYPE_DESCRIPTIONS,
    HypothesisArchetype,
    MetaGap,
    PaperSummary,
    ResearchFrame,
)


def archetype_seed_prompt(
    summary: PaperSummary,
    research_frame: ResearchFrame | None,
    gap: MetaGap,
    archetype: HypothesisArchetype,
    seeds_per_gap: int = 4,
    rag_snippets: list[str] | None = None,
) -> tuple[str, str]:
    """Generate seeds for a specific gap using a specific archetype."""
    archetype_desc = ARCHETYPE_DESCRIPTIONS.get(archetype, "")

    system = dedent(
        f"""\
        You are the VREDA Hypothesis Seeder — a precision instrument, not a brainstormer.

        You are generating seeds for archetype: {archetype.value}
        Archetype methodology: {archetype_desc}

        RULES — ENFORCED ON EVERY SEED:
        1. Each seed MUST follow the IF/THEN/BECAUSE format:
           "IF [exact intervention] THEN [quantified delta] on [named dataset] BECAUSE [mechanism]"
        2. Real named datasets ONLY (GLUE, ImageNet-C, C4, SWE-bench, MMLU, etc.)
           — NEVER "standard benchmark" or "suitable dataset"
        3. Prediction MUST contain a number or bounded direction
           — "+4-7% F1", "2x speedup", ">3 point BLEU improvement"
        4. The intervention must be a SINGLE precise change, not a research agenda
        5. The mechanism (BECAUSE) must reference a specific operator or principle from the paper

        Return JSON: {{"seeds": [{{"text": "IF ... THEN ... BECAUSE ...",
        "type": "hypothesis_type", "predicted_impact": "number or bounded direction",
        "archetype": "{archetype.value}", "gap_id": "{gap.gap_id}"}}]}}

        Generate exactly {seeds_per_gap} seeds."""
    )

    frame_block = ""
    if research_frame:
        gains_text = "; ".join(
            f"{g.operator}: {g.gain} ({g.condition})" for g in research_frame.claimed_gains[:5]
        ) or "none stated"
        frame_block = dedent(
            f"""
            RESEARCH FRAME:
            Core operators: {', '.join(research_frame.core_operators) or 'not_stated'}
            Core mechanism: {research_frame.core_mechanism or 'not_stated'}
            Claimed gains: {gains_text}
            Assumptions: {', '.join(research_frame.assumptions[:5]) or 'not_stated'}
            Missing baselines: {', '.join(research_frame.missing_baselines[:5]) or 'not_stated'}
            Untested axes: {', '.join(research_frame.untested_axes[:5]) or 'not_stated'}
            """
        )

    snippet_text = ""
    if rag_snippets:
        snippet_text = "\nCONTEXT SNIPPETS:\n" + "\n".join(f"- {s[:250]}" for s in rag_snippets[:3])

    user = dedent(
        f"""\
        PAPER: {summary.title}
        Domain: {summary.domain}
        Methods: {', '.join(summary.methods[:5])}
        Limitations: {', '.join(summary.limitations[:5])}
        {frame_block}
        TARGET GAP:
        [{gap.gap_id}] ({gap.gap_type}): {gap.statement}
        Why it matters: {gap.why_it_matters}
        Nearest prior work: {gap.nearest_prior_work}

        ARCHETYPE: {archetype.value} — {archetype_desc}
        {snippet_text}
        Generate {seeds_per_gap} seeds using the IF/THEN/BECAUSE format.
        Each seed must target the gap above using the {archetype.value} methodology."""
    )
    return system, user
