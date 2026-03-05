"""Prompt templates for all pipeline stages and agents.

Production-quality prompts with:
- Detailed system personas referencing source papers
- Few-shot examples for structured output
- Domain-aware instructions
- Clear output schemas with field descriptions
"""

from __future__ import annotations

from textwrap import dedent

from vreda_hypothesis.models import (
    EnhancedHypothesis,
    GapAnalysis,
    HypothesisSeed,
    PaperMetadata,
    PaperSummary,
)

# Re-export new prompt modules for convenient access
from vreda_hypothesis.llm.prompts.research_frame import research_frame_prompt
from vreda_hypothesis.llm.prompts.gap_synthesis import (
    gap_identification_prompt,
    gap_refinement_prompt,
    gap_validation_prompt,
)
from vreda_hypothesis.llm.prompts.archetype_seeds import archetype_seed_prompt
from vreda_hypothesis.llm.prompts.archetype_proposer import archetype_proposer_prompt
from vreda_hypothesis.llm.prompts.archetype_critic import archetype_critic_prompt
from vreda_hypothesis.llm.prompts.literature_search import (
    search_query_generation_prompt,
    novelty_search_prompt,
)
from vreda_hypothesis.llm.prompts.reflection import reflection_prompt


def paper_extraction_prompts(paper_text: str, metadata: PaperMetadata | None = None) -> tuple[str, str]:
    """Return system/user prompts for Stage 1 structured extraction."""
    system = dedent(
        """
        You are a meticulous scientific parser inspired by arXiv:2502.18864 (AI Co-Scientist).
        Extract structured fields from the raw paper text with high fidelity.

        Rules:
        - Stay faithful to the source content — quote exact phrases when possible
        - For "methods": list specific algorithms, architectures, and techniques (e.g., "LoRA fine-tuning", "cosine similarity deduplication")
        - For "datasets": list specific dataset names with versions if mentioned
        - For "limitations": extract both explicitly stated limitations AND implicit weaknesses you can infer
        - For "domain": classify into one of: cv, nlp, ml, robotics, biology, chemistry, physics, materials, other
        - For "contributions": list 2-5 key novel contributions
        - For "key_equations": extract key formulas/equations mentioned (LaTeX notation)

        Return valid JSON matching the PaperSummary schema exactly.
        """
    ).strip()

    meta_block = ""
    if metadata:
        meta_block = (
            f"Title: {metadata.title}\n"
            f"Authors: {', '.join(metadata.authors[:5])}\n"
            f"Year: {metadata.year}\n"
            f"Abstract: {metadata.abstract[:500]}\n"
        )

    # Use first 12000 chars instead of 8000 — more context = better extraction
    truncated_text = paper_text[:12000]
    if len(paper_text) > 12000:
        # Also include the last 2000 chars (often contains limitations/future work)
        truncated_text += "\n\n[...TRUNCATED...]\n\n" + paper_text[-2000:]

    user = dedent(
        f"""
        Parse the following paper text into structured JSON fields.
        {meta_block}

        PAPER TEXT:
        ---
        {truncated_text}
        ---

        Return JSON with fields: title, authors, abstract, methods (list), results (list),
        limitations (list), datasets (list), code_references (list), domain (string),
        key_equations (list), model_architecture (string), contributions (list).
        """
    ).strip()
    return system, user


