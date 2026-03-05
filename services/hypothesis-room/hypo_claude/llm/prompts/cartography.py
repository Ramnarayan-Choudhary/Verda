"""Layer 1 prompts — Research Space Cartography (gap taxonomy)."""

from __future__ import annotations


def gap_taxonomy_prompt(
    landscape_json: str,
    paper_titles: list[str],
    related_papers_json: str,
) -> tuple[str, str]:
    """4-type gap taxonomy with severity scoring."""
    system = """\
You are a research space cartographer. Given a research landscape synthesis and related literature,
identify ALL research gaps organized into 4 types.

GAP TAXONOMY:
1. KNOWLEDGE gaps — "We don't know X" (missing empirical evidence)
2. METHOD gaps — "We can't measure/do X" (missing tools or techniques)
3. ASSUMPTION gaps — "We assume X but haven't verified" (untested foundations)
4. THEORETICAL gaps — "We can't explain WHY X works" (missing frameworks)

FOR EACH GAP:
- statement: One sentence describing what's missing
- why_it_matters: Why filling this gap would be important
- expected_impact: low | medium | high | paradigm_shift
- nearest_prior_work: The closest existing work that partially addresses this
- difficulty_estimate: well-defined | complex | open
- source_papers: Which papers revealed this gap
- cross_domain_hint: If applicable, a field where this is already solved

RANKING CRITERIA (for high_value_targets):
Priority = (expected_impact * 3) + (has_cross_domain_hint * 2) + (difficulty != "open" * 1)

Select 5-7 gap_ids as high_value_targets — these become the seeds for hypothesis generation.

Return valid JSON matching the ResearchSpaceMap schema."""

    titles_str = "\n".join(f"- {t}" for t in paper_titles)

    user = f"""\
Map the research space and identify all gaps.

SOURCE PAPERS:
{titles_str}

RESEARCH LANDSCAPE:
{landscape_json}

RELATED LITERATURE (for grounding):
{related_papers_json[:6000]}

Return a JSON object matching the ResearchSpaceMap schema with knowledge_gaps, method_gaps,
assumption_gaps, theoretical_gaps, and high_value_targets."""

    return system, user
