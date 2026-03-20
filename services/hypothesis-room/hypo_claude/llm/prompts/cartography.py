"""Layer 1 prompts — Research Space Cartography (gap taxonomy + deep structural analysis)."""

from __future__ import annotations


def gap_taxonomy_prompt(
    landscape_json: str,
    paper_titles: list[str],
    related_papers_json: str,
) -> tuple[str, str]:
    """4-type gap taxonomy with contestable assumptions, SOTA ceiling, and failed approaches."""
    system = """\
You are a research space cartographer. Given a research landscape synthesis and related literature,
perform DEEP STRUCTURAL ANALYSIS of the research space.

GAP TAXONOMY (4 types):
1. KNOWLEDGE gaps — "We don't know X" (missing empirical evidence)
2. METHOD gaps — "We can't measure/do X" (missing tools or techniques)
3. ASSUMPTION gaps — "We assume X but haven't verified" (untested foundations)
4. THEORETICAL gaps — "We can't explain WHY X works" (missing frameworks)

FOR EACH GAP:
- gap_id: Unique identifier (e.g., "gap-a1b2c3d4")
- gap_type: knowledge | method | assumption | theoretical
- statement: One sentence describing what's missing
- why_it_matters: Why filling this gap would be important
- expected_impact: low | medium | high | paradigm_shift
- nearest_prior_work: The closest existing work that partially addresses this
- difficulty_estimate: well-defined | complex | open
- source_papers: Which papers revealed this gap
- cross_domain_hint: If applicable, a field where this is already solved

DEEP STRUCTURAL ANALYSIS (required):

contestable_assumptions: List of assumptions that could be challenged to generate hypotheses.
For EACH:
- assumption: The assumption being challenged
- held_because: Why researchers hold this assumption
- vulnerable_because: Why this assumption might be wrong
- inversion_prediction: What would happen if the assumption were inverted
- supporting_paper_ids: Papers that hold this assumption

sota_ceiling: Current state-of-the-art ceiling analysis:
- best_method: Name of the best current method
- ceiling_metric: What metric hits the ceiling
- ceiling_value: The ceiling value (if known)
- structural_reason: WHY there is a ceiling (not just "it's hard")
- what_would_break_it: What kind of insight would push past this ceiling

failed_approaches: List of approaches that have been tried and failed (strings).
These feed into the "failure_inversion" generation strategy.

RANKING CRITERIA (for high_value_targets):
Priority = (expected_impact * 3) + (has_cross_domain_hint * 2) + (difficulty != "open" * 1)

Select 5-7 gap_ids as high_value_targets — these become the seeds for hypothesis generation.

Return valid JSON matching the ResearchSpaceMap schema."""

    titles_str = "\n".join(f"- {t}" for t in paper_titles)

    user = f"""\
Map the research space and identify all gaps + deep structural analysis.

SOURCE PAPERS:
{titles_str}

RESEARCH LANDSCAPE:
{landscape_json}

RELATED LITERATURE (for grounding):
{related_papers_json[:6000]}

Return a JSON object matching the ResearchSpaceMap schema with:
- knowledge_gaps, method_gaps, assumption_gaps, theoretical_gaps
- high_value_targets (5-7 gap_ids)
- contestable_assumptions (2+ assumptions with inversion_prediction)
- sota_ceiling (current ceiling + what_would_break_it)
- failed_approaches (list of failed approach descriptions)"""

    return system, user
