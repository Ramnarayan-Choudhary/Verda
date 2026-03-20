"""
Centralized configuration for the hypo-claude Epistemic Engine.

Uses pydantic-settings for validated env var loading.
Designed for OpenAI as primary provider, but swappable via LLM_PROVIDER.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOT_ENV_LOCAL = _REPO_ROOT / ".env.local"


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


class GeminiConfig(BaseSettings):
    """Google Gemini API configuration — used for FAST tier (extraction, serialization)."""
    api_key: str = Field(default="")
    fast_model: str = Field(default="gemini-2.5-flash")
    reasoning_model: str = Field(default="gemini-1.5-pro")

    model_config = {"env_prefix": "GEMINI_"}


class SupabaseConfig(BaseSettings):
    """Supabase connection for pgvector."""
    url: str = Field(default="")
    service_role_key: str = Field(default="")
    postgres_url: str = Field(default="")

    model_config = {"env_prefix": "SUPABASE_"}


class LLMRuntimeConfig(BaseSettings):
    """Operational safeguards for LLM calls."""
    request_timeout_s: int = Field(default=120, ge=10, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    provider: str = Field(default="openai", description="openai | anthropic")

    model_config = {"env_prefix": "LLM_"}


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)

    model_config = {"env_prefix": "HYPO_CLAUDE_"}


class PipelineDefaults(BaseSettings):
    """Default pipeline parameters (overridable per-request)."""
    max_hypotheses_per_strategy: int = Field(default=1, ge=1, le=10)
    tribunal_cycles: int = Field(default=1, ge=1, le=5)
    dedup_threshold: float = Field(default=0.80, ge=0.5, le=1.0)
    max_concurrent_strategies: int = Field(default=2, ge=1, le=7)
    max_concurrent_critics: int = Field(default=1, ge=1, le=8)

    model_config = {"env_prefix": "PIPELINE_"}


# Stage timeouts (seconds)
DEFAULT_STAGE_TIMEOUTS: dict[str, int] = {
    "intelligence": 300,
    "cartography": 300,
    "generation": 600,
    "tribunal": 900,
    "evaluation": 600,
    "portfolio": 300,
    "output": 60,
}


class Settings(BaseSettings):
    """Root settings — aggregates all config sections."""

    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    llm: LLMRuntimeConfig = Field(default_factory=LLMRuntimeConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    pipeline: PipelineDefaults = Field(default_factory=PipelineDefaults)

    semantic_scholar_api_key: str = Field(default="")
    tavily_api_key: str = Field(default="")

    model_config = {
        "env_file": str(_ROOT_ENV_LOCAL),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def load_settings() -> Settings:
    """Load settings from environment / root .env.local file."""
    from dotenv import load_dotenv

    if _ROOT_ENV_LOCAL.exists():
        load_dotenv(_ROOT_ENV_LOCAL, override=True)

    return Settings()


settings = load_settings()
