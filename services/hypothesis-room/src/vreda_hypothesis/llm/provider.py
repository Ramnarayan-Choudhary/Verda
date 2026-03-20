"""
Tiered LLM Provider — role-based model routing with automatic fallback.

Each agent role maps to its IDEAL model. When that model's API key
isn't configured, the system falls back through the priority chain
until it finds an available provider.

Tier Strategy (with ChatAnywhere as primary):
  - REASONING (critic, meta-reviewer, judge, gap analysis):
      ChatAnywhere/deepseek-r1 → Claude Sonnet → DeepSeek direct → K2Think
  - CREATIVE (proposer, evolver, seed generation):
      ChatAnywhere/deepseek-v3 → DeepSeek direct → GPT-4o → K2Think
  - FAST (paper extraction, verifiability, batch operations):
      ChatAnywhere/gpt-4o-mini → OpenRouter/Gemini → K2Think
  - UNIVERSAL (anything else):
      K2Think → ChatAnywhere/deepseek-v3 → OpenRouter

When only ChatAnywhere is configured, ALL tiers are covered.

Reference: arXiv:2502.18864 — AI Co-Scientist uses specialized models per agent role.
"""

from __future__ import annotations

import asyncio
import json
import re
from enum import Enum

import structlog
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from vreda_hypothesis.config import settings
from vreda_hypothesis.models import TokenUsage

logger = structlog.get_logger(__name__)


class AgentRole(str, Enum):
    """Semantic roles that determine which LLM tier to use."""

    # Tier: REASONING — needs deep analytical thinking
    CRITIC = "critic"
    META_REVIEWER = "meta_reviewer"
    TOURNAMENT_JUDGE = "tournament_judge"
    GAP_ANALYSIS = "gap_analysis"

    # Tier: CREATIVE — needs divergent thinking + novelty
    PROPOSER = "proposer"
    EVOLVER = "evolver"
    SEED_GENERATION = "seed_generation"

    # Tier: FAST — needs speed + structured output, low cost
    PAPER_EXTRACTION = "paper_extraction"
    VERIFIABILITY = "verifiability"
    FILTERING = "filtering"

    # Tier: UNIVERSAL — general purpose
    DEFAULT = "default"


# Which tier each role belongs to
_ROLE_TIER: dict[AgentRole, str] = {
    AgentRole.CRITIC: "reasoning",
    AgentRole.META_REVIEWER: "reasoning",
    AgentRole.TOURNAMENT_JUDGE: "reasoning",
    # GAP_ANALYSIS expects strict JSON; prefer structured-capable creative tier.
    AgentRole.GAP_ANALYSIS: "creative",
    AgentRole.PROPOSER: "creative",
    AgentRole.EVOLVER: "creative",
    AgentRole.SEED_GENERATION: "creative",
    AgentRole.PAPER_EXTRACTION: "fast",
    AgentRole.VERIFIABILITY: "fast",
    AgentRole.FILTERING: "fast",
    AgentRole.DEFAULT: "universal",
}


class _ProviderSlot:
    """A configured LLM client with its metadata."""

    def __init__(self, client: ChatOpenAI, name: str, model: str) -> None:
        self.client = client
        self.name = name
        self.model = model

    def with_temperature(self, temperature: float) -> ChatOpenAI:
        return self.client.with_config({"temperature": temperature})


