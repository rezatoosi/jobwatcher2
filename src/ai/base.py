# src/ai/base.py
"""Base classes and types for AI client abstraction."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI_COMPATIBLE = "openai_compatible"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    GOOGLE = "google"
    CEREBRAS = "cerebras"
    HYPERBOLIC = "hyperbolic"


@dataclass
class AIResponse:
    """Standardized AI response."""
    content: str
    provider: str
    model: str
    success: bool = True
    tokens_used: Optional[int] = None
    error: Optional[str] = None


class AIClientError(Exception):
    """Base exception for AI client errors."""
    pass


class RateLimitError(AIClientError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(AIClientError):
    """Authentication failed."""
    pass


class ModelNotAvailableError(AIClientError):
    """Requested model not available."""
    pass


class AIClient(ABC):
    """Abstract base class for AI clients."""

    # Overridden by each subclass; used in error messages.
    PROVIDER_NAME: str = "ai"

    def __init__(self, api_key: str, model: str):
        """
        Initialize AI client.

        Args:
            api_key: API key for authentication (from .env)
            model: Model identifier (from config.yaml)
        """
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def send_request(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.0
    ) -> AIResponse:
        """
        Send request to AI provider.

        Args:
            user_prompt: User prompt
            system_prompt: System instructions (optional)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            AIResponse with content and metadata

        Raises:
            RateLimitError: Rate limit exceeded
            AuthenticationError: Invalid API key
            ModelNotAvailableError: Model not found
            AIClientError: Other errors
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is available.

        Returns:
            True if provider responds successfully
        """
        pass

    def _handle_error_status(self, status_code: int, detail: str = "") -> None:
        """
        Map an HTTP error status code to a specific exception.

        Transport-agnostic: takes only the status code and an already-extracted
        detail string, so it works regardless of the HTTP client a provider uses.
        Each provider is responsible for extracting `detail` from its own
        response format before calling this.

        Args:
            status_code: HTTP status code from the provider's response.
            detail: Human-readable error message extracted from the response body.

        Raises:
            RateLimitError, AuthenticationError, ModelNotAvailableError,
            or AIClientError depending on the status code.
        """
        if status_code < 400:
            return

        name = self.PROVIDER_NAME
        detail = detail or "no detail"

        if status_code == 400:
            raise AIClientError(f"{name} bad request: {detail}")
        if status_code == 401:
            raise AuthenticationError(f"Invalid {name} API key: {detail}")
        if status_code == 402:
            raise AIClientError(f"{name} payment required (402): {detail}")
        if status_code == 403:
            raise AuthenticationError(
                f"{name} access forbidden "
                f"(possibly geo-restricted or insufficient permissions): {detail}"
            )
        if status_code == 404:
            raise ModelNotAvailableError(
                f"Model '{self.model}' not found on {name}: {detail}"
            )
        if status_code == 422:
            raise AIClientError(f"{name} unprocessable request: {detail}")
        if status_code == 429:
            raise RateLimitError(f"{name} rate limit exceeded: {detail}")
        if status_code in (500, 502, 503, 504):
            raise AIClientError(
                f"{name} server error ({status_code}, retryable): {detail}"
            )

        # Fallback for any other 4xx/5xx.
        raise AIClientError(f"{name} request failed ({status_code}): {detail}")
