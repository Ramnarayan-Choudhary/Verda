"""GPT provider facade with OpenAI JSON support and deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass
import json
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

        try:
            async with httpx.AsyncClient(timeout=settings.runtime.request_timeout_s) as client:
                response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if response.status_code >= 300:
                logger.warning("hypo_gpt.llm.text_http_error", status_code=response.status_code, body=response.text[:500])
                return None
            data = response.json()
            message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if isinstance(message, list):
                parts = [x.get("text", "") for x in message if isinstance(x, dict)]
                return " ".join(parts).strip() or None
            if isinstance(message, str):
                return message.strip() or None
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("hypo_gpt.llm.text_failed", error=str(exc))
            return None

    async def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_output_tokens: int = 2200,
        model: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_configured:
            return None

        payload = {
            "model": model or settings.openai.reasoning_model or self.model,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {settings.openai.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.runtime.request_timeout_s) as client:
                response = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            if response.status_code >= 300:
                logger.warning("hypo_gpt.llm.json_http_error", status_code=response.status_code, body=response.text[:500])
                return None
            data = response.json()
            message = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            if isinstance(message, list):
                parts = [x.get("text", "") for x in message if isinstance(x, dict)]
                message = " ".join(parts).strip()
            if not isinstance(message, str) or not message.strip():
                return None
            parsed = json.loads(message)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("hypo_gpt.llm.json_failed", error=str(exc))
            return None

    def get_active_provider(self) -> dict[str, str]:
        if self.is_configured:
            return {"openai": self.model}
        return {"fallback": "deterministic"}