class LLMProvider:
    """Tiered LLM interface — routes agent roles to their ideal model.

    Usage:
        llm = LLMProvider()

        # Default: uses universal tier
        result = await llm.generate("System", "User")

        # Role-specific: uses best available model for that role
        result = await llm.generate("System", "User", role=AgentRole.CRITIC)

        # JSON with validation
        parsed = await llm.generate_json("System", "User", MyModel, role=AgentRole.PROPOSER)
    """

    def __init__(self) -> None:
        self.token_usage = TokenUsage()
        self._providers: dict[str, _ProviderSlot] = {}
        self._init_providers()
        if settings.llm.force_openai_only and "openai" not in self._providers:
            raise RuntimeError(
                "LLM_FORCE_OPENAI_ONLY is enabled but OPENAI_API_KEY is missing. "
                "Set OPENAI_API_KEY or disable LLM_FORCE_OPENAI_ONLY."
            )

        # Build the fallback chains per tier
        self._tier_chains: dict[str, list[str]] = self._build_tier_chains()

        available = list(self._providers.keys())
        logger.info("llm.initialized", available_providers=available, tiers=self._tier_chains)

    def _init_providers(self) -> None:
        """Initialize all configured LLM clients."""
        runtime_kwargs = {
            "timeout": settings.llm.request_timeout_s,
            "max_retries": settings.llm.max_retries,
        }

        # ChatAnywhere — single key provides 3 tier-specific models
        if settings.chatanywhere.api_key:
            base = settings.chatanywhere.base_url
            key = settings.chatanywhere.api_key

            # REASONING: deepseek-r1-0528 (strong analytical thinking)
            self._providers["ca_reasoning"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key,
                    base_url=base,
                    model=settings.chatanywhere.reasoning_model,
                    # DeepSeek R1 doesn't support json_object response_format
                    **runtime_kwargs,
                ),
                name=f"ChatAnywhere/{settings.chatanywhere.reasoning_model}",
                model=settings.chatanywhere.reasoning_model,
            )

            # CREATIVE: deepseek-v3 (fast creative generation)
            self._providers["ca_creative"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key,
                    base_url=base,
                    model=settings.chatanywhere.creative_model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name=f"ChatAnywhere/{settings.chatanywhere.creative_model}",
                model=settings.chatanywhere.creative_model,
            )

            # FAST: gpt-4o-mini-ca (cheap structured output)
            self._providers["ca_fast"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=key,
                    base_url=base,
                    model=settings.chatanywhere.fast_model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name=f"ChatAnywhere/{settings.chatanywhere.fast_model}",
                model=settings.chatanywhere.fast_model,
            )

        # K2Think — universal fallback
        if settings.k2think.api_key:
            self._providers["k2think"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=settings.k2think.api_key,
                    base_url=settings.k2think.base_url,
                    model=settings.k2think.model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name="K2Think",
                model=settings.k2think.model,
            )

        # OpenRouter → Gemini Flash — fast + cheap
        if settings.openrouter.api_key:
            self._providers["openrouter"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=settings.openrouter.api_key,
                    base_url=settings.openrouter.base_url,
                    model=settings.openrouter.model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    default_headers={
                        "HTTP-Referer": "https://vreda.ai",
                        "X-Title": "VREDA Hypothesis",
                    },
                    **runtime_kwargs,
                ),
                name="OpenRouter/Gemini",
                model=settings.openrouter.model,
            )

        # DeepSeek R1 (direct) — if you have a separate DeepSeek API key
        if settings.deepseek.api_key:
            self._providers["deepseek"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=settings.deepseek.api_key,
                    base_url=settings.deepseek.base_url,
                    model=settings.deepseek.model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name="DeepSeek",
                model=settings.deepseek.model,
            )

        # OpenAI GPT-4o (direct) — if you have a separate OpenAI key
        if settings.openai.api_key:
            self._providers["openai"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=settings.openai.api_key,
                    base_url=settings.openai.base_url,
                    model=settings.openai.model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    **runtime_kwargs,
                ),
                name="OpenAI",
                model=settings.openai.model,
            )

        # Anthropic Claude — via OpenRouter for API compatibility
        if settings.anthropic.api_key:
            self._providers["anthropic"] = _ProviderSlot(
                client=ChatOpenAI(
                    api_key=settings.anthropic.api_key,
                    base_url=settings.anthropic.base_url,
                    model=settings.anthropic.model,
                    model_kwargs={"response_format": {"type": "json_object"}},
                    default_headers={
                        "HTTP-Referer": "https://vreda.ai",
                        "X-Title": "VREDA Hypothesis",
                    },
                    **runtime_kwargs,
                ),
                name="Anthropic/Claude",
                model=settings.anthropic.model,
            )

        if not self._providers:
            raise RuntimeError(
                "No LLM provider configured. Set CHATANYWHERE_API_KEY or K2THINK_API_KEY in root .env.local."
            )

    def _build_tier_chains(self) -> dict[str, list[str]]:
        """Build fallback chains per tier — only includes available providers.

        Each chain is ordered from ideal → fallback. When a provider isn't
        configured, it's silently skipped.
        """
        if settings.llm.force_openai_only:
            return {
                "reasoning": ["openai"],
                "creative": ["openai"],
                "fast": ["openai"],
                "universal": ["openai"],
            }

        # Ideal ordering per tier (best first)
        ideal_chains = {
            "reasoning": ["ca_reasoning", "anthropic", "deepseek", "ca_creative", "k2think", "openrouter"],
            "creative": ["ca_creative", "deepseek", "openai", "ca_reasoning", "k2think", "openrouter"],
            "fast": ["ca_fast", "openrouter", "k2think", "ca_creative", "openai", "deepseek"],
            "universal": ["ca_creative", "k2think", "openrouter", "ca_fast", "deepseek", "openai"],
        }

        available = set(self._providers.keys())
        return {
            tier: [p for p in chain if p in available]
            for tier, chain in ideal_chains.items()
        }

    def _resolve_provider(self, role: AgentRole) -> tuple[_ProviderSlot, str]:
        """Resolve the best available provider for a given agent role."""
        tier = _ROLE_TIER.get(role, "universal")
        chain = self._tier_chains.get(tier, [])

        if not chain:
            # Absolute fallback — use whatever is available
            first_key = next(iter(self._providers))
            return self._providers[first_key], tier

        return self._providers[chain[0]], tier

    def _resolve_fallback(self, role: AgentRole, failed_provider: str) -> _ProviderSlot | None:
        """Get the next provider in the chain after a failure."""
        tier = _ROLE_TIER.get(role, "universal")
        chain = self._tier_chains.get(tier, [])

        try:
            idx = chain.index(failed_provider)
            if idx + 1 < len(chain):
                return self._providers[chain[idx + 1]]
        except ValueError:
            pass
        return None

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        role: AgentRole = AgentRole.DEFAULT,
    ) -> str:
        """Generate a text response using the best model for the given role.

        Tries the ideal provider, then falls back through the tier chain.
        """
        provider, tier = self._resolve_provider(role)

        try:
            return await self._call(provider, system, user, temperature)
        except Exception as primary_err:
            fallback = self._resolve_fallback(role, next(
                k for k, v in self._providers.items() if v is provider
            ))
            if fallback and fallback is not provider:
                logger.warning(
                    "llm.primary_failed_using_fallback",
                    primary=provider.name,
                    fallback=fallback.name,
                    tier=tier,
                    role=role.value,
                    error=str(primary_err),
                )
                return await self._call(fallback, system, user, temperature)
            raise

    async def generate_json(
        self,
        system: str,
        user: str,
        model_class: type[BaseModel],
        temperature: float = 0.2,
        role: AgentRole = AgentRole.DEFAULT,
        max_retries: int = 2,
    ) -> BaseModel:
        """Generate and parse a JSON response, validated against a Pydantic model.

        On validation failure, retries with a fix prompt (up to max_retries).
        Uses role-based model routing.
        """
        raw = await self.generate(system, user, temperature, role=role)
        parsed: dict | None = None
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                if parsed is None:
                    parsed = _extract_json(raw)
                return model_class.model_validate(parsed)
            except Exception as validation_err:
                last_error = validation_err
                if attempt < max_retries:
                    logger.warning(
                        "llm.validation_failed_retrying",
                        model=model_class.__name__,
                        role=role.value,
                        attempt=attempt + 1,
                        error=str(validation_err),
                    )
                    fix_prompt = (
                        f"{user}\n\n---\n"
                        f"IMPORTANT: Your previous response had validation errors:\n"
                        f"{validation_err}\n\n"
                        f"Fix these issues and return valid JSON matching the schema exactly."
                    )
                    raw = await self.generate(system, fix_prompt, temperature, role=role)
                    parsed = None
                else:
                    break

        # Final recovery pass: convert free-form output into strict schema JSON.
        try:
            recovered = await self._recover_structured_json(raw, model_class)
            return model_class.model_validate(recovered)
        except Exception as recover_err:
            if last_error:
                logger.warning(
                    "llm.structured_recovery_failed",
                    model=model_class.__name__,
                    role=role.value,
                    original_error=str(last_error),
                    recovery_error=str(recover_err),
                )
                raise last_error
            raise recover_err

        raise RuntimeError("generate_json exhausted retries")

    async def _recover_structured_json(self, raw_text: str, model_class: type[BaseModel]) -> dict:
        """Ask a structured-capable model to coerce raw text into valid schema JSON."""
        schema = model_class.model_json_schema()
        system = (
            "You are a strict JSON transformer.\n"
            "Convert the provided text into JSON that matches the provided schema.\n"
            "Rules: output ONLY JSON, no markdown, no explanations, include required fields."
        )
        user = (
            f"SCHEMA:\n{json.dumps(schema, ensure_ascii=True)}\n\n"
            f"RAW_TEXT:\n{raw_text}\n\n"
            "Return valid JSON only."
        )
        recovered = await self.generate(system, user, temperature=0.0, role=AgentRole.VERIFIABILITY)
        return _extract_json(recovered)

    async def generate_batch(
        self,
        prompts: list[tuple[str, str]],
        temperature: float = 0.5,
        role: AgentRole = AgentRole.DEFAULT,
        max_concurrent: int = 10,
    ) -> list[str]:
        """Generate multiple responses concurrently with semaphore control."""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _bounded_call(system: str, user: str) -> str:
            async with semaphore:
                return await self.generate(system, user, temperature, role=role)

        tasks = [_bounded_call(s, u) for s, u in prompts]
        return await asyncio.gather(*tasks)

    def get_active_providers(self) -> dict[str, str]:
        """Report which providers are active and what tier each role uses."""
        report = {}
        for role in AgentRole:
            provider, tier = self._resolve_provider(role)
            report[role.value] = f"{provider.name} ({tier})"
        return report

    @retry(
        stop=stop_after_attempt(settings.llm.max_retries + 1),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
    )
    async def _call(self, provider: _ProviderSlot, system: str, user: str, temperature: float) -> str:
        """Make a single LLM call with retry + exponential backoff."""
        logger.debug("llm.call_start", provider=provider.name, model=provider.model)

        client = provider.with_temperature(temperature)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        response = await client.ainvoke(messages)
        content = response.content if isinstance(response.content, str) else str(response.content)

        prompt_tokens, completion_tokens = self._extract_token_usage(response, system, user, content)
        cost = _estimate_cost(provider.model, prompt_tokens, completion_tokens)
        self.token_usage.add(prompt=prompt_tokens, completion=completion_tokens, cost=cost)

        logger.debug("llm.call_complete", provider=provider.name, length=len(content))
        return content

    @staticmethod
    def _extract_token_usage(response, system: str, user: str, content: str) -> tuple[int, int]:
        """Extract token counts from response, falling back to estimation.

        Checks three sources in order:
        1. usage_metadata (langchain's normalized format)
        2. response_metadata.token_usage (raw OpenAI format)
        3. Character-based estimation (~4 chars per token)
        """
        # Source 1: langchain's normalized usage_metadata
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            meta = response.usage_metadata
            prompt_t = getattr(meta, "input_tokens", 0) or meta.get("input_tokens", 0) if isinstance(meta, dict) else getattr(meta, "input_tokens", 0)
            comp_t = getattr(meta, "output_tokens", 0) or meta.get("output_tokens", 0) if isinstance(meta, dict) else getattr(meta, "output_tokens", 0)
            if prompt_t or comp_t:
                return int(prompt_t), int(comp_t)

        # Source 2: raw response_metadata from OpenAI-compatible APIs
        if hasattr(response, "response_metadata") and response.response_metadata:
            raw = response.response_metadata
            usage = raw.get("token_usage") or raw.get("usage") or {}
            prompt_t = usage.get("prompt_tokens", 0)
            comp_t = usage.get("completion_tokens", 0)
            if prompt_t or comp_t:
                return int(prompt_t), int(comp_t)

        # Source 3: estimate from character count (~4 chars per token)
        est_prompt = (len(system) + len(user)) // 4
        est_completion = len(content) // 4
        return est_prompt, est_completion


