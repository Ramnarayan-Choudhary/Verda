"""
Tiered LLM Provider — role-based model routing for the Epistemic Engine.

19 agent roles mapped to 3 tiers (REASONING, CREATIVE, FAST).
Uses OpenAI API via langchain-openai. Designed for easy provider switching.
"""

from __future__ import annotations

import asyncio
import json
import re
from enum import Enum

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from hypo_claude.config import settings
from hypo_claude.models import TokenUsage

logger = structlog.get_logger(__name__)


_NON_RETRYABLE_ERROR_NAMES = {
    "AuthenticationError",
    "PermissionDeniedError",
    "BadRequestError",
    "UnprocessableEntityError",
    "NotFoundError",
}


def _is_non_retryable_exception(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in _NON_RETRYABLE_ERROR_NAMES:
        return True

    message = str(exc).lower()
    if "incorrect api key" in message or "invalid api key" in message:
        return True
    if "authentication" in message and ("401" in message or "unauthorized" in message):
        return True
    if "insufficient_quota" in message or "billing" in message:
        return True

    if isinstance(exc, RuntimeError) and str(exc).startswith("LLM authentication/config failed"):
        return True

    return False


def _should_retry_exception(exc: Exception) -> bool:
    return not _is_non_retryable_exception(exc)


def _format_non_retryable_error(exc: Exception, provider_name: str, model: str) -> str:
    msg = str(exc).strip() or exc.__class__.__name__
    return (
        f"LLM authentication/config failed for {provider_name} ({model}). "
        f"Check OPENAI_API_KEY and model access, then restart hypo_claude. Upstream: {msg}"
    )


class AgentRole(str, Enum):
    """Semantic roles — each maps to a model tier."""

    # REASONING tier — deep analytical thinking
    DOMAIN_CRITIC = "domain_critic"
    METHODOLOGY_CRITIC = "methodology_critic"
    DEVILS_ADVOCATE = "devils_advocate"
    RESOURCE_CRITIC = "resource_critic"
    MECHANISM_VALIDATOR = "mechanism_validator"
    CONSERVATIVE_JUDGE = "conservative_judge"
    GENERALIST_JUDGE = "generalist_judge"
    PRACTITIONER_JUDGE = "practitioner_judge"
    GAP_ANALYST = "gap_analyst"
    LANDSCAPE_SYNTHESIZER = "landscape_synthesizer"

    # CREATIVE tier — divergent thinking + novelty
    ASSUMPTION_CHALLENGER = "assumption_challenger"
    DOMAIN_BRIDGE = "domain_bridge"
    CONTRADICTION_RESOLVER = "contradiction_resolver"
    CONSTRAINT_RELAXER = "constraint_relaxer"
    MECHANISM_EXTRACTOR = "mechanism_extractor"
    SYNTHESIS_CATALYST = "synthesis_catalyst"
    FALSIFICATION_DESIGNER = "falsification_designer"
    EVOLVER = "evolver"
    PORTFOLIO_CONSTRUCTOR = "portfolio_constructor"

    # FAST tier — extraction, structured output
    PAPER_EXTRACTOR = "paper_extractor"
    OUTPUT_SERIALIZER = "output_serializer"

    # Universal
    DEFAULT = "default"


_ROLE_TIER: dict[AgentRole, str] = {
    # Reasoning
    AgentRole.DOMAIN_CRITIC: "reasoning",
    AgentRole.METHODOLOGY_CRITIC: "reasoning",
    AgentRole.DEVILS_ADVOCATE: "reasoning",
    AgentRole.RESOURCE_CRITIC: "reasoning",
    AgentRole.MECHANISM_VALIDATOR: "reasoning",
    AgentRole.CONSERVATIVE_JUDGE: "reasoning",
    AgentRole.GENERALIST_JUDGE: "reasoning",
    AgentRole.PRACTITIONER_JUDGE: "reasoning",
    AgentRole.GAP_ANALYST: "reasoning",
    AgentRole.LANDSCAPE_SYNTHESIZER: "reasoning",
    # Creative
    AgentRole.ASSUMPTION_CHALLENGER: "creative",
    AgentRole.DOMAIN_BRIDGE: "creative",
    AgentRole.CONTRADICTION_RESOLVER: "creative",
    AgentRole.CONSTRAINT_RELAXER: "creative",
    AgentRole.MECHANISM_EXTRACTOR: "creative",
    AgentRole.SYNTHESIS_CATALYST: "creative",
    AgentRole.FALSIFICATION_DESIGNER: "creative",
    AgentRole.EVOLVER: "creative",
    AgentRole.PORTFOLIO_CONSTRUCTOR: "creative",
    # Fast
    AgentRole.PAPER_EXTRACTOR: "fast",
    AgentRole.OUTPUT_SERIALIZER: "fast",
    # Universal
    AgentRole.DEFAULT: "universal",
}


class _ProviderSlot:
    """A configured LLM client with metadata."""

    def __init__(self, client: ChatOpenAI, name: str, model: str) -> None:
        self.client = client
        self.name = name
        self.model = model


class LLMProvider:
    """Role-based LLM interface — routes agent roles to the best model tier.

    Usage:
        llm = LLMProvider()
        text = await llm.generate("System", "User", role=AgentRole.DOMAIN_CRITIC)
        obj = await llm.generate_json("System", "User", MyModel, role=AgentRole.EVOLVER)
    """

    def __init__(self) -> None:
        self.token_usage = TokenUsage()
        self._providers: dict[str, _ProviderSlot] = {}
        self._init_providers()
        self._tier_map = self._build_tier_map()

        available = list(self._providers.keys())
        logger.info("llm.initialized", providers=available, tier_map=self._tier_map)

    def _init_providers(self) -> None:
        runtime_kwargs = {
            "timeout": settings.llm.request_timeout_s,
            "max_retries": settings.llm.max_retries,
        }

        if settings.openai.api_key:
            base = settings.openai.base_url
            key = settings.openai.api_key

            self._providers["reasoning"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key, base_url=base,
                    model=settings.openai.reasoning_model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name=f"OpenAI/{settings.openai.reasoning_model}",
                model=settings.openai.reasoning_model,
            )
            self._providers["creative"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key, base_url=base,
                    model=settings.openai.creative_model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name=f"OpenAI/{settings.openai.creative_model}",
                model=settings.openai.creative_model,
            )
            self._providers["fast"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key, base_url=base,
                    model=settings.openai.fast_model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name=f"OpenAI/{settings.openai.fast_model}",
                model=settings.openai.fast_model,
            )

        if not self._providers:
            raise RuntimeError(
                "No LLM provider configured. Set OPENAI_API_KEY in your .env file."
            )

    def _build_tier_map(self) -> dict[str, str]:
        """Map each tier to its provider key."""
        result = {}
        for tier in ("reasoning", "creative", "fast"):
            if tier in self._providers:
                result[tier] = tier
            else:
                result[tier] = next(iter(self._providers))
        result["universal"] = next(iter(self._providers))
        return result

    def _resolve(self, role: AgentRole) -> _ProviderSlot:
        tier = _ROLE_TIER.get(role, "universal")
        provider_key = self._tier_map.get(tier, next(iter(self._providers)))
        return self._providers[provider_key]

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        role: AgentRole = AgentRole.DEFAULT,
    ) -> str:
        """Generate a text response using the best model for the given role."""
        provider = self._resolve(role)
        return await self._call(provider, system, user, temperature)

    async def generate_json(
        self,
        system: str,
        user: str,
        model_class: type[BaseModel],
        temperature: float = 0.2,
        role: AgentRole = AgentRole.DEFAULT,
        max_retries: int = 2,
    ) -> BaseModel:
        """Generate and validate a JSON response against a Pydantic model."""
        schema_hint = (
            f"\n\nYou MUST respond with valid JSON matching this schema:\n"
            f"{json.dumps(model_class.model_json_schema(), indent=2)}"
        )
        raw = await self.generate(system, user + schema_hint, temperature, role=role)
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                parsed = _extract_json(raw)
                return model_class.model_validate(parsed)
            except Exception as err:
                last_error = err
                if attempt < max_retries:
                    logger.warning(
                        "llm.json_retry",
                        model=model_class.__name__,
                        attempt=attempt + 1,
                        error=str(err)[:200],
                    )
                    fix_prompt = (
                        f"{user}{schema_hint}\n\n---\n"
                        f"Your previous response had validation errors:\n{err}\n"
                        f"Fix these and return valid JSON only."
                    )
                    raw = await self.generate(system, fix_prompt, temperature, role=role)

        # Final recovery: ask a fast model to coerce raw text into schema
        try:
            return await self._recover_json(raw, model_class)
        except Exception:
            raise last_error  # type: ignore[misc]

    async def _recover_json(self, raw_text: str, model_class: type[BaseModel]) -> BaseModel:
        schema = model_class.model_json_schema()
        system = (
            "You are a strict JSON transformer. "
            "Convert the provided text into JSON matching the schema exactly. "
            "Output ONLY valid JSON, no markdown, no explanations."
        )
        user = f"SCHEMA:\n{json.dumps(schema)}\n\nRAW_TEXT:\n{raw_text[:4000]}\n\nReturn valid JSON only."
        recovered = await self.generate(system, user, temperature=0.0, role=AgentRole.OUTPUT_SERIALIZER)
        parsed = _extract_json(recovered)
        return model_class.model_validate(parsed)

    async def generate_batch(
        self,
        prompts: list[tuple[str, str]],
        temperature: float = 0.5,
        role: AgentRole = AgentRole.DEFAULT,
        max_concurrent: int = 4,
    ) -> list[str]:
        """Generate multiple responses concurrently with semaphore control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded(system: str, user: str) -> str:
            async with semaphore:
                return await self.generate(system, user, temperature, role=role)

        return await asyncio.gather(*[_bounded(s, u) for s, u in prompts])

    def get_active_providers(self) -> dict[str, str]:
        report = {}
        for role in AgentRole:
            provider = self._resolve(role)
            tier = _ROLE_TIER.get(role, "universal")
            report[role.value] = f"{provider.name} ({tier})"
        return report

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_should_retry_exception),
    )
    async def _call(self, provider: _ProviderSlot, system: str, user: str, temperature: float) -> str:
        logger.debug("llm.call", provider=provider.name, model=provider.model)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            response = await provider.client.ainvoke(messages, temperature=temperature)
        except Exception as exc:
            if _is_non_retryable_exception(exc):
                detail = _format_non_retryable_error(exc, provider.name, provider.model)
                logger.error(
                    "llm.call_non_retryable",
                    provider=provider.name,
                    model=provider.model,
                    error=str(exc)[:400],
                )
                raise RuntimeError(detail) from exc
            raise
        content = response.content if isinstance(response.content, str) else str(response.content)

        # Track token usage
        prompt_t, comp_t = self._extract_usage(response, system, user, content)
        cost = _estimate_cost(provider.model, prompt_t, comp_t)
        self.token_usage.add(prompt=prompt_t, completion=comp_t, cost=cost)

        logger.debug("llm.done", provider=provider.name, chars=len(content))
        return content

    @staticmethod
    def _extract_usage(response, system: str, user: str, content: str) -> tuple[int, int]:
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            p = meta.get("input_tokens", 0) if isinstance(meta, dict) else getattr(meta, "input_tokens", 0)
            c = meta.get("output_tokens", 0) if isinstance(meta, dict) else getattr(meta, "output_tokens", 0)
            if p or c:
                return int(p), int(c)
        if hasattr(response, "response_metadata") and response.response_metadata:
            usage = response.response_metadata.get("token_usage") or response.response_metadata.get("usage") or {}
            p, c = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            if p or c:
                return int(p), int(c)
        return (len(system) + len(user)) // 4, len(content) // 4


_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "o3-mini": (1.10, 4.40),
}

_DEFAULT_COST = (2.50, 10.00)


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pr, cr = _MODEL_COSTS.get(model, _DEFAULT_COST)
    return (prompt_tokens * pr + completion_tokens * cr) / 1_000_000


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response — handles markdown-wrapped JSON."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}...")
