from __future__ import annotations

import re

from hypo_gpt.models import HypothesisV2, ResearchLandscape

NOVELTY_PROMPT = "Score novelty 0.0-1.0 and name closest prior work before scoring."
FEASIBILITY_PROMPT = "Score feasibility 0.0-1.0; penalize unknown/non-public data by 0.3."
MECHANISM_PROMPT = "Score mechanism coherence 0.0-1.0 for causal logic completeness."
EXEC_PROMPT = "Score executability 0.0-1.0 from implementation clarity and infra risk."


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())}


def _parse_compute(compute_estimate: str) -> tuple[int, int]:
    text = compute_estimate.lower()
    gpus = 0
    hours = 0
    m_gpu = re.search(r"(\d+)\s*x\s*[a-z0-9]+", text)
    if m_gpu:
        gpus = int(m_gpu.group(1))
    m_hours = re.search(r"(\d+)\s*h", text)
    if m_hours:
        hours = int(m_hours.group(1))
    return gpus, hours


def _specificity_bonus(text: str) -> float:
    lowered = text.lower()
    bonus = 0.0
    if re.search(r"\d", text):
        bonus += 0.04
    if any(token in lowered for token in ("ablation", "equal-compute", "stress", "shift", "baseline")):
        bonus += 0.06
    if any(token in lowered for token in ("mediator", "causal", "confound", "counterfactual")):
        bonus += 0.06
    if any(token in lowered for token in ("state-of-the-art", "improves performance", "general optimization")):
        bonus -= 0.08
    return bonus


def compute_composite_score(
    novelty: float,
    feasibility: float,
    mechanism_coherence: float,
    executability: float,
    strategy: str,
) -> float:
    weights = {
        "gap_fill": dict(n=0.25, f=0.35, m=0.20, e=0.20),
        "cross_domain": dict(n=0.40, f=0.20, m=0.25, e=0.15),
        "assumption_challenge": dict(n=0.30, f=0.20, m=0.35, e=0.15),
        "method_recomb": dict(n=0.25, f=0.25, m=0.25, e=0.25),
        "failure_inversion": dict(n=0.30, f=0.25, m=0.25, e=0.20),
        "abductive": dict(n=0.35, f=0.20, m=0.35, e=0.10),
        "constraint_relax": dict(n=0.30, f=0.30, m=0.20, e=0.20),
    }
    chosen = weights.get(strategy, dict(n=0.25, f=0.25, m=0.25, e=0.25))
    raw = (
        chosen["n"] * novelty
        + chosen["f"] * feasibility
        + chosen["m"] * mechanism_coherence
        + chosen["e"] * executability
    )
    if min(novelty, feasibility, mechanism_coherence) < 0.3:
        return min(0.5, raw)
    return raw


def score_hypothesis_fast(hypothesis: HypothesisV2, landscape: ResearchLandscape) -> HypothesisV2:
    strategy_bonus = {
        "cross_domain": 0.10,
        "constraint_relax": 0.08,
        "method_recomb": 0.06,
        "abductive": 0.07,
    }.get(hypothesis.strategy, 0.03)

    landscape_tokens = _tokenize(" ".join(landscape.established_facts[:5] + landscape.open_problems[:5]))
    hypo_tokens = _tokenize(
        f"{hypothesis.title} {hypothesis.problem_being_solved} {hypothesis.core_claim} "
        f"{hypothesis.causal_chain.intermediate}"
    )
    overlap_ratio = (len(hypo_tokens & landscape_tokens) / max(1, len(hypo_tokens)))
    novelty = _clip01(0.53 + strategy_bonus - (0.20 * overlap_ratio) + _specificity_bonus(hypothesis.title))

    gpus, hours = _parse_compute(hypothesis.experiment.compute_estimate)
    compute_penalty = 0.0
    if gpus >= 8:
        compute_penalty += 0.18
    elif gpus >= 4:
        compute_penalty += 0.10
    elif gpus > 0:
        compute_penalty += 0.04
    if hours >= 72:
        compute_penalty += 0.10
    elif hours >= 24:
        compute_penalty += 0.05

    feasibility = 0.68
    if "public" in hypothesis.experiment.required_data.lower():
        feasibility += 0.08
    if "equal-compute" in hypothesis.experiment.baseline.lower():
        feasibility += 0.04
    feasibility += _specificity_bonus(hypothesis.experiment.design)
    feasibility = _clip01(feasibility - compute_penalty)

    intermediate_words = len(hypothesis.causal_chain.intermediate.split())
    mechanism_signals = [
        "mediator",
        "causal",
        "ablation",
        "confound",
        "intervention",
    ]
    signal_hits = sum(1 for signal in mechanism_signals if signal in hypothesis.causal_chain.intermediate.lower())
    mechanism = _clip01(0.40 + (0.012 * min(intermediate_words, 28)) + (0.04 * signal_hits) + _specificity_bonus(hypothesis.causal_chain.intermediate))

    exec_features = 0.0
    design_text = hypothesis.experiment.design.lower()
    if "ablation" in design_text:
        exec_features += 0.10
    if "stress" in design_text or "shift" in design_text:
        exec_features += 0.06
    if "baseline" in hypothesis.experiment.baseline.lower():
        exec_features += 0.08
    if re.search(r"\d", hypothesis.falsification_criterion):
        exec_features += 0.08
    executability = _clip01(0.50 + exec_features + _specificity_bonus(hypothesis.falsification_criterion) - (0.25 * compute_penalty))

    hypothesis.novelty = round(novelty, 4)
    hypothesis.feasibility = round(feasibility, 4)
    hypothesis.mechanism_coherence = round(mechanism, 4)
    hypothesis.executability = round(executability, 4)
    hypothesis.composite_score = round(
        compute_composite_score(
            hypothesis.novelty,
            hypothesis.feasibility,
            hypothesis.mechanism_coherence,
            hypothesis.executability,
            hypothesis.strategy,
        ),
        4,
    )
    return hypothesis
