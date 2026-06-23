"""Manage multiple AI providers with priority-based selection and fallback."""

import logging
from typing import Optional

from .base import AIResponse, AIClientError, RateLimitError, AuthenticationError
from .factory import create_client

logger = logging.getLogger(__name__)


class AIProviderManager:
    """Select and call AI providers by priority, falling back on failure.

    The manager builds clients lazily from an ordered list of provider
    configs. On each request it tries providers from highest priority
    (lowest number) to lowest, returning the first successful response.
    """

    def __init__(self, ai_config, network_config=None) -> None:
        """Initialize the manager from parsed config objects.

        Args:
            ai_config: An AIConfig with `enabled` and `providers`.
            network_config: Optional NetworkConfig for proxy/timeout.
        """
        self._enabled = bool(ai_config.enabled) if ai_config else False
        proxy = network_config.proxy if network_config else ""
        timeout = network_config.request_timeout if network_config else 30

        # Filter enabled providers, then sort by priority ascending
        enabled_providers = [
            p for p in (ai_config.providers if ai_config else ())
            if p.enabled
        ]

        # Sort by priority ascending; lower number means higher priority.
        sorted_configs = sorted(enabled_providers, key=lambda p: p.priority)

        self._clients: list[tuple[str, object]] = []
        for cfg in sorted_configs:
            try:
                client = create_client(
                    provider=cfg.name,
                    api_key=cfg.api_key,
                    model=cfg.model,
                    proxy=proxy,
                    timeout=timeout,
                    base_url=cfg.base_url,
                )
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Skipping provider '%s': failed to build client (%s)",
                    cfg.name,
                    exc,
                )
                continue
            self._clients.append((cfg.name, client))

    @property
    def enabled(self) -> bool:
        """Whether the AI layer is enabled and has at least one client."""
        return self._enabled and bool(self._clients)

    def send_request(
        self,
        user_prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Send a request to the first available provider by priority.

        Tries each provider in order. Authentication and rate-limit
        errors trigger a fallback to the next provider. The last error
        is reported if all providers fail.

        Returns:
            An AIResponse. On total failure, `success` is False and
            `error` describes the last failure.
        """
        if not self.enabled:
            return AIResponse(
                content="",
                provider="none",
                model="",
                success=False,
                error="AI layer is disabled or has no configured providers",
            )

        last_error = "No providers attempted"

        for name, client in self._clients:
            try:
                response = client.send_request(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except (RateLimitError, AuthenticationError) as exc:
                logger.warning(
                    "Provider '%s' unavailable (%s); falling back",
                    name,
                    exc,
                )
                last_error = f"{name}: {exc}"
                continue
            except AIClientError as exc:
                logger.warning(
                    "Provider '%s' failed (%s); falling back", name, exc
                )
                last_error = f"{name}: {exc}"
                continue

            if response.success:
                return response

            logger.warning(
                "Provider '%s' returned failure (%s); falling back",
                name,
                response.error,
            )
            last_error = f"{name}: {response.error}"

        return AIResponse(
            content="",
            provider="none",
            model="",
            success=False,
            error=f"All providers failed. Last error: {last_error}",
        )

    def list_providers(self) -> list[str]:
        """Return provider names in priority order."""
        return [name for name, _ in self._clients]
