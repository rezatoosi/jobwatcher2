# src/ai/providers/cerebras.py
import requests
from typing import Optional

from ..base import AIResponse, AIClientError
from .openai_compatible import OpenAICompatibleClient


class CerebrasClient(OpenAICompatibleClient):
    PROVIDER_NAME = "cerebras"
    BASE_URL = "https://api.cerebras.ai/v1/chat/completions"
    DEFAULT_MODEL = "gpt-oss-120b"

    # gpt-oss-120b is a reasoning model: tokens are spent on the
    # hidden reasoning channel first, so small max_tokens leaves nothing
    # for the final answer.
    MIN_MAX_TOKENS = 10 #1024

    def send_request(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.0,
    ) -> AIResponse:
        # Ensure reasoning models have enough room for a final answer.
        effective_max_tokens = max(max_tokens, self.MIN_MAX_TOKENS)

        headers = self._build_headers()
        payload = self._build_payload(
            user_prompt, system_prompt, effective_max_tokens, temperature
        )

        try:
            response = requests.post(
                self.BASE_URL,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                proxies=self.proxies,
            )

            self._handle_error_status(response)
            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            # Reasoning models may leave `content` empty and put the
            # answer in `reasoning`. Fall back to it when needed.
            content = message.get("content") or message.get("reasoning") or ""

            tokens = data.get("usage", {}).get("total_tokens")

            return AIResponse(
                content=content,
                provider=self.PROVIDER_NAME,
                model=self.model,
                success=True,
                tokens_used=tokens,
            )
        except AIClientError:
            raise
        except requests.RequestException as e:
            raise AIClientError(f"{self.PROVIDER_NAME} request failed: {str(e)}")
        except (KeyError, ValueError) as e:
            raise AIClientError(
                f"Invalid {self.PROVIDER_NAME} response format: {str(e)}"
            )
