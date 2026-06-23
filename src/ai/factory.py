# src/ai/factory.py
"""Factory for creating AI clients by provider.

Responsibility is limited to object construction. Config loading and
file I/O stay outside, so the factory remains easy to test and loosely
coupled.
"""

from typing import Union

from .base import AIClient, AIProvider, AIClientError
from .providers import (
    GroqClient,
    OpenRouterClient,
    TogetherClient,
    GoogleClient,
    OpenAICompatibleGenericClient,
    CerebrasClient,
    HyperbolicClient,
)


# Maps each provider to its client class.
# OPENAI_COMPATIBLE is handled separately because it needs base_url.
_PROVIDER_MAP = {
    AIProvider.GROQ: GroqClient,
    AIProvider.OPENROUTER: OpenRouterClient,
    AIProvider.TOGETHER: TogetherClient,
    AIProvider.GOOGLE: GoogleClient,
    AIProvider.CEREBRAS: CerebrasClient,
    AIProvider.HYPERBOLIC: HyperbolicClient,
}


def create_client(
    provider: Union[AIProvider, str],
    api_key: str,
    model: str = "",
    proxy: str = "",
    timeout: int = 30,
    base_url: str = "",
) -> AIClient:
    """Create an AI client for the given provider.

    Args:
        provider: AIProvider enum or its string value (e.g. "groq").
        api_key: API key for the provider.
        model: Model name. Empty string uses the provider's default.
        proxy: Optional proxy URL (http/https/socks5).
        timeout: Request timeout in seconds.
        base_url: Required only for OPENAI_COMPATIBLE providers
                  (LM Studio, Ollama, vLLM, custom endpoints).

    Returns:
        A ready-to-use AIClient instance.

    Raises:
        AIClientError: If the provider is unknown or required args are missing.
    """
    provider = _normalize_provider(provider)

    # The generic OpenAI-compatible client needs an explicit base_url.
    if provider == AIProvider.OPENAI_COMPATIBLE:
        if not base_url:
            raise AIClientError(
                "OPENAI_COMPATIBLE provider requires a base_url"
            )
        return OpenAICompatibleGenericClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            proxy=proxy,
            timeout=timeout,
        )

    client_class = _PROVIDER_MAP.get(provider)
    if client_class is None:
        raise AIClientError(f"Unsupported provider: {provider}")

    return client_class(
        api_key=api_key,
        model=model,
        proxy=proxy,
        timeout=timeout,
    )


def _normalize_provider(provider: Union[AIProvider, str]) -> AIProvider:
    """Accept either an AIProvider enum or its string value."""
    if isinstance(provider, AIProvider):
        return provider
    try:
        return AIProvider(provider.lower())
    except ValueError:
        valid = ", ".join(p.value for p in AIProvider)
        raise AIClientError(
            f"Unknown provider '{provider}'. Valid options: {valid}"
        )
