from __future__ import annotations

import numpy as np
import pytest

from shared import vector_store as module
from shared.vector_store import VectorStoreClient


@pytest.mark.asyncio
async def test_vector_store_add_and_search(monkeypatch) -> None:
    async def fake_embed(texts):
        vectors = []
        for idx, _ in enumerate(texts):
            v = np.zeros(384, dtype=np.float32)
            v[idx % 384] = 1.0
            vectors.append(v)
        return np.asarray(vectors, dtype=np.float32)

    monkeypatch.setattr(module, "_embed_texts", fake_embed)

    store = VectorStoreClient()
    await store.add_chunks("doc", ["alpha", "beta"])
    results = await store.similarity_search("alpha", k=2)
    assert len(results) == 2
