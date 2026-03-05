from __future__ import annotations

from collections import Counter
import re

from hypo_gpt.models import (
    AssumptionTarget,
    Contradiction,
    CrossDomainBridge,
    PaperIntelligence,
    ResearchLandscape,
)


def _detect_domain(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("transformer", "language", "llm", "nlp", "token")):
        return "nlp"
    if any(k in lower for k in ("vision", "image", "cnn", "segmentation")):
        return "cv"
    if any(k in lower for k in ("reinforcement", "policy", "reward", "agent")):
        return "rl"
    if any(k in lower for k in ("protein", "genome", "biolog", "molecule")):
        return "biology"
    return "ml"


def _first_sentence(text: str, fallback: str) -> str:
    chunks = [x.strip() for x in text.replace("\n", " ").split(".") if x.strip()]
    return chunks[0] if chunks else fallback


def _extract_key_phrases(text: str, limit: int = 8) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]{3,}", text.lower())
    stop = {
        "this", "that", "with", "from", "using", "under", "into", "than", "when", "where", "which", "their",
        "model", "models", "paper", "results", "result", "method", "methods", "approach", "approaches",
        "training", "dataset", "performance", "improve", "improves", "improved", "study", "shows", "show",
    }
    counts = Counter(w for w in words if w not in stop)
    return [term for term, _ in counts.most_common(limit)]


class PaperIntelligenceExtractor:
    def extract(self, title: str, text: str, year: int | None = None) -> PaperIntelligence:
        domain = _detect_domain(text)
        claim = _first_sentence(text, f"{title} proposes a new approach.")
        mechanism = _first_sentence(text[180:1800], "The approach combines representation learning and optimization.")
        phrases = _extract_key_phrases(text, limit=10)

        methods: list[str] = []
        if "ablation" in text.lower():
            methods.append("ablation")
        if "benchmark" in text.lower():
            methods.append("benchmark comparison")
        if "retrieval" in text.lower():
            methods.append("retrieval-augmented evaluation")
        if "distillation" in text.lower():
            methods.append("knowledge distillation")
        if "alignment" in text.lower():
            methods.append("alignment-tuning")
        methods = methods or ["ablation", "benchmark comparison", "optimization"]

        open_questions = [
            f"Which mechanism among {', '.join(phrases[:3]) or 'core components'} drives gains?",
            "Do gains persist under out-of-distribution shift?",
            "How sensitive is performance to compute/data budget changes?",
        ]
        untested = ["long-tail distribution", "adversarial or shift stress tests", "low-resource regime"]
        assumptions = [
            "training distribution approximates deployment distribution",
            "evaluation benchmarks reflect real-world performance",
        ]
        explicit_limitations = [
            "limited evaluation breadth",
            "resource assumptions may not generalize",
        ]
        return PaperIntelligence(
            title=title,
            domain=domain,
            subdomain="general",
            year=year,
            central_claim=claim,
            core_mechanism=mechanism,
            key_assumptions=assumptions,
            methods=methods,
            empirical_results=["reported gains on primary benchmark"],
            explicit_limitations=explicit_limitations,
            implicit_limitations=["sensitivity to data shift", "possible hidden confounders"],
            open_questions=open_questions,
            missing_baselines=["latest stronger baseline under identical compute"],
            untested_conditions=untested,
            analogous_domains=["control theory", "economics", "neuroscience"],
            borrowed_concepts=phrases[:3] or ["information bottleneck"],
            exportable_concepts=phrases[3:7] or ["adaptive objective scheduling"],
            confidence_level="preliminary",
            replication_status="single_study",
        )


class LandscapeSynthesizer:
    def synthesize(self, research_intent: str, papers: list[PaperIntelligence]) -> ResearchLandscape:
        if not papers:
            return ResearchLandscape(research_intent=research_intent, bottleneck_hypothesis="insufficient evidence")

        assumptions = Counter(a for paper in papers for a in paper.key_assumptions)
        shared_assumptions = [a for a, c in assumptions.items() if c >= max(1, len(papers) // 2)]

        contested_claims: list[Contradiction] = []
        if len(papers) >= 2:
            for idx in range(len(papers) - 1):
                a, b = papers[idx], papers[idx + 1]
                if a.central_claim != b.central_claim:
                    contested_claims.append(
                        Contradiction(
                            claim="performance attribution mechanism",
                            paper_a=a.title,
                            paper_b=b.title,
                            nature="scope",
                            resolution_hypothesis="effectiveness depends on regime and data conditions",
                        )
                    )

        opportunities = [
            CrossDomainBridge(
                source_domain="control theory",
                target_domain=papers[0].domain,
                analogous_problem="stability under perturbation",
                solved_by="robust feedback control",
                transfer_hypothesis="introduce adaptive stability constraints during optimization",
            )
        ]

        vulnerabilities = [
            AssumptionTarget(
                assumption=item,
                held_by=[p.title for p in papers],
                vulnerability_reason="assumption is rarely stress-tested under deployment shift",
                challenge_hypothesis="relaxing the assumption improves robustness while preserving core accuracy",
            )
            for item in shared_assumptions[:3]
        ]

        domain = papers[0].domain
        return ResearchLandscape(
            research_intent=research_intent,
            intent_domain=domain,
            intent_subdomain="general",
            shared_assumptions=shared_assumptions,
            contested_claims=contested_claims,
            methodological_consensus=list({m for p in papers for m in p.methods})[:6],
            dominant_paradigm="scale existing architectures with incremental optimization refinements",
            established_facts=[p.central_claim for p in papers[:3]],
            open_problems=[q for p in papers for q in p.open_questions][:6],
            pseudoknowledge=["benchmark gains imply broad real-world robustness"],
            cross_domain_opportunities=opportunities,
            assumption_vulnerabilities=vulnerabilities,
            methodological_gaps=["insufficient causal attribution analysis"],
            bottleneck_hypothesis="mechanistic uncertainty under distribution shift",
        )