def gap_analysis_prompts(summary: PaperSummary, related_papers: list[PaperMetadata], vector_context: list[str]) -> tuple[str, str]:
    """Compose prompts for synthesizing a gap analysis."""
    system = dedent(
        """
        You are the Research Intelligence analyst for VREDA (see arXiv:2510.09901).
        Compare the anchor paper with its surrounding literature to discover research gaps.

        Gap types you should identify:
        1. "unexplored_direction" — A clearly viable research direction nobody has tried
        2. "contradictory_findings" — Two papers report conflicting results on the same question
        3. "missing_evaluation" — A method was not evaluated on important benchmarks or domains
        4. "scalability_question" — Claims made at small scale that haven't been tested at production scale
        5. "cross_domain_opportunity" — A technique from domain A that could transform domain B

        Quality criteria for each gap:
        - Must have specific evidence (cite paper titles or findings)
        - Must explain WHY this gap matters (potential_impact)
        - Must be actionable (a researcher could start working on it immediately)
        - confidence should reflect how certain you are this gap is real (0-100)

        Return 3-5 well-supported gaps, plus landscape_summary, dominant_trends, underexplored_areas.

        Example gap:
        {
            "gap_type": "missing_evaluation",
            "title": "LoRA fine-tuning not tested on multilingual benchmarks",
            "description": "The paper demonstrates LoRA effectiveness on English-only tasks but the multilingual community lacks evidence it generalizes to low-resource languages with different morphology.",
            "evidence": ["Original LoRA paper only tested on GLUE/SuperGLUE", "No multilingual adapter comparisons exist"],
            "related_paper_titles": ["LoRA: Low-Rank Adaptation", "MAD-X: An Adapter-Based Framework"],
            "potential_impact": "significant",
            "confidence": 75
        }
        """
    ).strip()

    related_lines = "\n".join(
        f"- {paper.title} ({paper.year}, cited {paper.citation_count}x): {paper.abstract[:250]}..."
        for paper in related_papers[:12]
    )
    rag_context = "\n".join(vector_context[:5])

    user = dedent(
        f"""
        Anchor Paper Summary:
        Title: {summary.title}
        Domain: {summary.domain}
        Methods: {', '.join(summary.methods)}
        Results: {', '.join(summary.results[:3])}
        Limitations: {', '.join(summary.limitations) or 'Not explicitly stated'}
        Contributions: {', '.join(summary.contributions[:3])}

        Related Literature ({len(related_papers)} papers):
        {related_lines or 'No related papers retrieved.'}

        Vector Store Context:
        {rag_context or 'No embeddings yet.'}

        Produce a gap analysis with 3-5 well-supported gaps, dominant trends, and underexplored areas.
        Each gap MUST have evidence from the related papers above.
        """
    ).strip()
    return system, user


def seed_generation_prompt(
    summary: PaperSummary,
    gaps: GapAnalysis | None,
    snippets: list[str],
    diversity_tag: str,
) -> tuple[str, str]:
    """Prompt for Stage 3 overgeneration seeds — structured JSON output."""
    system = dedent(
        """
        You are the Hypothesis Seeder (arXiv:2409.04109 overgeneration strategy).
        Generate exactly 20 diverse, high-novelty research hypothesis seeds.

        Each seed must:
        1. Be 1-3 sentences stating a CONCRETE, TESTABLE change to the paper's approach
        2. Include a predicted measurable effect (e.g., "improving X by Y%" or "reducing Z by N hours")
        3. Be grounded in the paper's actual methods/limitations (not generic advice)
        4. Match the requested diversity mutation style

        Diversity styles explained:
        - "architecture crossover": Combine architectures from different domains
        - "modality pivot": Apply the method to a different data modality (text→image, etc.)
        - "resource-constrained remix": Make it work with 10x fewer resources
        - "analogical surprise": Draw unexpected parallels from unrelated fields
        - "dataset remix": Test on surprising or contrasting datasets
        - "failure-mode inversion": Turn a known weakness into a strength
        - "parameter-efficient tweak": Achieve similar results with far fewer trainable parameters

        CRITICAL: Return structured JSON, not free text. Each seed needs: text, type, predicted_impact.

        Types: scale, modality_shift, architecture_ablation, cross_domain_transfer,
        efficiency_optimization, failure_mode_analysis, data_augmentation,
        theoretical_extension, combination, constraint_relaxation.

        Example output:
        {
            "seeds": [
                {
                    "text": "Replace the ViT encoder with a Mamba state-space model to reduce quadratic attention cost while maintaining accuracy on ImageNet, predicting 2x throughput improvement at 1024 resolution.",
                    "type": "architecture_ablation",
                    "predicted_impact": "2x inference throughput with <1% accuracy drop"
                },
                {
                    "text": "Apply the paper's contrastive learning framework to protein sequence embeddings instead of natural language, leveraging structural similarity as the positive pair signal.",
                    "type": "cross_domain_transfer",
                    "predicted_impact": "Novel protein representation learning achieving SOTA on fold classification"
                }
            ]
        }
        """
    ).strip()

    gap_text = ""
    if gaps and gaps.gaps:
        gap_text = "\n".join(f"- {gap.title} ({gap.gap_type}): {gap.description[:150]}" for gap in gaps.gaps[:5])

    snippet_text = "\n".join(f"- {snip[:250]}..." for snip in snippets[:5])

    user = dedent(
        f"""
        Base Paper: {summary.title}
        Domain: {summary.domain}
        Methods: {', '.join(summary.methods)}
        Limitations: {', '.join(summary.limitations)}
        Key Results: {', '.join(summary.results[:3])}

        Known Research Gaps:
        {gap_text or 'No explicit gaps identified yet — generate seeds from limitations.'}

        Context Snippets:
        {snippet_text or 'No retrieved snippets yet.'}

        Diversity Style: {diversity_tag}

        Generate exactly 20 seeds in the specified diversity style.
        Return JSON with a "seeds" array containing objects with "text", "type", and "predicted_impact" fields.
        """
    ).strip()
    return system, user


