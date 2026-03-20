"""GPT provider facade with OpenAI JSON support and deterministic fallback."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
from typing import Any

import httpx
import structlog

from hypo_gpt.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class LLMProvider:
    """Lightweight provider wrapper.

    This implementation intentionally favors deterministic local behavior so the
    service remains usable even when external model credentials are missing.
    """

    model: str = settings.openai.model

    @staticmethod
    def _coerce_message_content(message: Any) -> str:
        if isinstance(message, list):
            parts = [item.get("text", "") for item in message if isinstance(item, dict)]
            return " ".join(parts).strip()
        if isinstance(message, str):
            return message.strip()
        return ""

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any] | None:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        for candidate in (cleaned, cleaned[cleaned.find("{") : cleaned.rfind("}") + 1] if "{" in cleaned and "}" in cleaned else ""):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    async def _post_chat(self, payload: dict[str, Any], headers: dict[str, str]) -> httpx.Response | None:
        retries = max(0, settings.runtime.max_retries)
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.runtime.request_timeout_s) as client:
                    response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if response.status_code >= 500 and attempt < retries:
                    await asyncio.sleep(0.35 * (attempt + 1))
                    continue
                if response.status_code == 429 and attempt < retries:
                    await asyncio.sleep(0.6 * (attempt + 1))
                    continue
                return response
            except Exception as exc:  # noqa: BLE001
                if attempt >= retries:
                    logger.warning("hypo_gpt.llm.request_failed", error=str(exc), attempt=attempt + 1)
                    return None
                await asyncio.sleep(0.35 * (attempt + 1))
        return None

    @property
    def is_configured(self) -> bool:
        return bool(settings.openai.api_key)

    async def summarize(self, text: str, max_chars: int = 500) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[:max_chars].rsplit(" ", 1)[0] + "..."

    async def expand(self, prompt: str, context: str = "") -> str:
        if self.is_configured:
            system = "You are a senior research strategist. Expand prompt into concrete, technical, concise guidance."
            user = f"Prompt: {prompt.strip()}\n\nContext:\n{context[:4000]}"
            response = await self.complete_text(system_prompt=system, user_prompt=user, temperature=0.2, max_output_tokens=350)
            if response:
                return response
        if context:
            return f"{prompt.strip()} | Context: {context[:240]}"
        return prompt.strip()

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 1200,
        model: str | None = None,
    ) -> str | None:
        if not self.is_configured:
            return None

        payload = {
            "model": model or settings.openai.reasoning_model or self.model,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.openai.api_key}",
            "Content-Type": "application/json",
        }

        response = await self._post_chat(payload, headers)
        if response is None:
            return None
        if response.status_code >= 300:
            logger.warning("hypo_gpt.llm.text_http_error", status_code=response.status_code, body=response.text[:500])
            return None
        try:
            data = response.json()
            message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            content = self._coerce_message_content(message)
            return content or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("hypo_gpt.llm.text_parse_failed", error=str(exc))
            return None

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 2200,
        model: str | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_configured:
            return None

        response_format: dict[str, Any] = {"type": "json_object"}
        if json_schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": json_schema,
                },
            }

        payload = {
            "model": model or settings.openai.reasoning_model or self.model,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": response_format,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.openai.api_key}",
            "Content-Type": "application/json",
        }

        response = await self._post_chat(payload, headers)
        if response is None:
            return None
        if response.status_code >= 300:
            if json_schema is not None and response.status_code == 400:
                # Some provider/model combinations may not support strict json_schema in chat completions.
                return await self.complete_json(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    model=model,
                    json_schema=None,
                )
            logger.warning("hypo_gpt.llm.json_http_error", status_code=response.status_code, body=response.text[:500])
            return None
        try:
            data = response.json()
            message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            content = self._coerce_message_content(message)
            if not content:
                return None
            parsed = self._extract_json_object(content)
            if parsed is None:
                logger.warning("hypo_gpt.llm.json_parse_failed", preview=content[:200])
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning("hypo_gpt.llm.json_failed", error=str(exc))
            return None

    def get_active_provider(self) -> dict[str, str]:
        if self.is_configured:
            return {"openai": self.model}
        return {"fallback": "deterministic"}
