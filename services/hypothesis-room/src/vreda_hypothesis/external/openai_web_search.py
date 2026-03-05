"""
OpenAI Responses API web-search client.

Uses an existing OPENAI_API_KEY to run web retrieval during Stage 2 grounding.
"""

from __future__ import annotations

from urllib.parse import urlparse
from typing import Any

import httpx
import structlog

from vreda_hypothesis.config import settings

logger = structlog.get_logger(__name__)
_MAX_QUERY_CHARS = 280


class OpenAIWebSearchClient:
    """Async OpenAI web-search wrapper for literature retrieval."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or settings.openai.api_key
        self._base_url = (base_url or settings.openai.base_url or "https://api.openai.com/v1").rstrip("/")
        self._model = model or settings.openai.websearch_model or settings.openai.model
        self._max_results = settings.openai.websearch_max_results
        self._context_size = settings.openai.websearch_context_size
        timeout = settings.openai.websearch_timeout_s
        self._client = http_client or httpx.AsyncClient(timeout=timeout)

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        max_results: int | None = None,
        allowed_domains: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search the web via OpenAI Responses API and normalize result snippets."""
        if not self._api_key:
            logger.debug("openai_web_search.not_configured")
            return []

        query = _normalize_query(query)
        if not query:
            return []
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        # Retry with progressively simpler payloads because different OpenAI deployments
        # can enforce slightly different tool contracts.
        attempts: list[dict[str, Any]] = [
            {
                "tool_type": "web_search",
                "include_sources": True,
                "use_reasoning": True,
                "use_filters": bool(allowed_domains),
            },
            {
                "tool_type": "web_search",
                "include_sources": False,
                "use_reasoning": False,
                "use_filters": False,
            },
            {
                "tool_type": "web_search_preview",
                "include_sources": False,
                "use_reasoning": False,
                "use_filters": False,
            },
        ]

        data: dict[str, Any] | None = None
        for idx, attempt in enumerate(attempts, start=1):
            payload = _build_payload(
                model=self._model,
                query=query,
                context_size=self._context_size,
                tool_type=attempt["tool_type"],
                include_sources=attempt["include_sources"],
                use_reasoning=attempt["use_reasoning"],
                allowed_domains=allowed_domains if attempt["use_filters"] else None,
            )
            try:
                resp = await self._client.post(
                    f"{self._base_url}/responses",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                break
            except httpx.HTTPStatusError as exc:
                body = ""
                try:
                    body = exc.response.text[:400]
                except Exception:
                    body = ""
                logger.warning(
                    "openai_web_search.http_error",
                    query=query[:80],
                    status=exc.response.status_code,
                    attempt=idx,
                    tool_type=attempt["tool_type"],
                    body_excerpt=body,
                )
                continue
            except Exception as exc:
                logger.warning(
                    "openai_web_search.error",
                    query=query[:80],
                    attempt=idx,
                    tool_type=attempt["tool_type"],
                    error=str(exc),
                )
                continue

        if not data:
            return []

        summary_text = _extract_output_text(data)
        sources = _extract_sources(data)
        normalized = _normalize_results(
            sources=sources,
            summary_text=summary_text,
            max_results=max_results or self._max_results,
        )
        logger.info(
            "openai_web_search.complete",
            query=query[:80],
            sources=len(sources),
            returned=len(normalized),
            sample_urls=[item.get("url", "") for item in normalized[:3]],
        )
        return normalized

    async def close(self) -> None:
        await self._client.aclose()


def _extract_output_text(payload: dict[str, Any]) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    output = payload.get("output")
    if not isinstance(output, list):
        return ""

    fragments: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            candidate = block.get("text")
            if isinstance(candidate, str) and candidate.strip():
                fragments.append(candidate.strip())
    return " ".join(fragments).strip()


def _normalize_query(query: str) -> str:
    cleaned = " ".join((query or "").split()).strip()
    if len(cleaned) > _MAX_QUERY_CHARS:
        cleaned = cleaned[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0]
    return cleaned


def _build_payload(
    model: str,
    query: str,
    context_size: str,
    tool_type: str,
    include_sources: bool,
    use_reasoning: bool,
    allowed_domains: list[str] | None,
) -> dict[str, Any]:
    tool_config: dict[str, Any] = {"type": tool_type}
    if tool_type == "web_search":
        tool_config["search_context_size"] = context_size
    if allowed_domains and tool_type == "web_search":
        tool_config["filters"] = {"allowed_domains": allowed_domains[:100]}

    payload: dict[str, Any] = {
        "model": model,
        "tools": [tool_config],
        "input": query,
    }
    if use_reasoning:
        payload["reasoning"] = {"effort": "low"}
    if include_sources:
        payload["include"] = ["web_search_call.action.sources"]
    return payload


def _extract_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            sources = node.get("sources")
            if isinstance(sources, list):
                for source in sources:
                    if isinstance(source, dict):
                        collected.append(source)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(payload)
    return collected


def _normalize_results(
    sources: list[dict[str, Any]],
    summary_text: str,
    max_results: int,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in sources:
        url = source.get("url")
        if not isinstance(url, str):
            url = ""
        key = url.strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)

        title = source.get("title")
        if not isinstance(title, str) or not title.strip():
            title = _title_from_url(url)
        snippet = source.get("snippet")
        if not isinstance(snippet, str) or not snippet.strip():
            snippet = source.get("text")
        if not isinstance(snippet, str) or not snippet.strip():
            snippet = (summary_text[:420] + "...") if len(summary_text) > 420 else summary_text

        normalized.append(
            {
                "title": title or "OpenAI web result",
                "url": url,
                "content": snippet or "No snippet returned",
            }
        )
        if len(normalized) >= max_results:
            break

    if normalized:
        return normalized

    if summary_text.strip():
        return [
            {
                "title": "OpenAI web synthesis",
                "url": "",
                "content": summary_text.strip(),
            }
        ][:max_results]

    return []


def _title_from_url(url: str) -> str:
    if not url:
        return "Web source"
    try:
        host = urlparse(url).netloc
        return host or "Web source"
    except Exception:
        return "Web source"