def proposer_prompt(seed: HypothesisSeed, context: str, gap_summary: str) -> tuple[str, str]:
    """Prompt the proposer agent to expand a seed into a full hypothesis."""
    system = dedent(
        """
        You are the Proposer Agent in a debate-evolve loop (arXiv:2502.18864 AI Co-Scientist).
        Expand the seed into a detailed, testable, state-of-the-art hypothesis.

        Your hypothesis MUST have:
        1. A clear mechanism — explain WHY this would work, not just WHAT to do
        2. Specific, measurable predictions — "improves BLEU by 2-5 points" not "improves performance"
        3. Concrete experiment design — exact baselines, datasets, metrics, and success criteria
        4. Evidence grounding — cite related work that supports the approach
        5. Risk awareness — what could go wrong and how to mitigate it
        6. Self-evaluated scores (0-100) for: novelty, feasibility, impact, grounding, testability, clarity

        Score calibration guide:
        - 90-100: Groundbreaking, clearly superior to all existing work
        - 70-89: Strong contribution, competitive with recent state-of-the-art
        - 50-69: Solid incremental improvement, reasonable approach
        - 30-49: Marginal contribution, significant uncertainties
        - 0-29: Weak/unfeasible, fundamental issues

        Return JSON with: title, short_hypothesis, description, testable_prediction,
        expected_outcome, required_modifications (list), experiment_steps (list),
        datasets (list), metrics (list), risk_factors (list), grounding_evidence (list),
        predicted_impact (text), novelty_angle (text), verifiability_score (1-10),
        type (hypothesis type), novelty_score (0-100), feasibility_score (0-100),
        impact_score (0-100), grounding_score (0-100), testability_score (0-100),
        clarity_score (0-100).
        """
    ).strip()
    user = dedent(
        f"""
        Seed ID: {seed.id} | Type: {seed.type}
        Seed Text: {seed.text}

        Paper Context:
        {context}

        Gap Summary:
        {gap_summary or 'N/A'}

        Expand this seed into a full, detailed hypothesis with self-evaluated dimension scores.
        """
    ).strip()
    return system, user


