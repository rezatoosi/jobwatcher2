# src/ai/providers/openrouter.py
from .openai_compatible import OpenAICompatibleClient


class OpenRouterClient(OpenAICompatibleClient):
    PROVIDER_NAME = "openrouter"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

    def _extra_headers(self) -> dict:
        # OpenRouter uses these for routing/analytics; optional but recommended.
        return {
            "HTTP-Referer": "https://github.com/rezatoosi",
            "X-Title": "reddit-job-scorer",
        }
