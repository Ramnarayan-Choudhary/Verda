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


DATASET_PATTERNS = [
    "imagenet",
    "cifar-10",
    "cifar10",
    "cifar-100",
    "cifar100",
    "coco",
    "voc",
    "cityscapes",
    "wikitext",
    "squad",
    "glue",
    "mmlu",
    "librispeech",
]


DOMAIN_ANALOGIES = {
    "cv": ["signal processing", "compressed sensing", "computer graphics"],
    "nlp": ["information retrieval", "computational linguistics", "knowledge organization"],
    "rl": ["control theory", "operations research", "decision science"],
    "biology": ["systems biology", "biophysics", "statistical mechanics"],
    "ml": ["optimization theory", "statistics", "scientific computing"],
}


def _detect_domain(text: str) -> str:
    lower = text.lower()
    keyword_sets = {
        "nlp": ("language", "llm", "nlp", "token", "prompt", "decoder", "instruction"),
        "cv": ("vision", "image", "cnn", "segmentation", "detection", "pixel", "video", "pruning", "sparsity"),
        "rl": ("reinforcement", "policy", "reward", "agent", "environment", "trajectory"),
        "biology": ("protein", "genome", "biolog", "molecule", "cell", "sequence"),
    }
    scores: dict[str, int] = {}
    for domain, keywords in keyword_sets.items():
        score = 0
        for keyword in keywords:
            score += lower.count(keyword)
        scores[domain] = score

    # "transformer" appears in CV and NLP; treat it as weak tie-breaker only.
    if "transformer" in lower:
        scores["nlp"] += 1
        scores["cv"] += 1

    best_domain, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score > 0:
        return best_domain
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
        "present", "visual", "interactive", "propose", "proposed", "novel", "state", "art", "deep", "learning",
        "neural", "network", "networks", "framework", "based",
    }
    filtered = [w for w in words if w not in stop]
    unigram_counts = Counter(filtered)

    bigrams: list[str] = []
    for i in range(len(filtered) - 1):
        first, second = filtered[i], filtered[i + 1]
        if first == second:
            continue
        if len(first) < 4 or len(second) < 4:
            continue
        bigrams.append(f"{first} {second}")
    bigram_counts = Counter(bigrams)

    ranked: list[str] = [phrase for phrase, _ in bigram_counts.most_common(limit)]
    for term, _ in unigram_counts.most_common(limit * 2):
        if len(ranked) >= limit:
            break
        if term not in ranked:
            ranked.append(term)
    return ranked[:limit]


def _extract_datasets(text: str, limit: int = 3) -> list[str]:
    lower = text.lower()
    out: list[str] = []
    for name in DATASET_PATTERNS:
        if name in lower:
            canonical = name.replace("cifar10", "CIFAR-10").replace("cifar100", "CIFAR-100").upper() if "cifar" in name else name
            if canonical not in out:
                out.append(canonical)
        if len(out) >= limit:
            break
    return out


def _extract_methods(text: str) -> list[str]:
    lower = text.lower()
    catalog = [
        ("ablation", "ablation"),
        ("benchmark", "benchmark comparison"),
        ("retrieval", "retrieval-augmented evaluation"),
        ("distillation", "knowledge distillation"),
        ("alignment", "alignment-tuning"),
        ("pruning", "structured pruning"),
        ("sparsity", "sparsity regularization"),
        ("quantization", "quantization"),
        ("fine-tuning", "fine-tuning"),
        ("adapter", "adapter tuning"),
        ("contrastive", "contrastive learning"),
    ]
    methods = [label for token, label in catalog if token in lower]
    if methods:
        return methods[:6]
    return ["ablation", "benchmark comparison", "optimization"]


def _derive_analogous_domains(domain: str, phrases: list[str], methods: list[str]) -> list[str]:
    phrase_text = " ".join(phrases).lower()
    out = list(DOMAIN_ANALOGIES.get(domain, DOMAIN_ANALOGIES["ml"]))
    if "pruning" in phrase_text or any("pruning" in m for m in methods):
        out = ["compressed sensing", "compiler optimization", "signal processing"]
    elif "retrieval" in phrase_text:
        out = ["information retrieval", "graph search", "knowledge systems"]
    elif "control" in phrase_text and domain in {"rl", "robotics"}:
        out = ["control theory", "operations research", "dynamical systems"]
    return out[:3]


class PaperIntelligenceExtractor:
    def extract(self, title: str, text: str, year: int | None = None) -> PaperIntelligence:
        # Bound extraction window for predictable runtime on large PDFs.
        sample = text[:120_000]
        domain = _detect_domain(sample)
        claim = _first_sentence(sample, f"{title} proposes a new approach.")
        mechanism = _first_sentence(sample[180:1800], "The approach combines representation learning and optimization.")
        phrases = _extract_key_phrases(f"{title}. {sample}", limit=10)
        methods = _extract_methods(sample)
        datasets = _extract_datasets(sample)

        key_focus = phrases[0] if phrases else "core model components"
        method_focus = methods[0] if methods else "intervention mechanism"
        dataset_focus = datasets[0] if datasets else "deployment-like shift suites"
        open_questions = [
            f"Which causal mediator drives observed gains in {key_focus} during {method_focus}?",
            f"Do gains persist on {dataset_focus} when evaluated under distribution shift and stress conditions?",
            "How sensitive are reported gains to equal-compute controls and repeated-seed variance?",
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
        analogous_domains = _derive_analogous_domains(domain, phrases, methods)

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
            analogous_domains=analogous_domains,
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
                source_domain=(papers[0].analogous_domains[0] if papers and papers[0].analogous_domains else "optimization theory"),
                target_domain=papers[0].domain,
                analogous_problem="stability under perturbation",
                solved_by="structured control of error amplification",
                transfer_hypothesis="introduce explicit stability constraints and mediator probes during training",
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
            dominant_paradigm="improve benchmark metrics through incremental objective/training refinements",
            established_facts=[f"{p.title}: {p.central_claim}" for p in papers[:3]],
            open_problems=[q for p in papers for q in p.open_questions][:6],
            pseudoknowledge=["benchmark gains imply broad real-world robustness"],
            cross_domain_opportunities=opportunities,
            assumption_vulnerabilities=vulnerabilities,
            methodological_gaps=["insufficient causal attribution analysis"],
            bottleneck_hypothesis="mechanistic uncertainty under distribution shift",
        )
