from __future__ import annotations

import httpx
import pytest

from shared.external.arxiv import ArxivClient
from shared.external.semantic_scholar import SemanticScholarClient


@pytest.mark.asyncio
async def test_arxiv_search_parses_entries() -> None:
    xml_payload = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry>
        <id>http://arxiv.org/abs/2401.12345v1</id>
        <title>Test Paper</title>
        <summary>Abstract text</summary>
        <published>2024-01-20T00:00:00Z</published>
        <author><name>Author One</name></author>
      </entry>
    </feed>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml_payload)

    client = ArxivClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    results = await client.search("test", max_results=1)
    assert len(results) == 1
    assert results[0].title == "Test Paper"
    await client.close()


@pytest.mark.asyncio
async def test_semantic_scholar_keyword_search() -> None:
    payload = {
        "data": [
            {
                "paperId": "abc",
                "title": "S2 Paper",
                "abstract": "A",
                "year": 2023,
                "authors": [{"name": "A"}],
                "externalIds": {"ArXiv": "2301.00001"},
                "citationCount": 10,
                "url": "https://example.com",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = SemanticScholarClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    results = await client.keyword_search("test", limit=1)
    assert len(results) == 1
    assert results[0].title == "S2 Paper"
    await client.close()