# Cost per 1M tokens (USD) — approximate rates for ChatAnywhere-proxied models
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (prompt_cost_per_1M, completion_cost_per_1M)
    "deepseek-r1-0528": (0.55, 2.19),       # DeepSeek R1 pricing
    "deepseek-v3": (0.27, 1.10),             # DeepSeek V3 pricing
    "gpt-4o-mini-ca": (0.15, 0.60),          # GPT-4o-mini pricing
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "deepseek-reasoner": (0.55, 2.19),
    "google/gemini-2.0-flash-001": (0.075, 0.30),
    "MBZUAI-IFM/K2-Think-v2": (0.50, 2.00),  # Estimated
    "anthropic/claude-sonnet-4-5-20250929": (3.00, 15.00),
}

# Default cost when model isn't in the table
_DEFAULT_COST = (0.50, 2.00)


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for a single LLM call."""
    prompt_rate, completion_rate = _MODEL_COSTS.get(model, _DEFAULT_COST)
    return (prompt_tokens * prompt_rate + completion_tokens * completion_rate) / 1_000_000


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response — handles markdown-wrapped JSON."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    code_block_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    array_match = re.search(r"\[[\s\S]*\]", text)
    if array_match:
        try:
            result = json.loads(array_match.group(0))
            return {"items": result} if isinstance(result, list) else result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}...")
