import math

from vreda_hypothesis.utils.cost import estimate_budget, estimate_model_size, estimate_training_hours


def test_estimate_model_size_detects_large_models():
    assert estimate_model_size("We fine-tune a 70B parameter model") == "xxlarge"
    assert estimate_model_size("distilbert variant") == "tiny"


def test_estimate_training_hours_keywords():
    assert estimate_training_hours("pretrain from scratch on Imagenet") >= 48
    assert estimate_training_hours("benchmark inference only") == 1.0


def test_estimate_budget_shapes():
    budget = estimate_budget("Fine-tune a 7B model on ImageNet for 48 hours")
    assert budget["gpu"] in {"a100_80gb", "a40", "h100", "l40s", "rtx_4090"}
    assert math.isclose(budget["cost_with_contingency_usd"], budget["base_cost_usd"] * 1.2, rel_tol=1e-3)
