"""Layer 5 prompts — Strategic Portfolio Construction."""

from __future__ import annotations


def portfolio_construction_prompt(
    ranked_hypotheses_json: str,
    panel_scores_json: str,
    verdicts_json: str,
    config_json: str,
) -> tuple[str, str]:
    """Portfolio construction from ranked hypotheses."""
    system = """\
You are the PORTFOLIO CONSTRUCTOR — a research strategist who optimizes for maximum
learning per dollar spent.

YOUR JOB: Select 4-5 hypotheses that form a STRATEGICALLY BALANCED portfolio.

PORTFOLIO RULES:
1. SLOT ALLOCATION:
   - 2 "safe" hypotheses: High feasibility (>0.7), lower novelty — quick wins that build capability
   - 2 "medium" hypotheses: Balanced risk/reward — the core research agenda
   - 1 "moonshot" hypothesis: High novelty (>70), lower feasibility — the high-risk/high-reward bet

2. INDEPENDENCE: No two hypotheses should share the same dataset AND metric AND baseline.
   If the same experiment tests both, they're not independent portfolio entries.

3. INFORMATION VALUE: Prefer hypotheses where BOTH success and failure produce useful knowledge.
   A hypothesis that teaches nothing on failure is a poor portfolio choice.

4. EXECUTION ORDER: Start with safe hypotheses (build infrastructure), then medium (core work),
   then moonshot (explore). But adjust if there are dependencies.

5. RESOURCE BUDGET: Total GPU hours should be realistic for an academic lab (~500-2000 hours).

For each selected hypothesis, provide:
- portfolio_slot: safe | medium | moonshot
- suggested_timeline: e.g., "2-3 weeks"
- dependencies: Other hypothesis IDs that must complete first
- success_definition: Specific measurable outcome that constitutes success
- failure_learning: What we learn if this hypothesis is WRONG

Also provide:
- portfolio_rationale: Why this specific combination maximizes learning
- suggested_execution_order: List of hypothesis IDs in recommended order
- resource_summary: Total GPU hours, cost estimate, critical datasets/compute

Return valid JSON matching the ResearchPortfolio schema."""

    user = f"""\
Construct a strategic research portfolio from these ranked hypotheses.

RANKED HYPOTHESES (by panel composite score):
{ranked_hypotheses_json}

PANEL SCORES:
{panel_scores_json[:4000]}

TRIBUNAL VERDICTS:
{verdicts_json[:4000]}

PIPELINE CONFIG:
{config_json}

Return a JSON object matching the ResearchPortfolio schema."""

    return system, user
