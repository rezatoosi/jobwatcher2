# src/notifiers/factory.py
"""Factory for building notifier instances from validated configuration.

Keeps construction logic in one place so new channels can be added by
extending ``build_notifiers`` with another guarded branch, without touching
call sites.
"""

from typing import List

from ..config.loader import NotifiersConfig, TelegramNotifierConfig
from .base import Notifier
from .telegram import TelegramNotifier


def build_notifiers(config: NotifiersConfig) -> List[Notifier]:
    """Build all enabled notifier instances from configuration.

    Honors the two-level enable switch: the global ``notifiers.enabled``
    flag and each channel's own ``enabled`` field. Returns an empty list
    when notifications are globally off or no channel is enabled.

    Args:
        config: Validated notifiers configuration block.

    Returns:
        List of ready-to-use :class:`Notifier` instances.
    """
    if not config.enabled:
        return []

    notifiers: List[Notifier] = []

    if config.telegram is not None and config.telegram.enabled:
        notifiers.append(_build_telegram(config.telegram))

    return notifiers


def _build_telegram(cfg: TelegramNotifierConfig) -> TelegramNotifier:
    """Map a validated Telegram config to a ``TelegramNotifier`` instance."""
    return TelegramNotifier(
        token=cfg.token,
        chat_id=cfg.chat_id,
        enabled=cfg.enabled,
        timeout=cfg.timeout,
        max_retries=cfg.max_retries,
        initial_backoff=cfg.initial_backoff,
        max_backoff=cfg.max_backoff,
        backoff_multiplier=cfg.backoff_multiplier,
    )
