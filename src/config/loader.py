"""Load and validate application configuration from a YAML file."""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

@dataclass
class NetworkConfig:
    """Network-related settings."""
    proxy: str = ""
    request_timeout: int = 15


@dataclass(frozen=True)
class AIProviderConfig:
    """Configuration for a single AI provider."""

    name: str
    enabled: bool
    api_key: str
    model: str
    priority: int
    base_url: str = ""  # used only by openai_compatible generic provider


@dataclass(frozen=True)
class AIConfig:
    """Holds the AI layer configuration."""

    enabled: bool
    providers: tuple[AIProviderConfig, ...]


@dataclass(frozen=True)
class AppConfig:
    """Holds all configuration values used across the application."""

    subreddits: list[str]
    keywords: dict[str, int]
    filters: Optional[dict[str, dict]]
    min_score: int
    request_delay: int
    fetch_limit: int
    network: NetworkConfig = field(default_factory=NetworkConfig)
    ai: Optional[AIConfig] = None


_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def _resolve_env(value: str) -> str:
    """Replace ${VAR} placeholders with environment variable values.

    Raises:
        ValueError: If a referenced environment variable is not set.
    """
    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            raise ValueError(f"Environment variable '{var_name}' is not set")
        return env_value

    return _ENV_PATTERN.sub(replace, value)


def load_config(config_path: Path) -> AppConfig:
    """Read a YAML config file and return a validated AppConfig.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        An AppConfig instance populated with the file's values.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If a required field is missing or empty.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    network_data = data.get("network", {}) or {}

    return AppConfig(
        subreddits=_require_list(data, "subreddits"),
        keywords=_require_dict_int(data, "keywords"),
        filters=_require_dict_in_dict(data, "filters"),
        min_score=_require_int(data, "min_score"),
        request_delay=_require_int(data, "request_delay"),
        fetch_limit=_require_int(data, "fetch_limit"),
        network=NetworkConfig(
            proxy=network_data.get("proxy", ""),
            request_timeout=int(network_data.get("request_timeout", 15)),
        ),
        ai=_load_ai_config(data),
    )


def _load_ai_config(data: dict) -> Optional[AIConfig]:
    """Parse the optional 'ai_providers' section into an AIConfig."""
    ai_data = data.get("ai_providers")
    if not ai_data:
        return None
    if not isinstance(ai_data, dict):
        raise ValueError("Config field 'ai_providers' must be a dictionary")

    enabled = bool(ai_data.get("enabled", False))
    raw_providers = ai_data.get("providers", []) or []

    if not isinstance(raw_providers, list):
        raise ValueError("Config field 'ai_providers.providers' must be a list")

    providers: list[AIProviderConfig] = []
    for index, entry in enumerate(raw_providers):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Provider at index {index} must be a dictionary"
            )

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"Provider at index {index} must have a non-empty 'name'"
            )
        
        provider_enabled = bool(entry.get("enabled", True))

        raw_key = entry.get("api_key", "")
        api_key = _resolve_env(str(raw_key)) if raw_key else ""

        providers.append(
            AIProviderConfig(
                name=name,
                enabled=provider_enabled,
                api_key=api_key,
                model=str(entry.get("model", "")),
                priority=int(entry.get("priority", 100)),
                base_url=str(entry.get("base_url", "")),
            )
        )

    return AIConfig(enabled=enabled, providers=tuple(providers))


def _require_list(data: dict, key: str) -> list[str]:
    """Return a non-empty list value from the config, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Config field '{key}' must be a non-empty list")
    return value


def _require_dict_int(data: dict, key: str) -> dict[str, int]:
    """Return a non-empty dict with string keys and int values, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"Config field '{key}' must be a non-empty dictionary")

    for k, v in value.items():
        if not isinstance(k, str):
            raise ValueError(f"Config field '{key}' must have string keys")
        if not isinstance(v, int):
            raise ValueError(f"Config field '{key}' must have integer values")

    return value


def _require_dict_in_dict(data: dict, key: str) -> dict[str, dict]:
    """Return a non-empty dict with string keys and dict values, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, dict) or not value:
        raise ValueError(f"Config field '{key}' must be a non-empty dictionary")

    for k, v in value.items():
        if not isinstance(k, str):
            raise ValueError(f"Config field '{key}' must have string keys")
        if not isinstance(v, dict):
            raise ValueError(f"Config field '{key}' must have dict values")

    return value


def _require_int(data: dict, key: str) -> int:
    """Return an integer value from the config, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Config field '{key}' must be an integer")
    return value
