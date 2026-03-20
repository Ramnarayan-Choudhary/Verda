"""Configuration for standalone GPT hypothesis service."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

_REPO_ROOT = Path(__file__).resolve().parents[5]
_ROOT_ENV_LOCAL = _REPO_ROOT / ".env.local"
_ENV_FILE = str(_ROOT_ENV_LOCAL)


class OpenAIConfig(BaseSettings):
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.openai.com/v1")
    model: str = Field(default="gpt-4o")
    reasoning_model: str = Field(default="gpt-4o")
    fast_model: str = Field(default="gpt-4o-mini")
    websearch_model: str = Field(default="gpt-4o")
    websearch_timeout_s: int = Field(default=35, ge=10, le=90)
    websearch_max_results: int = Field(default=4, ge=1, le=8)
    websearch_context_size: str = Field(default="medium")

    model_config = {"env_prefix": "OPENAI_", "env_file": _ENV_FILE, "extra": "ignore"}


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8100)

    model_config = {"env_prefix": "HYPOTHESIS_GPT_", "env_file": _ENV_FILE, "extra": "ignore"}


class RuntimeConfig(BaseSettings):
    request_timeout_s: int = Field(default=45, ge=10, le=180)
    max_retries: int = Field(default=1, ge=0, le=5)
    enable_external_grounding: bool = Field(default=True)
    external_grounding_timeout_s: int = Field(default=20, ge=5, le=90)
    external_grounding_max_docs: int = Field(default=8, ge=2, le=24)

    model_config = {"env_prefix": "HYPOTHESIS_GPT_", "env_file": _ENV_FILE, "extra": "ignore"}


class Settings(BaseSettings):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    model_config = {"env_file": _ENV_FILE, "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
