# src/ai/providers/openai_compatible.py
"""Shared base for all OpenAI-compatible providers."""

import requests
from typing import Optional
from ..base import AIClient, AIResponse, AIClientError


class OpenAICompatibleClient(AIClient):
    """Base for providers exposing an OpenAI-compatible /chat/completions API.

    Subclasses only need to set BASE_URL, PROVIDER_NAME, DEFAULT_MODEL,
    and optionally override `_extra_headers()`.
    """

    BASE_URL: str = ""          # must be set by subclass
    DEFAULT_MODEL: str = ""     # must be set by subclass

    def __init__(
        self,
        api_key: str,
        model: str = "",
        proxy: str = "",
        timeout: int = 30,
    ):
        super().__init__(api_key, model or self.DEFAULT_MODEL)
        self.timeout = timeout
        self.proxies = {"http": proxy, "https": proxy} if proxy else None

    # --- hooks subclasses can override ---------------------------------

    def _extra_headers(self) -> dict:
        """Provider-specific headers (e.g. OpenRouter referer). Empty by default."""
        return {}

    # --- shared implementation -----------------------------------------

    def _build_headers(self) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(self._extra_headers())
        return headers

    def _build_payload(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    def _handle_error_status(self, response: requests.Response) -> None:
        """Extract detail from the response body, then delegate to base."""
        if response.status_code < 400:
            return
        detail = self._extract_error_detail(response)
        super()._handle_error_status(response.status_code, detail)

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        """OpenAI-compatible error body: {"error": {"message": ...}}."""
        try:
            data = response.json()
            if isinstance(data, dict):
                error = data.get("error")
                if isinstance(error, dict):
                    return error.get("message", str(error))
                if error:
                    return str(error)
            return response.text[:200]
        except ValueError:
            return response.text[:200] if response.text else "no detail"

    def send_request(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.0,
    ) -> AIResponse:
        headers = self._build_headers()
        payload = self._build_payload(user_prompt, system_prompt, max_tokens, temperature)

        try:
            response = requests.post(
                self.BASE_URL,
                json=payload,
                headers=headers,
                timeout=self.timeout,
                proxies=self.proxies,
            )

            # print("RAW RESPONSE:", response.json())

            self._handle_error_status(response)
            response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
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

    def is_available(self) -> bool:
        try:
            response = self.send_request(user_prompt="Hi", max_tokens=5, temperature=0.0)
            return response.success
        except AIClientError:
            return False
