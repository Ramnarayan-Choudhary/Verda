"""Stage 7 — Portfolio Audit.

Checks that the hypothesis set has:
1. Coverage across portfolio tags (empirical, robustness, scaling, theoretical)
2. No redundancies (two hypotheses testing the same variable)
3. Optimal execution order (cheapest + highest signal first)
"""

from __future__ import annotations

from typing import Any

import structlog

from vreda_hypothesis.models import EnhancedHypothesis, PipelineState, PortfolioAudit, StageError

logger = structlog.get_logger(__name__)


async def run(state: PipelineState) -> dict[str, Any]:
    hypotheses = state.tournament_results or state.refined_hypotheses
    if not hypotheses:
        return {}

    top_k = state.config.top_k
    top_hypotheses = hypotheses[:top_k]

    try:
        # 1. Coverage check
        coverage: dict[str, str] = {}
        for h in top_hypotheses:
            tag = h.portfolio_tag
            if tag not in coverage:
                coverage[tag] = h.id

        # 2. Redundancy detection
        redundancies = _find_redundancies(top_hypotheses)

        # 3. Execution order — cheapest GPU hours + highest composite first
        execution_order = sorted(
            top_hypotheses,
            key=lambda h: (h.resources.gpu_hours, -h.composite_score),
        )
        order_descriptions = [
            f"{h.id} — {h.resources.gpu_hours}h GPU, score={h.composite_score}, {h.archetype.value}"
            for h in execution_order
        ]

        audit = PortfolioAudit(
            coverage=coverage,
            redundancies=redundancies,
            execution_order=order_descriptions,
        )

        # Log coverage gaps
        expected_tags = {"empirical", "robustness", "scaling", "theoretical"}
        missing_tags = expected_tags - set(coverage.keys())
        if missing_tags:
            logger.warning(
                "portfolio_audit.coverage_gap",
                missing=list(missing_tags),
                covered=list(coverage.keys()),
            )

        logger.info(
            "stage.portfolio_audit.complete",
            coverage_count=len(coverage),
            redundancies=len(redundancies),
            total_hypotheses=len(top_hypotheses),
        )
        return {"portfolio_audit": audit}

    except Exception as exc:
        logger.exception("stage.portfolio_audit.error", error=str(exc))
        state.errors.append(StageError(stage="portfolio_audit", message=str(exc)))
        return {"errors": state.errors}


def _find_redundancies(hypotheses: list[EnhancedHypothesis]) -> list[str]:
    """Detect hypotheses that test the same variable or cover the same gap."""
    redundancies: list[str] = []
    seen_gaps: dict[str, str] = {}
    seen_interventions: dict[str, str] = {}

    for h in hypotheses:
        # Check gap-level redundancy
        if h.addresses_gap_id and h.addresses_gap_id in seen_gaps:
            redundancies.append(
                f"{h.id} and {seen_gaps[h.addresses_gap_id]} both target gap {h.addresses_gap_id}"
            )
        elif h.addresses_gap_id:
            seen_gaps[h.addresses_gap_id] = h.id

        # Check intervention-level redundancy (simplified: same archetype + similar title)
        key = f"{h.archetype.value}:{h.experiment_spec.dataset}"
        if key in seen_interventions and h.experiment_spec.dataset:
            redundancies.append(
                f"{h.id} and {seen_interventions[key]} use same archetype+dataset: {key}"
            )
        elif h.experiment_spec.dataset:
            seen_interventions[key] = h.id

    return redundancies
