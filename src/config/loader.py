# src/config/loader.py
"""Configuration loader with environment variable expansion."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class SubredditFilter(BaseModel):
    """Filter rules for a specific subreddit."""

    title_must_contain: List[str] = Field(default_factory=list)
    title_must_not_contain: List[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    """Scoring pipeline configuration."""

    keyword_threshold: float = Field(
        default=20.0,
        description="Minimum keyword score to pass to AI stage",
    )
    ai_system_prompt: str = Field(
        default="",
        description="System prompt for AI scorer (supports {skills} placeholder)",
    )


class AIProviderConfig(BaseModel):
    """Configuration for a single AI provider."""

    name: str
    enabled: bool = False
    api_key: str
    model: str
    priority: int = 100
    base_url: str = Field(
        default="",
        description="Base URL, required only for OPENAI_COMPATIBLE providers",
    )

    @field_validator("api_key")
    @classmethod
    def expand_env_var(cls, v: str) -> str:
        """Expand ${VAR_NAME} to environment variable value."""
        if match := re.match(r"\$\{([^}]+)\}", v):
            var_name = match.group(1)
            value = os.environ.get(var_name)
            if not value:
                raise ValueError(f"Environment variable {var_name!r} is not set")
            return value
        return v


class AIProvidersConfig(BaseModel):
    """AI providers configuration."""

    enabled: bool = True
    max_tokens: int = Field(
        default=256,
        description="Token budget for the AI scorer response (shared across providers)",
    )
    providers: List[AIProviderConfig] = Field(default_factory=list)


class RateLimitingConfig(BaseModel):
    """Rate limiting and backoff configuration (global)."""

    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for rate limit errors",
    )
    initial_backoff: float = Field(
        default=5.0,
        description="Initial delay in seconds before first retry",
    )
    max_backoff: float = Field(
        default=60.0,
        description="Maximum delay in seconds between retries",
    )
    backoff_multiplier: float = Field(
        default=2.0,
        description="Multiplier for exponential backoff",
    )


class TelegramNotifierConfig(BaseModel):
    """Telegram notification settings."""

    enabled: bool = False
    token: str = ""
    chat_id: str = ""
    timeout: int = 10
    max_retries: int = 3
    initial_backoff: float = 2.0
    max_backoff: float = 30.0
    backoff_multiplier: float = 2.0

    @model_validator(mode="after")
    def expand_env_vars(self) -> "TelegramNotifierConfig":
        """Expand ${VAR_NAME} placeholders only when enabled."""
        if not self.enabled:
            return self
        for field in ("token", "chat_id"):
            value = getattr(self, field)
            if match := re.match(r"\$\{([^}]+)\}", value):
                var_name = match.group(1)
                env_value = os.environ.get(var_name)
                if not env_value:
                    raise ValueError(
                        f"Environment variable {var_name!r} is not set"
                    )
                setattr(self, field, env_value)
        return self


class NotifiersConfig(BaseModel):
    """Container for all notification channels.

    Holds a global ``enabled`` switch plus one optional config block per
    channel type. Add new channels (e.g. ``discord``) as additional fields.
    """

    enabled: bool = False
    telegram: Optional[TelegramNotifierConfig] = None

    @model_validator(mode="before")
    @classmethod
    def drop_channels_when_globally_off(cls, data: Any) -> Any:
        """Strip channel configs before validation if globally disabled.

        Running this in ``before`` mode means the child models (e.g.
        ``TelegramNotifierConfig``) are never constructed when notifiers are
        off, so a missing ``TELEGRAM_BOT_TOKEN`` won't fail validation.
        """
        if isinstance(data, dict) and not data.get("enabled", False):
            return {"enabled": False}
        return data


class NetworkConfig(BaseModel):
    """Network and proxy settings."""

    proxy: str = ""
    request_timeout: int = 15


class AppConfig(BaseModel):
    """Application configuration loaded from YAML."""

    subreddits: List[str]
    filters: Dict[str, SubredditFilter] = Field(default_factory=dict)
    keywords: Dict[str, float]
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    ai_providers: AIProvidersConfig
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)
    request_delay: int = 60
    fetch_limit: int = 50
    cleanup_before_fetch: bool = False
    cleanup_until: int = 30
    notifiers: NotifiersConfig = Field(default_factory=NotifiersConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @field_validator("filters", mode="before")
    @classmethod
    def parse_filters(cls, v: Any) -> Dict[str, SubredditFilter]:
        """Convert dict of dicts to dict of SubredditFilter objects."""
        if not isinstance(v, dict):
            return {}
        return {
            subreddit.lower(): SubredditFilter(**rules)
            for subreddit, rules in v.items()
        }

    @field_validator("cleanup_until")
    @classmethod
    def validate_cleanup_until(cls, v: int) -> int:
        """Ensure cleanup_until is a positive number of days."""
        if v <= 0:
            raise ValueError("cleanup_until must be a positive integer")
        return v


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """Load and validate configuration from YAML file.

    Args:
        config_path: Path to config.yaml. Defaults to project root.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: Config file not found.
        ValueError: Invalid YAML or schema validation failed.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    try:
        return AppConfig(**raw_config)
    except Exception as e:
        raise ValueError(f"Config validation failed: {e}") from e
