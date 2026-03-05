"""
Centralized configuration for the hypo-claude Epistemic Engine.

Uses pydantic-settings for validated env var loading.
Designed for OpenAI as primary provider, but swappable via LLM_PROVIDER.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class OpenAIConfig(BaseSettings):
    """OpenAI API configuration."""
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.openai.com/v1")
    reasoning_model: str = Field(default="gpt-4o")
    creative_model: str = Field(default="gpt-4o")
    fast_model: str = Field(default="gpt-4o-mini")

    model_config = {"env_prefix": "OPENAI_"}


class AnthropicConfig(BaseSettings):
    """Anthropic API configuration (future use)."""
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.anthropic.com/v1")
    model: str = Field(default="claude-sonnet-4-5-20250929")

    model_config = {"env_prefix": "ANTHROPIC_"}


class SupabaseConfig(BaseSettings):
    """Supabase connection for pgvector."""
    url: str = Field(default="")
    service_role_key: str = Field(default="")
    postgres_url: str = Field(default="")

    model_config = {"env_prefix": "SUPABASE_"}


class LLMRuntimeConfig(BaseSettings):
    """Operational safeguards for LLM calls."""
    request_timeout_s: int = Field(default=60, ge=10, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    provider: str = Field(default="openai", description="openai | anthropic")

    model_config = {"env_prefix": "LLM_"}


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)

    model_config = {"env_prefix": "HYPO_CLAUDE_"}


class PipelineDefaults(BaseSettings):
    """Default pipeline parameters (overridable per-request)."""
    max_hypotheses_per_strategy: int = Field(default=5, ge=2, le=10)
    tribunal_cycles: int = Field(default=3, ge=1, le=5)
    dedup_threshold: float = Field(default=0.80, ge=0.5, le=1.0)
    max_concurrent_strategies: int = Field(default=4, ge=1, le=7)
    max_concurrent_critics: int = Field(default=4, ge=1, le=8)

    model_config = {"env_prefix": "PIPELINE_"}


# Stage timeouts (seconds)
DEFAULT_STAGE_TIMEOUTS: dict[str, int] = {
    "intelligence": 180,
    "cartography": 240,
    "generation": 240,
    "tribunal": 360,
    "evaluation": 180,
    "portfolio": 60,
    "output": 15,
}


class Settings(BaseSettings):
    """Root settings — aggregates all config sections."""

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    pipeline: PipelineDefaults = Field(default_factory=PipelineDefaults)

    semantic_scholar_api_key: str = Field(default="")
    tavily_api_key: str = Field(default="")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def load_settings() -> Settings:
    """Load settings from environment / .env file."""
    from dotenv import load_dotenv

    service_root = Path(__file__).resolve().parents[1]
    repo_root = service_root.parents[1]
    env_candidates = [
        service_root / ".env",
        repo_root / ".env",
        repo_root / "apps/web/.env.local",
    ]

    # Load all known env files in order; later files override earlier values.
    # This lets hypo_claude pick up app-level secrets from apps/web/.env.local.
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=True)

    return Settings()


settings = load_settings()
