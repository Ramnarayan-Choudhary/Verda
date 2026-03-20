"""OpenAI Responses API web-search client for shared literature grounding."""

from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

import httpx
import structlog

from shared.external.types import WebSearchResult

logger = structlog.get_logger(__name__)
_MAX_QUERY_CHARS = 280


class OpenAIWebSearchClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_s: int = 35,
        context_size: str = "medium",
        max_results: int = 4,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._context_size = context_size
        self._max_results = max_results
        self._client = http_client or httpx.AsyncClient(timeout=float(timeout_s))
        self._preferred_tool_type: str | None = None
        self._domain_filters_supported = True

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        allowed_domains: list[str] | None = None,
    ) -> list[WebSearchResult]:
        if not self.is_configured:
            return []

        normalized_query = _normalize_query(query)
        if not normalized_query:
            return []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        attempts: list[dict[str, Any]] = [
            {"tool_type": "web_search", "include_sources": True, "use_reasoning": False, "use_filters": bool(allowed_domains)},
            {"tool_type": "web_search_2025_08_26", "include_sources": True, "use_reasoning": False, "use_filters": bool(allowed_domains)},
            {"tool_type": "web_search_preview", "include_sources": False, "use_reasoning": False, "use_filters": False},
            {"tool_type": "web_search_preview_2025_03_11", "include_sources": False, "use_reasoning": False, "use_filters": False},
        ]
        if self._preferred_tool_type:
            attempts.sort(key=lambda item: 0 if item["tool_type"] == self._preferred_tool_type else 1)

        payload_data: dict[str, Any] | None = None
        failures: list[dict[str, Any]] = []
        for idx, attempt in enumerate(attempts, start=1):
            use_filters = attempt["use_filters"] and self._domain_filters_supported
            payload = _build_payload(
                model=self._model,
                query=normalized_query,
                context_size=self._context_size,
                tool_type=attempt["tool_type"],
                include_sources=attempt["include_sources"],
                use_reasoning=attempt["use_reasoning"],
                allowed_domains=allowed_domains if use_filters else None,
            )
            try:
                resp = await self._client.post(f"{self._base_url}/responses", headers=headers, json=payload)
                resp.raise_for_status()
                payload_data = resp.json()
                self._preferred_tool_type = attempt["tool_type"]
                break
            except httpx.HTTPStatusError as exc:
                body_excerpt = exc.response.text[:260]
                if exc.response.status_code == 400 and ("allowed_domains" in body_excerpt or "filters" in body_excerpt):
                    self._domain_filters_supported = False
                failures.append(
                    {
                        "attempt": idx,
                        "tool_type": attempt["tool_type"],
                        "status_code": exc.response.status_code,
                        "body_excerpt": body_excerpt,
                    }
                )
                continue
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "attempt": idx,
                        "tool_type": attempt["tool_type"],
                        "status_code": None,
                        "body_excerpt": str(exc)[:260],
                    }
                )
                continue

        if not payload_data:
            for failure in failures:
                logger.warning(
                    "shared.openai_web_search.error",
                    attempt=failure["attempt"],
                    tool_type=failure["tool_type"],
                    status_code=failure["status_code"],
                    body_excerpt=failure["body_excerpt"],
                    query=normalized_query[:80],
                )
            return []
        if failures:
            logger.info(
                "shared.openai_web_search.fallback_used",
                query=normalized_query[:80],
                failures=len(failures),
                chosen_tool_type=self._preferred_tool_type,
                domain_filters_supported=self._domain_filters_supported,
            )

        summary_text = _extract_output_text(payload_data)
        sources = _extract_sources(payload_data)
        return _normalize_results(
            sources=sources,
            summary_text=summary_text,
            max_results=max_results or self._max_results,
        )

    async def close(self) -> None:
        await self._client.aclose()


def _normalize_query(query: str) -> str:
    cleaned = " ".join((query or "").split()).strip()
    cleaned = re.sub(r"vreda_hyp_[a-z0-9_-]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b[0-9a-f]{24,}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip()
    if len(cleaned) > _MAX_QUERY_CHARS:
        cleaned = cleaned[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0]
    return cleaned


def _build_payload(
    *,
    model: str,
    query: str,
    context_size: str,
    tool_type: str,
    include_sources: bool,
    use_reasoning: bool,
    allowed_domains: list[str] | None,
) -> dict[str, Any]:
    tool_config: dict[str, Any] = {"type": tool_type}
    if "web_search" in tool_type:
        tool_config["search_context_size"] = context_size
    if allowed_domains and tool_type.startswith("web_search") and "preview" not in tool_type:
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
    *,
    sources: list[dict[str, Any]],
    summary_text: str,
    max_results: int,
) -> list[WebSearchResult]:
    normalized: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    for source in sources:
        url = source.get("url")
        if not isinstance(url, str):
            url = ""
        dedup_key = url.strip().lower()
        if dedup_key and dedup_key in seen_urls:
            continue
        if dedup_key:
            seen_urls.add(dedup_key)

        title = source.get("title")
        if not isinstance(title, str) or not title.strip():
            title = _title_from_url(url)
        snippet = source.get("snippet")
        if not isinstance(snippet, str) or not snippet.strip():
            snippet = source.get("text")
        if not isinstance(snippet, str) or not snippet.strip():
            snippet = (summary_text[:420] + "...") if len(summary_text) > 420 else summary_text

        normalized.append(
            WebSearchResult(
                title=title or "OpenAI web result",
                url=url,
                content=snippet or "No snippet returned",
                source="openai_web_search",
            )
        )
        if len(normalized) >= max_results:
            break

    if normalized:
        return normalized
    if summary_text.strip():
        return [WebSearchResult(title="OpenAI web synthesis", content=summary_text, source="openai_web_search")]
    return []


def _title_from_url(url: str) -> str:
    if not url:
        return "Web source"
    try:
        host = urlparse(url).netloc
        return host or "Web source"
    except Exception:
        return "Web source"