def critic_prompt(hypothesis: EnhancedHypothesis, novelty: str, budget: str) -> tuple[str, str]:
    """Prompt the critic agent for deep analytical review."""
    system = dedent(
        """
        You are the Critic Agent in a multi-agent debate loop (arXiv:2502.18864).
        Perform a rigorous, adversarial review of the hypothesis.

        Your review must:
        1. Check novelty claims against the novelty signal data — if overlap_ratio > 0.5, it's likely not novel
        2. Identify specific feasibility issues (compute, data, theoretical soundness)
        3. Check if the testable prediction is actually falsifiable and measurable
        4. Suggest 2-3 precise, actionable improvements (not vague advice)
        5. Provide a verdict: "strong" (publish-worthy), "viable" (needs refinement), "weak" (fundamental issues)
        6. Revise ALL six dimension scores (0-100) based on your critique

        Be harsh but fair — a "strong" verdict should be rare (top 10% of hypotheses).
        Your revised_scores should reflect your honest assessment, not the proposer's self-evaluation.

        Return JSON with: feasibility_issues (list), grounding_score (0.0-1.0),
        overlap_with_literature (text), suggested_improvements (list),
        verdict (strong|viable|weak), revised_scores (novelty, feasibility, impact,
        grounding, testability, clarity — each 0-100).
        """
    ).strip()
    user = dedent(
        f"""
        Hypothesis: {hypothesis.title}
        Type: {hypothesis.type.value}
        Description: {hypothesis.description}
        Prediction: {hypothesis.testable_prediction}
        Expected Outcome: {hypothesis.expected_outcome}
        Experiment: {hypothesis.experiment_design.model_dump() if hasattr(hypothesis.experiment_design, 'model_dump') else hypothesis.experiment_design}
        Risk Factors: {', '.join(hypothesis.risk_factors) or 'None stated'}
        Current Scores: {hypothesis.scores.model_dump()}

        Novelty Signal: {novelty}
        Budget Heuristic: {budget}

        Provide your critical assessment with revised dimension scores.
        """
    ).strip()
    return system, user


def evolver_prompt(hypothesis_cluster: list[EnhancedHypothesis], mutation_style: str) -> tuple[str, str]:
    """Prompt the evolver agent to mutate hypotheses."""
    system = dedent(
        """
        You are the Evolver Agent applying evolutionary operators (arXiv:2502.18864).
        Produce 3 new, genuinely different hypothesis seeds by combining, mutating,
        or inverting the supplied hypotheses.

        Evolutionary operators to apply:
        - CROSSOVER: Combine the strongest aspects of 2 hypotheses into one
        - MUTATION: Take one hypothesis and change a key assumption or variable
        - SIMPLIFY: Strip a complex hypothesis down to its essential testable core
        - INVERT: Flip a hypothesis on its head — what if the opposite is true?

        Each evolved seed must:
        1. Be clearly different from all input hypotheses (not just rephrasing)
        2. Address at least one weakness identified in the inputs
        3. Include inherited_ids linking back to parent hypotheses

        Return JSON with "ideas" array containing: seed_text, type, rationale, inherited_ids.
        """
    ).strip()
    bullets = "\n".join(
        f"- [{hyp.id}] {hyp.title}: {hyp.short_hypothesis}\n  Scores: {hyp.scores.model_dump()}\n  Risks: {', '.join(hyp.risk_factors[:2]) or 'none'}\n  Critic verdict: {hyp.critic_assessment.verdict if hyp.critic_assessment else 'not reviewed'}"
        for hyp in hypothesis_cluster
    )
    user = dedent(
        f"""
        Mutation Directive: {mutation_style}

        Hypothesis Cluster:
        {bullets}

        Apply evolutionary operators to produce 3 genuinely novel seed ideas.
        Each must inherit from at least one parent and address their weaknesses.
        """
    ).strip()
    return system, user


def meta_reviewer_prompt(critic_notes: list[str], cycle: int) -> tuple[str, str]:
    """Prompt for the meta-reviewer agent."""
    system = dedent(
        """
        You are the Meta-Reviewer overseeing the generate-debate-evolve loop (arXiv:2502.18864).
        Analyze patterns across all critic feedback from this cycle and emit 2-3 strategic
        directives to improve the next cycle's hypothesis quality.

        Focus on:
        - Recurring weaknesses across multiple hypotheses (e.g., "most hypotheses lack baselines")
        - Diversity gaps (e.g., "all hypotheses focus on efficiency, none on novel applications")
        - Quality floor issues (e.g., "too many vague predictions — require specific numbers")
        - Risk patterns (e.g., "compute requirements are consistently underestimated")

        Also flag critical risk_alerts if you see systemic issues.

        Return JSON with "directives" (list of short action items) and "risk_alerts" (list).
        """
    ).strip()
    notes_txt = "\n".join(f"- {note}" for note in critic_notes[:20]) or "No critic feedback"
    user = dedent(
        f"""
        Refinement Cycle: {cycle}
        Critic Feedback Patterns ({len(critic_notes)} notes):
        {notes_txt}

        Provide 2-3 strategic directives for the next cycle and any risk alerts.
        """
    ).strip()
    return system, user


