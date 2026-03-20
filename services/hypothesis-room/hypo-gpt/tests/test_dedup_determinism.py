import numpy as np

from shared.dedup import compute_embeddings


def test_fallback_embeddings_are_deterministic() -> None:
    texts = [
        "Causal mediator controls robustness drift.",
        "Ablation confirms mechanism under equal compute.",
    ]
    first = compute_embeddings(texts)
    second = compute_embeddings(texts)
    assert np.allclose(first, second)
