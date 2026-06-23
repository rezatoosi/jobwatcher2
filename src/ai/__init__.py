# src/ai/__init__.py
"""AI client abstraction layer."""

from .base import (
    AIClient,
    AIResponse,
    AIProvider,
    AIClientError,
    RateLimitError,
    AuthenticationError,
    ModelNotAvailableError,
)

from .providers import (
    GroqClient,
    OpenRouterClient,
    TogetherClient,
    GoogleClient,
    OpenAICompatibleClient,         # shared base for OpenAI-compatible APIs
    OpenAICompatibleGenericClient,  # generic client with dynamic base_url
)

from .factory import create_client

__all__ = [
    # Base classes
    "AIClient",
    "AIResponse",
    "AIProvider",
    # Exceptions
    "AIClientError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotAvailableError",
    # Provider implementations
    "GroqClient",
    "OpenRouterClient",
    "TogetherClient",
    "GoogleClient",
    "OpenAICompatibleClient",
    "OpenAICompatibleGenericClient",
    # Factory
    "create_client",
]
