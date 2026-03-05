"""Unit tests for OpenAI web-search client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from vreda_hypothesis.external.openai_web_search import OpenAIWebSearchClient


class _MockResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class _MockHTTPClient:
    def __init__(self, response_payload: dict[str, Any]) -> None:
        self.response_payload = response_payload
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, Any]):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _MockResponse(self.response_payload)

    async def aclose(self) -> None:
        return None


class _SequencedHTTPClient:
    def __init__(self, responses: list[_MockResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, Any]):
        self.calls.append({"url": url, "json": json, "headers": headers})
        response = self.responses.pop(0)
        if response.status_code >= 400:
            request = httpx.Request("POST", url)
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=request,
                response=httpx.Response(response.status_code, request=request, text='{"error":"bad request"}'),
            )
        return response

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_openai_web_search_returns_empty_without_api_key() -> None:
    client = OpenAIWebSearchClient(api_key="", http_client=_MockHTTPClient({}))
    result = await client.search("transformer sparse attention")
    assert result == []


@pytest.mark.asyncio
async def test_openai_web_search_normalizes_sources() -> None:
    mock_payload = {
        "output_text": "Sparse attention variants improve memory under long context.",
        "output": [
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {"title": "Longformer", "url": "https://arxiv.org/abs/2004.05150"},
                        {"title": "BigBird", "url": "https://arxiv.org/abs/2007.14062"},
                    ]
                },
            }
        ],
    }
    http_client = _MockHTTPClient(mock_payload)
    client = OpenAIWebSearchClient(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="o4-mini",
        http_client=http_client,
    )
    results = await client.search(
        "long context sparse attention benchmarks",
        max_results=2,
        allowed_domains=["arxiv.org"],
    )

    assert len(results) == 2
    assert results[0]["title"] == "Longformer"
    assert results[0]["url"] == "https://arxiv.org/abs/2004.05150"
    assert "Sparse attention variants" in results[0]["content"]

    assert len(http_client.calls) == 1
    payload = http_client.calls[0]["json"]
    assert payload["model"] == "o4-mini"
    assert payload["tools"][0]["type"] == "web_search"
    assert payload["tools"][0]["filters"]["allowed_domains"] == ["arxiv.org"]


@pytest.mark.asyncio
async def test_openai_web_search_retries_with_simpler_payload() -> None:
    ok_payload = {
        "output_text": "result summary",
        "output": [{"type": "web_search_call", "action": {"sources": [{"title": "A", "url": "https://arxiv.org/abs/1"}]}}],
    }
    http_client = _SequencedHTTPClient(
        responses=[
            _MockResponse({}, status_code=400),
            _MockResponse(ok_payload, status_code=200),
        ]
    )
    client = OpenAIWebSearchClient(api_key="test-key", http_client=http_client)
    results = await client.search("test query", allowed_domains=["arxiv.org"])

    assert len(results) == 1
    assert len(http_client.calls) == 2
    # Second attempt should simplify payload and remove include/filters.
    second_payload = http_client.calls[1]["json"]
    assert "include" not in second_payload
    assert "reasoning" not in second_payload
    assert "filters" not in second_payload["tools"][0]
