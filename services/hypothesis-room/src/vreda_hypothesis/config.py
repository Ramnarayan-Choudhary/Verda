"""
Centralized configuration — validates all env vars at import time.

Supports 6 LLM providers with tiered routing:
- ChatAnywhere (primary — provides deepseek-r1, deepseek-v3, gpt-4o-mini via one key)
- K2Think (universal fallback)
- OpenRouter → Gemini Flash (fast, cheap structured output)
- DeepSeek R1 (direct API — if you have a separate key)
- OpenAI GPT-4o (direct API — if you have a separate key)
- Anthropic Claude Sonnet (deepest reasoning, best for critique)

When only ChatAnywhere is configured, ALL tiers are covered:
  REASONING → deepseek-r1-0528, CREATIVE → deepseek-v3, FAST → gpt-4o-mini-ca
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class ChatAnywhereConfig(BaseSettings):
    """ChatAnywhere API — single key provides deepseek-r1, deepseek-v3, gpt-4o-mini.

    This is the primary provider. One API key covers all 3 tiers:
    - REASONING: deepseek-r1-0528 (deep analytical thinking)
    - CREATIVE:  deepseek-v3 (fast creative generation)
    - FAST:      gpt-4o-mini-ca (cheap structured output)
    """
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.chatanywhere.tech/v1")
    reasoning_model: str = Field(default="deepseek-r1-0528")
    creative_model: str = Field(default="deepseek-v3")
    fast_model: str = Field(default="gpt-4o-mini-ca")

    model_config = {"env_prefix": "CHATANYWHERE_"}


class K2ThinkConfig(BaseSettings):
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.k2think.ai/v1")
    model: str = Field(default="MBZUAI-IFM/K2-Think-v2")

    model_config = {"env_prefix": "K2THINK_"}


class OpenRouterConfig(BaseSettings):
    api_key: str = Field(default="")
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    model: str = Field(default="google/gemini-2.0-flash-001")

    model_config = {"env_prefix": "OPENROUTER_"}


class DeepSeekConfig(BaseSettings):
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.deepseek.com/v1")
    model: str = Field(default="deepseek-reasoner")

    model_config = {"env_prefix": "DEEPSEEK_"}


class OpenAIConfig(BaseSettings):
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.openai.com/v1")
    model: str = Field(default="gpt-4o")
    # OpenAI Responses API web-search settings
    websearch_model: str = Field(default="gpt-4o")
    websearch_timeout_s: int = Field(default=35, ge=10, le=120)
    websearch_max_results: int = Field(default=5, ge=1, le=20)
    websearch_context_size: str = Field(default="medium")

    model_config = {"env_prefix": "OPENAI_"}


class AnthropicConfig(BaseSettings):
    """Anthropic Claude — accessed via OpenRouter (OpenAI-compatible).

    To use Claude directly, set ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
    and use langchain-anthropic instead (see LLM_PROVIDERS.md).
    For now we route through OpenRouter for API compatibility.
    """
    api_key: str = Field(default="")
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    model: str = Field(default="anthropic/claude-sonnet-4-5-20250929")

    model_config = {"env_prefix": "ANTHROPIC_"}


class SupabaseConfig(BaseSettings):
    url: str = Field(default="")
    service_role_key: str = Field(default="")
    # Direct Postgres connection for vecs library (pgvector)
    postgres_url: str = Field(default="")

    model_config = {"env_prefix": "SUPABASE_"}


class PipelineDefaults(BaseSettings):
    max_seeds: int = Field(default=200)
    max_cycles: int = Field(default=4)
    top_k: int = Field(default=10)

    model_config = {"env_prefix": "DEFAULT_"}


class LLMRuntimeConfig(BaseSettings):
    """Operational safeguards for LLM calls."""

    request_timeout_s: int = Field(default=45, ge=10, le=180)
    max_retries: int = Field(default=1, ge=0, le=5)
    # Force all agent roles to use OpenAI (gpt-4o) only.
    force_openai_only: bool = Field(default=True)

    model_config = {"env_prefix": "LLM_"}


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)


class Settings(BaseSettings):
    """Root settings — aggregates all config sections."""

    chatanywhere: ChatAnywhereConfig = Field(default_factory=ChatAnywhereConfig)
    k2think: K2ThinkConfig = Field(default_factory=K2ThinkConfig)
    openrouter: OpenRouterConfig = Field(default_factory=OpenRouterConfig)
    deepseek: DeepSeekConfig = Field(default_factory=DeepSeekConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    pipeline: PipelineDefaults = Field(default_factory=PipelineDefaults)
    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    # Optional API keys for external services
    github_token: str = Field(default="")
    semantic_scholar_api_key: str = Field(default="")
    tavily_api_key: str = Field(default="")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def load_settings() -> Settings:
    """Load settings from environment / .env file."""
    for env_path in [
        ".env",
        "../../apps/web/.env.local",
        "../../vreda-app/.env.local",
        "../vreda-app/.env.local",
    ]:
        if os.path.exists(env_path):
            from dotenv import load_dotenv

            load_dotenv(env_path)
            break

    return Settings()


# Singleton
settings = load_settings()
