# src/ai/providers/hyperbolic.py
from .openai_compatible import OpenAICompatibleClient


class HyperbolicClient(OpenAICompatibleClient):
    PROVIDER_NAME = "hyperbolic"
    BASE_URL = "https://api.hyperbolic.xyz/v1/chat/completions"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
