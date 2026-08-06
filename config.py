"""
Centralized, typed application configuration.

Everything the app needs from the environment is declared here, once,
so no other module reads `os.environ` directly. This keeps config
discoverable (grep this file, not the whole repo) and gives us
validation for free via pydantic.

Usage:
    from config import settings
    settings.primary_model
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    """
    Application settings, populated from environment variables / .env file.

    Field names map to UPPER_SNAKE_CASE env vars automatically
    (e.g. `primary_model` <- `PRIMARY_MODEL`).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM providers ---
    anthropic_api_key: str = Field(default="", repr=False)
    openai_api_key: str = Field(default="", repr=False)

    # --- Model routing defaults ---
    # LiteLLM-style identifiers: "<provider>/<model-name>"
    # gpt-4o-mini as default while iterating on phases (cheap, fast).
    # Switch primary_model to an Anthropic model for the final quality pass.
    primary_model: str = "openai/gpt-4o-mini"
    fallback_model: str = "anthropic/claude-sonnet-4-5"

    # Ceiling on completion length per agent call. 4000 gives headroom
    # above the most verbose agent observed so far (notebook, ~2925
    # output tokens on a real run) without being wasteful on short
    # agents like persona (~270 tokens).
    max_tokens: int = 4000

    # --- App ---
    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    workspace_dir: Path = Path("./workspace")
    outputs_dir: Path = Path("./outputs")

    # --- Database ---
    database_url: str = "sqlite:///./ai_university.db"

    # --- Optional integrations (Phase 2+) ---
    tavily_api_key: str = Field(default="", repr=False)

    # --- Cost guardrails ---
    max_cost_per_run_usd: float = 2.00

    @field_validator("workspace_dir", "outputs_dir")
    @classmethod
    def _ensure_dir_exists(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    def validate_at_least_one_provider(self) -> None:
        """Raise a clear error early if no LLM provider is configured at all."""
        if not (self.has_anthropic or self.has_openai):
            raise RuntimeError(
                "No LLM provider configured. Set ANTHROPIC_API_KEY and/or "
                "OPENAI_API_KEY in your .env file (see .env.example)."
            )


# Single shared instance, imported everywhere else in the app.
settings = Settings()
