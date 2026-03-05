import numpy as np
import pytest

from vreda_hypothesis.knowledge import vector_store
from vreda_hypothesis.knowledge.vector_store import VectorStoreClient


@pytest.mark.asyncio
async def test_vector_store_memory_backend(monkeypatch):
    async def fake_embed(texts):
        return np.array([[float(i + 1)] for i in range(len(texts))], dtype=np.float32)

    monkeypatch.setattr(vector_store, "_embed_texts", fake_embed)
    store = VectorStoreClient()
    assert store._backend == "memory"

    await store.add_chunks("doc", ["alpha hypothesis", "beta insight"])
    results = await store.similarity_search("beta", k=1)
    assert results and results[0]["text"].startswith("beta")
