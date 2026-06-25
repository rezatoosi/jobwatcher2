# src/config/loader.py
"""Configuration loader with environment variable expansion."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


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
    providers: List[AIProviderConfig] = Field(default_factory=list)


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
    request_delay: int = 60
    fetch_limit: int = 50
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    @field_validator("filters", mode="before")
    @classmethod
    def parse_filters(cls, v: Any) -> Dict[str, SubredditFilter]:
        """Convert dict of dicts to dict of SubredditFilter objects."""
        if not isinstance(v, dict):
            return {}
        return {
            subreddit: SubredditFilter(**rules)
            for subreddit, rules in v.items()
        }


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
