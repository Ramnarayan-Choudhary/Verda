import pytest

from hypo_gpt.models import GenerateRequest, InputDocument, PipelineConfig
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


@pytest.mark.asyncio
async def test_pipeline_supports_v2_output_schema() -> None:
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
        config=PipelineConfig(output_schema="v2", enable_memory=False),
    )

    output = await pipeline.run(request)
    assert output.engine_used == "gpt"
    assert len(output.hypotheses) >= 1
    assert len(output.panel_verdicts) >= 1


@pytest.mark.asyncio
async def test_legacy_output_uses_v2_selected_hypotheses_when_available() -> None:
    pipeline = HypothesisPipeline()
    request = GenerateRequest(
        research_intent="Generate falsifiable CV hypotheses for pruning under deployment shift.",
        input_documents=[
            InputDocument(
                type="text",
                title="Paper A",
                text="Vision transformer pruning improves image metrics but has limited ablation and weak deployment stress testing.",
            ),
        ],
        config=PipelineConfig(output_schema="legacy", top_k=4, domain_hint="cv"),
    )

    output = await pipeline.run(request)
    assert output.engine_used == "gpt"
    assert len(output.hypotheses) >= 3
    assert any(h.id.startswith("hyp2-") for h in output.hypotheses)
