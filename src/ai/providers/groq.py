# src/ai/providers/groq.py
from .openai_compatible import OpenAICompatibleClient


class GroqClient(OpenAICompatibleClient):
    PROVIDER_NAME = "groq"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
