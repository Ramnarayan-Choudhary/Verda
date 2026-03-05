"""Prompt for the enhanced Proposer Agent — full archetype-structured hypotheses.

Outputs include: IF/THEN/BECAUSE statement, 5-step MVE, falsification threshold,
adversarial defense, and resource estimates.
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import (
    ARCHETYPE_DESCRIPTIONS,
    HypothesisArchetype,
    HypothesisSeed,
    MetaGap,
    ResearchFrame,
)


def archetype_proposer_prompt(
    seed: HypothesisSeed,
    context: str,
    gap_summary: str,
    research_frame: ResearchFrame | None = None,
    meta_gap: MetaGap | None = None,
) -> tuple[str, str]:
    """Prompt the proposer to expand a seed into a full archetype-structured hypothesis."""
    archetype = seed.archetype
    archetype_desc = ARCHETYPE_DESCRIPTIONS.get(archetype, "")

    system = dedent(
        f"""\
        You are the VREDA Proposer Agent — a precision hypothesis engineer, not a brainstormer.

        You are expanding a seed into a COMPLETE, EXECUTABLE research hypothesis using
        the {archetype.value} archetype: {archetype_desc}

        HARD RULES — ENFORCED ON EVERY OUTPUT:
        1. Real named datasets ONLY (GLUE, ImageNet-C, C4, SWE-bench, MMLU, etc.)
           — NEVER "standard benchmark" or "suitable dataset"
        2. Prediction MUST contain a number or bounded direction
           — e.g., "+4-7% F1", "2x speedup", ">3 point BLEU improvement"
        3. MVE MUST be EXACTLY 5 steps — reject if it cannot be written in 5
           Format: "1. Load [dataset]", "2. Apply [intervention]", etc.
        4. gpu_hours MUST be MVE-realistic — not a full training run
        5. novelty verdict = "incremental" requires explicit justification
        6. Statement MUST follow IF/THEN/BECAUSE format

        OUTPUT SCHEMA:
        {{
            "title": "6 words max. Specific.",
            "archetype": "{archetype.value}",
            "gap_id": "the gap ID this targets",
            "statement": "IF [exact intervention] THEN [quantified delta] on [named dataset] BECAUSE [mechanism]",
            "experiment": {{
                "intervention": "The single precise change",
                "control": "What stays fixed",
                "dataset": "Named real dataset only",
                "metric": "Named metric only",
                "prediction": "Number or direction with magnitude",
                "falsification_threshold": "Dead if: [specific condition]"
            }},
            "mve": [
                "1. Load [dataset]",
                "2. Apply [intervention] to [component]",
                "3. Train [N steps] with [config]",
                "4. Eval [metric] vs control on [split]",
                "5. Statistical test: [method]"
            ],
            "resources": {{
                "model": "Exact model name",
                "gpu_hours": 24
            }},
            "novelty": {{
                "closest_paper": "Most similar existing work",
                "why_distinct": "One sentence",
                "verdict": "substantial|incremental"
            }},
            "adversarial": {{
                "kill_switch": "Strongest reviewer objection",
                "defense": "Design change that neutralizes it"
            }},
            "description": "2-3 sentences describing the hypothesis",
            "testable_prediction": "Specific, falsifiable statement",
            "expected_outcome": "What success looks like",
            "required_modifications": ["list of code/experiment changes"],
            "risk_factors": ["what could go wrong"],
            "grounding_evidence": ["supporting papers or findings"],
            "predicted_impact": "why this matters",
            "type": "hypothesis_type for frontend",
            "novelty_score": 0-100,
            "feasibility_score": 0-100,
            "impact_score": 0-100,
            "grounding_score": 0-100,
            "testability_score": 0-100,
            "clarity_score": 0-100
        }}

        Score calibration:
        - 90-100: Groundbreaking, clearly superior to all existing work
        - 70-89: Strong contribution, competitive with recent SOTA
        - 50-69: Solid incremental improvement
        - 30-49: Marginal contribution, significant uncertainties
        - 0-29: Weak/unfeasible"""
    )

    frame_block = ""
    if research_frame:
        gains_text = "; ".join(
            f"{g.operator}: {g.gain} ({g.condition})" for g in research_frame.claimed_gains[:3]
        ) or "none"
        frame_block = (
            f"\nRESEARCH FRAME:\n"
            f"Core operators: {', '.join(research_frame.core_operators[:5]) or 'not_stated'}\n"
            f"Core mechanism: {research_frame.core_mechanism or 'not_stated'}\n"
            f"Claimed gains: {gains_text}\n"
            f"Assumptions: {', '.join(research_frame.assumptions[:3]) or 'not_stated'}\n"
        )

    gap_block = ""
    if meta_gap:
        gap_block = (
            f"\nTARGET GAP:\n"
            f"[{meta_gap.gap_id}] ({meta_gap.gap_type}): {meta_gap.statement}\n"
            f"Why: {meta_gap.why_it_matters}\n"
            f"Prior: {meta_gap.nearest_prior_work}\n"
        )

    user = dedent(
        f"""\
        Seed ID: {seed.id} | Archetype: {seed.archetype.value} | Type: {seed.type.value}
        Seed Text: {seed.text}

        Paper Context:
        {context}
        {frame_block}{gap_block}
        Gap Summary: {gap_summary or 'N/A'}

        Expand this seed into a full archetype-structured hypothesis.
        Follow the IF/THEN/BECAUSE format. Include exactly 5 MVE steps.
        Include falsification threshold and adversarial defense."""
    )
    return system, user
