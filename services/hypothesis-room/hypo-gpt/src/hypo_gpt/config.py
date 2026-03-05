"""Configuration for standalone GPT hypothesis service."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class OpenAIConfig(BaseSettings):
    api_key: str = Field(default="")
    model: str = Field(default="gpt-4o")
    reasoning_model: str = Field(default="gpt-4o")
    fast_model: str = Field(default="gpt-4o-mini")

    model_config = {"env_prefix": "OPENAI_", "env_file": (".env", "../.env"), "extra": "ignore"}


class ServerConfig(BaseSettings):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8100)

    model_config = {"env_prefix": "HYPOTHESIS_GPT_", "env_file": (".env", "../.env"), "extra": "ignore"}


class RuntimeConfig(BaseSettings):
    request_timeout_s: int = Field(default=45, ge=10, le=180)
    max_retries: int = Field(default=1, ge=0, le=5)

    model_config = {"env_prefix": "HYPOTHESIS_GPT_", "env_file": (".env", "../.env"), "extra": "ignore"}


class Settings(BaseSettings):
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    model_config = {"env_file": (".env", "../.env"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
