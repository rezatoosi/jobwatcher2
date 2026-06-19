"""Load and validate application configuration from a YAML file."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

@dataclass
class NetworkConfig:
    proxy: str = ""
    request_timeout: int = 15

@dataclass(frozen=True)
class AppConfig:
    """Holds all configuration values used across the application."""

    subreddits: list[str]
    keywords: dict[str, int]
    min_score: int
    request_delay: int
    fetch_limit: int
    network: NetworkConfig = field(default_factory=NetworkConfig)


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
        keywords=_require_dict(data, "keywords"),
        min_score=_require_int(data, "min_score"),
        request_delay=_require_int(data, "request_delay"),
        fetch_limit=_require_int(data, "fetch_limit"),
        network=NetworkConfig(
            proxy=network_data.get("proxy", ""),
            request_timeout=int(network_data.get("request_timeout", 15)),
        )
    )


def _require_list(data: dict, key: str) -> list[str]:
    """Return a non-empty list value from the config, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Config field '{key}' must be a non-empty list")
    return value


def _require_dict(data: dict, key: str) -> dict[str, int]:
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


def _require_int(data: dict, key: str) -> int:
    """Return an integer value from the config, or raise ValueError."""
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Config field '{key}' must be an integer")
    return value
