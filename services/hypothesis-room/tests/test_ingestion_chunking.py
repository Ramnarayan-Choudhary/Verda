from vreda_hypothesis.stages.ingestion import _chunk_text


def test_chunk_text_overlap():
    text = " ".join(str(i) for i in range(500))
    chunks = _chunk_text(text, chunk_size=50, overlap=10)
    assert chunks
    assert all(len(chunk.split()) <= 50 for chunk in chunks)
    # Check overlap by ensuring consecutive chunks share tokens
    if len(chunks) > 1:
        assert chunks[0].split()[-10:] == chunks[1].split()[:10]
