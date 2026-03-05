"""
GPU Cost Estimation — heuristics-based budget scoring.

Maps hypothesis requirements to estimated GPU costs using RunPod rates.
Used in Stage 4 (filtering) to score budget/feasibility.
"""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger(__name__)

# RunPod GPU rates (USD per hour, on-demand)
GPU_RATES: dict[str, dict] = {
    "a40": {"vram_gb": 48, "rate_per_hr": 0.49, "tflops_fp16": 150},
    "a100_40gb": {"vram_gb": 40, "rate_per_hr": 1.64, "tflops_fp16": 312},
    "a100_80gb": {"vram_gb": 80, "rate_per_hr": 1.99, "tflops_fp16": 312},
    "h100": {"vram_gb": 80, "rate_per_hr": 3.89, "tflops_fp16": 990},
    "l40s": {"vram_gb": 48, "rate_per_hr": 0.74, "tflops_fp16": 362},
    "rtx_4090": {"vram_gb": 24, "rate_per_hr": 0.44, "tflops_fp16": 165},
}

# Model size → VRAM estimate (rough)
MODEL_SIZE_VRAM: dict[str, float] = {
    "tiny": 2.0,       # <500M params
    "small": 4.0,      # 500M-2B params
    "medium": 16.0,    # 2B-7B params
    "large": 40.0,     # 7B-30B params
    "xlarge": 80.0,    # 30B-70B params
    "xxlarge": 160.0,  # 70B+ params
}


def estimate_model_size(text: str) -> str:
    """Heuristically estimate model size from hypothesis text."""
    text_lower = text.lower()

    # Look for explicit parameter counts
    param_match = re.search(r"(\d+(?:\.\d+)?)\s*[bm]\s*param", text_lower)
    if param_match:
        num = float(param_match.group(1))
        unit = "b" if "b" in text_lower[param_match.start():param_match.end()] else "m"
        params_b = num if unit == "b" else num / 1000

        if params_b < 0.5:
            return "tiny"
        if params_b < 2:
            return "small"
        if params_b < 7:
            return "medium"
        if params_b < 30:
            return "large"
        if params_b < 70:
            return "xlarge"
        return "xxlarge"

    # Keyword heuristics
    if any(kw in text_lower for kw in ["distilbert", "mobilenet", "tiny"]):
        return "tiny"
    if any(kw in text_lower for kw in ["gpt-4", "llama-70b", "claude", "palm"]):
        return "xlarge"
    if any(kw in text_lower for kw in ["llama-2", "mistral-7b", "7b", "13b"]):
        return "large"
    if any(kw in text_lower for kw in ["bert", "gpt-2", "t5-base", "resnet"]):
        return "small"

    return "medium"  # Default assumption


def estimate_training_hours(text: str) -> float:
    """Heuristically estimate training hours from hypothesis text."""
    text_lower = text.lower()

    # Look for dataset size hints
    if any(kw in text_lower for kw in ["imagenet", "laion", "million images", "billion"]):
        return 48.0  # Large dataset
    if any(kw in text_lower for kw in ["cifar", "mnist", "small dataset", "fine-tun"]):
        return 4.0   # Small dataset / fine-tuning
    if any(kw in text_lower for kw in ["pretrain", "from scratch"]):
        return 72.0  # Full pretraining
    if any(kw in text_lower for kw in ["inference", "evaluation", "benchmark"]):
        return 1.0   # Just inference

    return 12.0  # Default: moderate training


def select_gpu(vram_needed_gb: float) -> str:
    """Select cheapest GPU that meets VRAM requirement."""
    candidates = [
        (name, info)
        for name, info in GPU_RATES.items()
        if info["vram_gb"] >= vram_needed_gb
    ]
    if not candidates:
        return "h100"  # Fallback to largest

    # Sort by rate, pick cheapest
    candidates.sort(key=lambda x: x[1]["rate_per_hr"])
    return candidates[0][0]


def estimate_budget(hypothesis_text: str) -> dict:
    """Estimate GPU budget for a hypothesis.

    Returns:
        Dict with gpu, hours, cost_usd, breakdown.
    """
    model_size = estimate_model_size(hypothesis_text)
    vram_needed = MODEL_SIZE_VRAM[model_size]
    training_hours = estimate_training_hours(hypothesis_text)
    gpu = select_gpu(vram_needed)
    rate = GPU_RATES[gpu]["rate_per_hr"]
    cost = training_hours * rate

    # Add 20% contingency (matching TS accountant-agent.ts pattern)
    cost_with_contingency = cost * 1.2

    result = {
        "gpu": gpu,
        "vram_gb": GPU_RATES[gpu]["vram_gb"],
        "estimated_hours": training_hours,
        "rate_per_hr": rate,
        "base_cost_usd": round(cost, 2),
        "cost_with_contingency_usd": round(cost_with_contingency, 2),
        "model_size_category": model_size,
    }

    logger.debug(
        "cost.estimate",
        model_size=model_size,
        gpu=gpu,
        hours=training_hours,
        cost=cost_with_contingency,
    )
    return result
