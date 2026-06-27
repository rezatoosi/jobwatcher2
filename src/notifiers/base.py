# src/notifiers/base.py
"""Base notifier interface for outbound notification transports.

A notifier is a thin transport layer: it knows how to deliver a single
text message over one channel (Telegram, email, ...). It does not know
about posts, scoring, or message formatting — that is the job of the
notifications service. Keeping transports behind one `send` contract
makes them interchangeable and independently testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NotificationResult:
    """Outcome of a single send attempt.

    Notifiers return this instead of raising on delivery failure, so the
    caller (the notifications service) can decide whether to continue a
    batch, retry later, or mark a post as notified. Only a `success`
    result should trigger `mark_notified`.
    """

    success: bool
    error: Optional[str] = None
    # Optional channel-specific identifier (e.g. Telegram message_id),
    # handy for logging and future edit/delete support.
    message_ref: Optional[str] = None

    @classmethod
    def ok(cls, message_ref: Optional[str] = None) -> "NotificationResult":
        return cls(success=True, message_ref=message_ref)

    @classmethod
    def failed(cls, error: str) -> "NotificationResult":
        return cls(success=False, error=error)


class Notifier(ABC):
    """Abstract transport for delivering text notifications.

    Concrete implementations own authentication, the wire protocol, rate
    limiting, retries, and any channel-specific constraints (such as
    splitting oversized messages). Configuration (tokens, destination
    ids, enabled flag) is injected at construction time so the transport
    stays decoupled from global config loading — mirroring how `AIClient`
    receives its provider config.
    """

    #: Human-readable channel name, used in logs (e.g. "telegram").
    name: str = "notifier"

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether this notifier is configured and allowed to send.

        The service should skip sending entirely when this is False,
        rather than calling `send` and handling a guaranteed failure.
        """
        raise NotImplementedError

    @abstractmethod
    def send(
        self, text: str, *, parse_mode: Optional[str] = None
    ) -> NotificationResult:
        """Deliver a single text message over the channel.

        Args:
            text: The fully formatted message body. The service owns
                content and formatting; the notifier only transports it,
                splitting oversized messages if the channel requires it.
            parse_mode: Optional channel-specific render hint (e.g.
                "Markdown" or "HTML" for Telegram). Implementations that
                do not support it should ignore it.

        Returns:
            A NotificationResult describing success or failure. Transport
            errors are captured in the result rather than raised, so a
            batch of notifications can continue past a single failure.
        """
        raise NotImplementedError
