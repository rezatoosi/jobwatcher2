# src/ai/providers/together.py
from .openai_compatible import OpenAICompatibleClient


class TogetherClient(OpenAICompatibleClient):
    PROVIDER_NAME = "together"
    BASE_URL = "https://api.together.xyz/v1/chat/completions"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
