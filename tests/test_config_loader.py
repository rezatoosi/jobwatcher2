# tests/test_config_loader.py
"""Tests for the configuration loader."""

import pytest

from src.config.loader import AppConfig, load_config


def _write_config(tmp_path, body: str):
    """Write a config.yaml into tmp_path and return its Path."""
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# --- Basic loading ---

def test_load_valid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "secret-123")
    cfg = _write_config(tmp_path, """
      subreddits:
        - python
      keywords:
        pytorch: 15.0
      ai_providers:
        enabled: true
        max_tokens: 512
        providers:
          - name: openai
            enabled: true
            api_key: ${MY_API_KEY}
            model: gpt-4o-mini
            priority: 1
      """)
    config = load_config(cfg)

    assert isinstance(config, AppConfig)
    assert config.subreddits == ["python"]
    assert config.keywords == {"pytorch": 15.0}
    assert config.ai_providers.max_tokens == 512
    # api_key should be expanded from the environment
    assert config.ai_providers.providers[0].api_key == "secret-123"


def test_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.yaml")


# --- Defaults ---

def test_defaults_applied(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "secret-123")
    cfg = _write_config(tmp_path, """
      subreddits:
        - python
      keywords:
        pytorch: 15.0
      ai_providers:
        enabled: true
        providers:
          - name: openai
            api_key: ${MY_API_KEY}
            model: gpt-4o-mini
      """)
    config = load_config(cfg)

    assert config.request_delay == 60
    assert config.fetch_limit == 50
    assert config.scoring.keyword_threshold == 20.0
    assert config.rate_limiting.max_retries == 3
    assert config.notifiers.enabled is False
    assert config.network.request_timeout == 15


# --- Environment variable expansion ---

def test_missing_env_var_raises_valueerror(tmp_path, monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    cfg = _write_config(tmp_path, """
      subreddits:
        - python
      keywords:
        pytorch: 15.0
      ai_providers:
        enabled: true
        providers:
          - name: openai
            api_key: ${MISSING_KEY}
            model: gpt-4o-mini
      """)
    # validator raises ValueError, load_config wraps it but it's still ValueError
    with pytest.raises(ValueError, match="MISSING_KEY"):
        load_config(cfg)


# --- Notifiers behavior ---

def test_notifiers_dropped_when_globally_off(tmp_path, monkeypatch):
    """Telegram block with an unset env var must NOT fail when notifiers are off."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    cfg = _write_config(tmp_path, """
      subreddits:
        - python
      keywords:
        pytorch: 15.0
      ai_providers:
        enabled: true
        providers:
          - name: openai
            api_key: dummy
            model: gpt-4o-mini
      notifiers:
        enabled: false
        telegram:
          enabled: true
          token: ${TELEGRAM_BOT_TOKEN}
          chat_id: ${TELEGRAM_CHAT_ID}
      """)
    config = load_config(cfg)

    assert config.notifiers.enabled is False
    assert config.notifiers.telegram is None


def test_telegram_env_expanded_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    cfg = _write_config(tmp_path, """
      subreddits:
        - python
      keywords:
        pytorch: 15.0
      ai_providers:
        enabled: true
        providers:
          - name: openai
            api_key: dummy
            model: gpt-4o-mini
      notifiers:
        enabled: true
        telegram:
          enabled: true
          token: ${TELEGRAM_BOT_TOKEN}
          chat_id: ${TELEGRAM_CHAT_ID}
      """)
    config = load_config(cfg)

    assert config.notifiers.telegram.token == "123:ABC"
    assert config.notifiers.telegram.chat_id == "999"


# --- Filters parsing ---

def test_filter_keys_are_lowercased(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_API_KEY", "secret-123")
    cfg = _write_config(tmp_path, """
      subreddits:
        - Python
      keywords:
        pytorch: 15.0
      filters:
        Python:
          title_must_contain:
            - hiring
          title_must_not_contain:
            - unpaid
      ai_providers:
        enabled: true
        providers:
          - name: openai
            api_key: ${MY_API_KEY}
            model: gpt-4o-mini
      """)
    config = load_config(cfg)

    assert "python" in config.filters
    assert "Python" not in config.filters
    assert config.filters["python"].title_must_contain == ["hiring"]
