import pytest

from hypo_gpt.models import GenerateRequest, InputDocument
from hypo_gpt.pipeline import HypothesisPipeline


@pytest.mark.asyncio
async def test_pipeline_generates_output() -> None:
    pipeline = HypothesisPipeline()
    request = GenerateRequest(
        research_intent="Improve robustness in LLMs",
        input_documents=[
            InputDocument(
                type="text",
                title="Paper A",
                text="This transformer paper improves benchmark scores but has limited robustness testing.",
            ),
            InputDocument(
                type="text",
                title="Paper B",
                text="A second study reports gains under compute constraints with incomplete mechanism explanation.",
            ),
        ],
    )

    output = await pipeline.run(request)
    assert output.engine_used == "gpt"
    assert len(output.hypotheses) >= 1
    assert output.gap_analysis_used is True
