# src/ai/providers/openai_compatible_generic.py
from .openai_compatible import OpenAICompatibleClient


class OpenAICompatibleGenericClient(OpenAICompatibleClient):
    """For any self-hosted or third-party OpenAI-compatible endpoint
    (LM Studio, Ollama, vLLM, etc.). BASE_URL comes from config."""

    PROVIDER_NAME = "openai_compatible"

    def __init__(self, api_key: str, model: str, base_url: str,
                 proxy: str = "", timeout: int = 30):
        super().__init__(api_key, model, proxy=proxy, timeout=timeout)
        if not base_url:
            raise ValueError("base_url is required for openai_compatible provider")
        self.BASE_URL = base_url  # instance-level override