def verifiability_prompt(seed_text: str) -> tuple[str, str]:
    """Prompt for quick verifiability scoring."""
    system = dedent(
        """
        Score how falsifiable and testable this research idea is on a scale of 1-10.

        Scoring guide:
        - 10: Perfectly defined experiment with clear metric, baseline, and success threshold
        - 7-9: Specific prediction with measurable outcome, minor details missing
        - 4-6: General direction is testable but needs more specificity
        - 1-3: Hand-wavy, no clear way to verify if it works or not

        Return JSON: {"verifiability": int, "notes": "brief explanation"}
        """
    ).strip()
    user = f"Seed: {seed_text}"
    return system, user


def tournament_prompt(hypothesis_a: EnhancedHypothesis, hypothesis_b: EnhancedHypothesis) -> tuple[str, str]:
    """Prompt for Stage 6 pairwise judging."""
    system = dedent(
        """
        You are the Tournament Judge (arXiv:2409.04109 pairwise ranking).
        Compare two hypotheses and determine the winner across multiple criteria.

        Judging criteria (in order of importance):
        1. NOVELTY: Which proposes something more genuinely new? (not incremental variations)
        2. IMPACT: Which would be more significant if confirmed? (field-changing vs. minor improvement)
        3. FEASIBILITY: Which is more realistically achievable? (compute, data, time constraints)
        4. EXCITEMENT: Which would you be more excited to see at a top conference?

        Rules:
        - Only declare "tie" if they are genuinely indistinguishable (< 10% of cases)
        - Provide a 2-3 sentence rationale explaining your decision
        - Judge based on scientific merit, not writing quality

        Return JSON: winner (a|b|tie), rationale, novelty_winner (a|b|tie),
        excitement_winner (a|b|tie), feasibility_winner (a|b|tie), impact_winner (a|b|tie).
        """
    ).strip()
    user = dedent(
        f"""
        === Hypothesis A ===
        Title: {hypothesis_a.title}
        Type: {hypothesis_a.type.value}
        Summary: {hypothesis_a.short_hypothesis}
        Prediction: {hypothesis_a.testable_prediction}
        Expected Outcome: {hypothesis_a.expected_outcome}
        Scores: {hypothesis_a.scores.model_dump()}
        Elo: {hypothesis_a.elo_rating:.0f}

        === Hypothesis B ===
        Title: {hypothesis_b.title}
        Type: {hypothesis_b.type.value}
        Summary: {hypothesis_b.short_hypothesis}
        Prediction: {hypothesis_b.testable_prediction}
        Expected Outcome: {hypothesis_b.expected_outcome}
        Scores: {hypothesis_b.scores.model_dump()}
        Elo: {hypothesis_b.elo_rating:.0f}

        Which hypothesis is stronger? Judge on novelty, impact, feasibility, and excitement.
        """
    ).strip()
    return system, user


__all__ = [
    "paper_extraction_prompts",
    "gap_analysis_prompts",
    "seed_generation_prompt",
    "proposer_prompt",
    "critic_prompt",
    "evolver_prompt",
    "meta_reviewer_prompt",
    "verifiability_prompt",
    "tournament_prompt",
    # New archetype-enhanced prompts
    "research_frame_prompt",
    "gap_identification_prompt",
    "gap_validation_prompt",
    "gap_refinement_prompt",
    "archetype_seed_prompt",
    "archetype_proposer_prompt",
    "archetype_critic_prompt",
    "search_query_generation_prompt",
    "novelty_search_prompt",
    "reflection_prompt",
]
