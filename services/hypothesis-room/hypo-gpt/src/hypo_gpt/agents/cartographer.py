from __future__ import annotations

from collections import Counter

from hypo_gpt.models import GapAnalysis, ResearchLandscape, ResearchSpaceMap


DEFAULT_CROSS_DOMAIN_BY_TARGET = {
    "cv": "signal processing",
    "nlp": "information retrieval",
    "rl": "control theory",
    "biology": "systems biology",
    "ml": "optimization theory",
}


class GapAnalyst:
    def map(self, landscape: ResearchLandscape) -> ResearchSpaceMap:
        source_titles = [item for item in landscape.established_facts if item][:3] or ["landscape_synthesis"]
        open_problem_raw = landscape.open_problems[0] if landscape.open_problems else "generalization under shift"
        lowered_problem = open_problem_raw.lower().strip()
        if lowered_problem.startswith("which ") or "which mechanism among" in lowered_problem:
            open_problem = landscape.bottleneck_hypothesis or "causal mechanism under deployment shift"
        else:
            open_problem = open_problem_raw
        shared_assumption = (
            landscape.shared_assumptions[0]
            if landscape.shared_assumptions
            else "benchmark gains transfer directly to deployment robustness"
        )
        cross_domain_hint = (
            landscape.cross_domain_opportunities[0].source_domain
            if landscape.cross_domain_opportunities
            else DEFAULT_CROSS_DOMAIN_BY_TARGET.get(landscape.intent_domain, "optimization theory")
        )
        bottleneck = landscape.bottleneck_hypothesis or "missing mechanism-level explanation"
        method_consensus = landscape.methodological_consensus[0] if landscape.methodological_consensus else "benchmark comparison"
        contested = (
            landscape.contested_claims[0].claim
            if landscape.contested_claims
            else "performance attribution mechanism"
        )

        knowledge = [
            GapAnalysis(
                gap_type="knowledge",
                statement=f"Mechanistic attribution gap for '{open_problem}' under deployment conditions",
                why_it_matters="Model selection fails when evaluation evidence does not isolate true causal contributors.",
                expected_impact="high",
                nearest_prior_work="Current benchmarks overweight IID splits and short-horizon tests",
                source_papers=source_titles,
            ),
            GapAnalysis(
                gap_type="knowledge",
                statement=f"Conflicting evidence around '{contested}' across evaluation regimes",
                why_it_matters="Without reconciliation, gains may be irreproducible or context-bound.",
                expected_impact="medium",
                nearest_prior_work="Single-paper conclusions without cross-regime replication",
                source_papers=source_titles,
            ),
        ]
        method = [
            GapAnalysis(
                gap_type="method",
                statement=(
                    f"Transfer {cross_domain_hint.title()} principles into "
                    f"{landscape.intent_domain} training under deployment shift with equal-compute controls"
                ),
                why_it_matters="Can improve stability and reduce variance under perturbations while remaining falsifiable.",
                expected_impact="high",
                nearest_prior_work=f"{method_consensus} with ad-hoc regularization",
                source_papers=source_titles,
                cross_domain_hint=cross_domain_hint,
            ),
            GapAnalysis(
                gap_type="method",
                statement="Factorized ablation protocol to isolate claimed causal components",
                why_it_matters="Mechanism claims stay weak without factorized ablations.",
                expected_impact="high",
                nearest_prior_work="End-to-end comparisons without causal decomposition",
                source_papers=source_titles,
            ),
        ]
        assumption = [
            GapAnalysis(
                gap_type="assumption",
                statement=f"Assumption '{shared_assumption}' may fail under deployment shift",
                why_it_matters="Unverified assumptions inflate confidence and hide failure modes.",
                expected_impact="paradigm_shift",
                nearest_prior_work="Benchmark-centric model selection pipelines",
                source_papers=source_titles,
            )
        ]
        theoretical = [
            GapAnalysis(
                gap_type="theoretical",
                statement=f"Unresolved theoretical bottleneck: {bottleneck}",
                why_it_matters="Without mechanism-level theory, observed gains are difficult to transfer or trust.",
                expected_impact="high",
                nearest_prior_work="Post-hoc attribution and weakly constrained theory",
                source_papers=source_titles,
            )
        ]

        all_gaps = knowledge + method + assumption + theoretical
        high_value_targets = [g.gap_id for g in sorted(all_gaps, key=lambda x: x.expected_impact != "paradigm_shift")[:5]]
        evidence_density = min(1.0, 0.2 + 0.1 * len(Counter(landscape.established_facts + landscape.methodological_consensus)))

        failed_approaches = list(landscape.pseudoknowledge[:3])
        if not failed_approaches:
            failed_approaches = ["Benchmark-centric optimization fails to generalize under shift."]

        return ResearchSpaceMap(
            knowledge_gaps=knowledge,
            method_gaps=method,
            assumption_gaps=assumption,
            theoretical_gaps=theoretical,
            high_value_targets=high_value_targets,
            contestable_assumptions=landscape.assumption_vulnerabilities,
            cross_domain_bridges=landscape.cross_domain_opportunities,
            sota_ceiling_statement=landscape.theoretical_upper_bound or "Current SOTA plateaus under realistic constraints.",
            sota_structural_reason=landscape.bottleneck_hypothesis or "Mechanistic uncertainty under shift.",
            sota_break_condition="Identify causal mediator and validate under equal-compute ablation.",
            failed_approaches_analysis=failed_approaches,
            evidence_density=evidence_density,
        )
