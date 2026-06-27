# src/notifiers/telegram.py
"""Telegram notifier implementation with retry logic."""

import time
import logging
from typing import Optional

import requests

from .base import Notifier, NotificationResult

logger = logging.getLogger(__name__)


class TelegramNotifier(Notifier):
    """Send notifications via Telegram Bot API.
    
    Handles rate limits with exponential backoff, redacts tokens from logs,
    and returns structured results instead of raising exceptions.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        enabled: bool = True,
        timeout: int = 10,
        max_retries: int = 3,
        initial_backoff: float = 2.0,
        max_backoff: float = 30.0,
        backoff_multiplier: float = 2.0
    ):
        """
        Initialize Telegram notifier.

        Args:
            token: Bot token from BotFather (from .env via config)
            chat_id: Target chat ID (from .env via config)
            enabled: Whether notifications are active
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on rate limit (429)
            initial_backoff: Initial delay before first retry
            max_backoff: Maximum delay between retries
            backoff_multiplier: Exponential backoff multiplier
        """
        self._token = token
        self._chat_id = chat_id
        self._enabled = enabled
        self._timeout = timeout
        self._max_retries = max_retries
        self._initial_backoff = initial_backoff
        self._max_backoff = max_backoff
        self._backoff_multiplier = backoff_multiplier

        self._base_url = f"https://api.telegram.org/bot{self._token}"
        self._session = requests.Session()

    @property
    def enabled(self) -> bool:
        """Check if notifier is enabled."""
        return self._enabled

    def send(
        self,
        text: str,
        *,
        parse_mode: Optional[str] = None
    ) -> NotificationResult:
        """
        Send a message to the configured chat.

        Args:
            text: Message text (max 4096 characters per Telegram limit)
            parse_mode: Formatting mode ('Markdown', 'MarkdownV2', 'HTML')

        Returns:
            NotificationResult with success status and optional message_id
        """
        if not self._enabled:
            return NotificationResult(
                success=False,
                error="Notifier is disabled"
            )

        if not text.strip():
            return NotificationResult(
                success=False,
                error="Empty message text"
            )

        # Split message if longer than Telegram's 4096 character limit
        chunks = self._split_message(text)
        if len(chunks) > 1:
            logger.info(f"Message split into {len(chunks)} chunks")

        results = []
        for idx, chunk in enumerate(chunks):
            result = self._send_chunk(chunk, parse_mode, chunk_num=idx + 1)
            results.append(result)
            if not result.success:
                # Stop on first failure
                return result
            # Brief delay between chunks to avoid rate limits
            if idx < len(chunks) - 1:
                time.sleep(0.5)

        # Return result of last chunk (contains final message_id)
        return results[-1]

    def _send_chunk(
        self,
        text: str,
        parse_mode: Optional[str],
        chunk_num: int = 1
    ) -> NotificationResult:
        """Send a single message chunk with retry logic."""
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        backoff = self._initial_backoff
        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                response = self._session.post(
                    url,
                    json=payload,
                    timeout=self._timeout
                )

                # Success
                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get("result", {}).get("message_id")
                    if message_id:
                        logger.info(
                            f"Telegram message sent (chunk {chunk_num}, id={message_id})"
                        )
                    return NotificationResult(
                        success=True,
                        message_ref=str(message_id) if message_id else None
                    )

                # Rate limit (429) - retry with backoff
                if response.status_code == 429:
                    retry_after = self._extract_retry_after(response)
                    wait_time = max(retry_after or backoff, backoff)

                    if attempt < self._max_retries:
                        logger.warning(
                            f"Telegram rate limit (429), retrying in {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{self._max_retries})"
                        )
                        time.sleep(wait_time)
                        backoff = min(backoff * self._backoff_multiplier, self._max_backoff)
                        continue

                    last_error = f"Rate limit exceeded after {self._max_retries} retries"
                    logger.error(last_error)
                    return NotificationResult(success=False, error=last_error)

                # Other errors - fail immediately
                detail = self._extract_error_detail(response)
                last_error = f"Telegram API error ({response.status_code}): {detail}"
                logger.error(self._mask_token(last_error))
                return NotificationResult(success=False, error=last_error)

            except requests.exceptions.Timeout:
                last_error = f"Request timeout after {self._timeout}s"
                logger.error(last_error)
                return NotificationResult(success=False, error=last_error)

            except requests.exceptions.RequestException as e:
                last_error = f"Network error: {e}"
                logger.error(self._mask_token(last_error))
                return NotificationResult(success=False, error=last_error)

        # Should not reach here, but fallback
        return NotificationResult(
            success=False,
            error=last_error or "Unknown error"
        )

    def _split_message(self, text: str, max_length: int = 4096) -> list[str]:
        """Split long messages into chunks respecting Telegram's limit.
        
        Splits at newlines when possible to avoid breaking sentences.
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current = []
        current_len = 0

        for line in text.split('\n'):
            line_len = len(line) + 1  # +1 for newline

            if current_len + line_len > max_length:
                # Flush current chunk
                if current:
                    chunks.append('\n'.join(current))
                    current = []
                    current_len = 0

                # Handle line longer than max_length (rare)
                if line_len > max_length:
                    for i in range(0, len(line), max_length):
                        chunks.append(line[i:i + max_length])
                else:
                    current.append(line)
                    current_len = line_len
            else:
                current.append(line)
                current_len += line_len

        if current:
            chunks.append('\n'.join(current))

        return chunks

    def _extract_retry_after(self, response: requests.Response) -> Optional[float]:
        """Extract Retry-After from 429 response (header or JSON body)."""
        # Try header first
        if retry_after := response.headers.get("Retry-After"):
            try:
                return float(retry_after)
            except ValueError:
                pass

        # Try JSON body
        try:
            data = response.json()
            if parameters := data.get("parameters", {}):
                if retry_after := parameters.get("retry_after"):
                    return float(retry_after)
        except Exception:
            pass

        return None

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract human-readable error from Telegram API response."""
        try:
            data = response.json()
            return data.get("description", "no detail")
        except Exception:
            return response.text[:200] if response.text else "no detail"

    def _mask_token(self, text: str) -> str:
        """Redact bot token from log messages."""
        if not self._token:
            return text
        return text.replace(self._token, "***")
