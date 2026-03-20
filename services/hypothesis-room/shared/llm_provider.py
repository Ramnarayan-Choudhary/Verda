"""Shared LLM provider with typed JSON handling and retries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """Base provider error."""


class LLMRequestError(LLMProviderError):
    """Raised when a provider request repeatedly fails."""


class LLMParseError(LLMProviderError):
    """Raised when model output cannot be parsed/validated."""


@dataclass(slots=True)
class LLMConfig:
    api_key: str = ""
    default_model: str = "gpt-4o"
    fast_model: str = "gpt-4o-mini"
    timeout_s: int = 45
    max_retries: int = 2
    base_url: str = "https://api.openai.com/v1/chat/completions"


class LLMProvider:
    """Thin async chat-completions wrapper with strict JSON parsing."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def is_configured(self) -> bool:
        return bool(self.config.api_key)

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 1800,
        response_format: dict[str, Any] | None = None,
    ) -> str | None:
        if not self.is_configured:
            return None

        payload: dict[str, Any] = {
            "model": model or self.config.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        last_error: str | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_s) as client:
                    response = await client.post(self.config.base_url, headers=headers, json=payload)
                if response.status_code >= 300:
                    last_error = f"status={response.status_code} body={response.text[:300]}"
                    continue
                data = response.json()
                message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                if isinstance(message, str):
                    return message.strip() or None
                if isinstance(message, list):
                    parts = [item.get("text", "") for item in message if isinstance(item, dict)]
                    joined = " ".join(parts).strip()
                    return joined or None
                return None
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                continue

        raise LLMRequestError(f"LLM request failed after retries: {last_error}")

    async def json_complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2200,
    ) -> dict[str, Any] | None:
        raw = await self.complete(
            messages,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_format={"type": "json_object"},
        )
        if raw is None:
            return None

        cleaned = self._strip_json_fences(raw)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"Invalid JSON payload: {exc}; sample={raw[:180]}") from exc
        if not isinstance(parsed, dict):
            raise LLMParseError("Model output JSON was not an object")
        return parsed

    async def structured_complete(
        self,
        messages: list[dict[str, str]],
        *,
        schema_model: type[T],
        model: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2200,
    ) -> T | None:
        parsed = await self.json_complete(
            messages,
            model=model,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        if parsed is None:
            return None
        try:
            return schema_model.model_validate(parsed)
        except ValidationError as exc:
            raise LLMParseError(f"Schema validation failed for {schema_model.__name__}: {exc}") from exc

    @staticmethod
    def _strip_json_fences(raw: str) -> str:
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
        return text.strip()


def log_llm_parse_error(exc: Exception, *, context: str) -> None:
    logger.warning("shared.llm.parse_error", context=context, error=str(exc))
