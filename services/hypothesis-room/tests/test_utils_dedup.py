import numpy as np

from vreda_hypothesis.utils import dedup


def test_deduplicate_by_cosine_returns_subset(monkeypatch):
    # Patch embeddings to deterministic values to avoid loading transformer
    monkeypatch.setattr(
        dedup,
        "compute_embeddings",
        lambda texts, batch_size=64: np.array(
            [
                [1.0, 0.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=float,
        ),
    )
    texts = ["A hypothesis", "A hypothesis", "Another idea"]
    unique, indices = dedup.deduplicate_by_cosine(texts, threshold=0.8)
    assert unique == ["A hypothesis", "Another idea"]
    assert indices == [0, 2]
