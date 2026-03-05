from __future__ import annotations

from hypo_gpt.models import GapAnalysis, ResearchLandscape, ResearchSpaceMap


class GapAnalyst:
    def map(self, landscape: ResearchLandscape) -> ResearchSpaceMap:
        source_titles = [item for item in landscape.established_facts if item][:3] or ["landscape_synthesis"]
        open_problem = (landscape.open_problems[0] if landscape.open_problems else "generalization under shift")
        shared_assumption = (
            landscape.shared_assumptions[0]
            if landscape.shared_assumptions
            else "benchmark gains transfer directly to deployment robustness"
        )
        cross_domain_hint = (
            landscape.cross_domain_opportunities[0].source_domain
            if landscape.cross_domain_opportunities
            else "control theory"
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
                statement=f"Evidence on '{open_problem}' is sparse under realistic deployment regimes.",
                why_it_matters="Model selection fails when evaluation does not match deployment distribution.",
                expected_impact="high",
                nearest_prior_work="Current benchmarks overweight IID splits and short-horizon tests",
                source_papers=source_titles,
            ),
            GapAnalysis(
                gap_type="knowledge",
                statement=f"Conflicting reports around '{contested}' are not reconciled with controlled experiments.",
                why_it_matters="Without reconciliation, gains may be irreproducible or context-bound.",
                expected_impact="medium",
                nearest_prior_work="Single-paper conclusions without cross-regime replication",
                source_papers=source_titles,
            ),
        ]
        method = [
            GapAnalysis(
                gap_type="method",
                statement=f"{cross_domain_hint.title()} techniques are underused in {landscape.intent_domain} training loops.",
                why_it_matters="Could improve stability and reduce variance under perturbations.",
                expected_impact="high",
                nearest_prior_work=f"{method_consensus} with ad-hoc regularization",
                source_papers=source_titles,
                cross_domain_hint=cross_domain_hint,
            ),
            GapAnalysis(
                gap_type="method",
                statement="Ablation protocols rarely isolate the claimed causal component.",
                why_it_matters="Mechanism claims stay weak without factorized ablations.",
                expected_impact="high",
                nearest_prior_work="End-to-end comparisons without causal decomposition",
                source_papers=source_titles,
            ),
        ]
        assumption = [
            GapAnalysis(
                gap_type="assumption",
                statement=f"Many methods assume '{shared_assumption}' without stress-testing boundary conditions.",
                why_it_matters="Unverified assumptions inflate confidence and hide failure modes.",
                expected_impact="paradigm_shift",
                nearest_prior_work="Benchmark-centric model selection pipelines",
                source_papers=source_titles,
            )
        ]
        theoretical = [
            GapAnalysis(
                gap_type="theoretical",
                statement=f"{bottleneck} remains unresolved by current analyses.",
                why_it_matters="Without mechanism-level theory, scaling gains are hard to transfer.",
                expected_impact="high",
                nearest_prior_work="Post-hoc attribution and weakly constrained theory",
                source_papers=source_titles,
            )
        ]

        all_gaps = knowledge + method + assumption + theoretical
        high_value_targets = [g.gap_id for g in sorted(all_gaps, key=lambda x: x.expected_impact != "paradigm_shift")[:5]]

        return ResearchSpaceMap(
            knowledge_gaps=knowledge,
            method_gaps=method,
            assumption_gaps=assumption,
            theoretical_gaps=theoretical,
            high_value_targets=high_value_targets,
        )
