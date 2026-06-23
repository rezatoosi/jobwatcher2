# src/ai/providers/google.py
"""Google AI Studio (Gemini) provider.

Does NOT follow the OpenAI-compatible shape, so it inherits directly
from AIClient instead of OpenAICompatibleClient.
"""

import requests
from typing import Optional
from ..base import AIClient, AIResponse, AIClientError


class GoogleClient(AIClient):
    PROVIDER_NAME = "google"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-2.5-flash"

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

    # --- request building ----------------------------------------------

    def _build_url(self) -> str:
        # API key goes in the query string for the Generative Language API.
        return f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"

    def _build_payload(
        self,
        user_prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> dict:
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        # Gemini uses a dedicated systemInstruction field, not a message role.
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        return payload

    # --- error handling ------------------------------------------------

    def _handle_error_status(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return
        detail = self._extract_error_detail(response)
        super()._handle_error_status(response.status_code, detail)

    @staticmethod
    def _extract_error_detail(response: requests.Response) -> str:
        """Gemini error body: {"error": {"message": ..., "status": ...}}."""
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

    # --- response parsing ----------------------------------------------

    @staticmethod
    def _extract_content(data: dict) -> str:
        """Pull text from candidates[0].content.parts[*].text.

        A response can have multiple parts; join them.
        """
        candidates = data.get("candidates")
        if not candidates:
            # Often caused by safety blocking or empty generation.
            feedback = data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason")
            if block_reason:
                raise AIClientError(f"Gemini blocked the prompt: {block_reason}")
            raise AIClientError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        texts = [p.get("text", "") for p in parts if "text" in p]
        if not texts:
            finish = candidates[0].get("finishReason", "unknown")
            raise AIClientError(f"Gemini returned no text (finishReason={finish})")
        return "".join(texts)

    # --- public API ----------------------------------------------------

    def send_request(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 100,
        temperature: float = 0.0,
    ) -> AIResponse:
        url = self._build_url()
        payload = self._build_payload(user_prompt, system_prompt, max_tokens, temperature)

        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
                proxies=self.proxies,
            )
            self._handle_error_status(response)
            response.raise_for_status()

            data = response.json()
            content = self._extract_content(data)
            tokens = data.get("usageMetadata", {}).get("totalTokenCount")

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
            response = self.send_request(user_prompt="Hi", max_tokens=10, temperature=0.0)
            return response.success
        except AIClientError:
            return False
