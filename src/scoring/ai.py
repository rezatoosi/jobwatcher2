# src/scoring/ai.py
"""AI-based scoring for Reddit posts."""

import json
import logging
import re
import time
from typing import Optional

from src.ai.manager import AIProviderManager
from src.scoring.base import BaseScorer, ScoredPost, ScorablePost

logger = logging.getLogger(__name__)


class AIScoringError(Exception):
    """Raised when the AI layer fails irrecoverably and the batch must stop."""
    pass


# Matches the first top-level {...} block in a string (non-greedy, DOTALL).
_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


class AIScorer(BaseScorer):
    """Score posts using an AI provider.

    The AI returns a JSON object. This scorer only interprets two fields:
    `is_relevant` (final keep/drop decision) and `score` (ranking value).
    All other fields are domain-specific and are preserved verbatim in
    `ScoredPost.ai_metadata` without the scorer needing to understand them.

    The system prompt is fully supplied by the caller (from config), so the
    scorer stays domain-agnostic and reusable beyond job/lead matching.
    """

    def __init__(
        self,
        manager: AIProviderManager,
        system_prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
        max_retries: int = 3,
        retry_delay: float = 60.0,
    ) -> None:
        """Initialize the AI scorer.

        Args:
            manager: Configured AIProviderManager used to send requests.
            system_prompt: Full system prompt (domain-specific), from config.
            max_tokens: Token budget for the response.
            temperature: Sampling temperature (0.0 = deterministic).
            max_retries: Attempts on provider/request failure before raising.
            retry_delay: Seconds to wait between provider-failure retries.
        """
        # min_score is intentionally unused for filtering here; the final
        # keep/drop decision is `is_relevant`, handled by the hybrid layer.
        super().__init__(min_score=0.0)
        self.manager = manager
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def score_post(self, post: ScorablePost) -> ScoredPost:
        """Score a single post via the AI provider.

        Returns a ScoredPost. On parse/validation or provider failure, returns
        a post with error flagged in ai_metadata (post stays pending for retry).
        """
        user_prompt = self._build_user_prompt(post)
        response = self._send_with_retry(user_prompt, post)

        # If _send_with_retry returned a ScoredPost (provider failure), return it
        if isinstance(response, ScoredPost):
            return response

        parsed = self._parse_response(response.content)
        if parsed is None:
            logger.warning(
                "Dropping post %s: could not parse AI response as JSON",
                post.post_id,
            )
            return ScoredPost(
                post=post,
                score=0.0,
                matched_keywords=[],
                ai_metadata={
                    "is_relevant": 0,
                    "error": "invalid_json",
                    "raw": response.content,
                    "provider": response.provider,
                    "model": response.model,
                },
            )

        is_relevant = int(parsed.get("is_relevant", 0))
        score = float(parsed.get("score", 0.0)) if is_relevant == 1 else 0.0

        # Keep every AI field as-is; only normalize the two we depend on.
        metadata = dict(parsed)
        metadata["is_relevant"] = is_relevant
        metadata["provider"] = response.provider
        metadata["model"] = response.model
        metadata["tokens_used"] = response.tokens_used

        return ScoredPost(
            post=post,
            score=score,
            matched_keywords=[],
            ai_metadata=metadata,
        )

    def fake_score_post(self, post: ScorablePost) -> ScoredPost:
        """Simulate AIScorer.score_post for testing without calling real AI API.
        
        Args:
            post: The post to score
        
        Returns:
            ScoredPost with fake AI metadata
        """
        import random
        
        is_relevant = random.choice([0, 1])
        score = round(random.uniform(0.5, 0.95), 2) if is_relevant == 1 else 0.0
        
        return ScoredPost(
            post=post,
            score=score,
            matched_keywords=[],
            ai_metadata={
                "is_relevant": is_relevant,
                "score": score,
                "reason": "Test simulation - randomly generated",
                "provider": "fake_provider",
                "model": "fake_model",
                "tokens_used": 0,
            }
        )

    def _send_with_retry(self, user_prompt: str, post: ScorablePost):
        """Send a request, retrying on provider/request failure.

        The manager already handles provider fallback internally and reports
        total failure via `AIResponse.success=False` (it does not raise), so
        we retry based on that flag.

        On total failure after all retries, returns a ScoredPost flagged with
        provider_failure error instead of raising, allowing the batch to continue.

        Returns:
            A successful AIResponse or a fallback ScoredPost on total failure.
        """
        last_error = "unknown error"
        for attempt in range(1, self.max_retries + 1):
            response = self.manager.send_request(
                user_prompt=user_prompt,
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            if response.success:
                return response

            last_error = response.error or "unknown error"
            logger.warning(
                "AI request failed for post %s (attempt %d/%d): %s",
                post.post_id,
                attempt,
                self.max_retries,
                last_error,
            )
            if attempt < self.max_retries:
                time.sleep(self.retry_delay)

        # if failed after 3 attempt, return a ScoredPost with error metadata
        logger.error(
            "AI provider failed for post %s after %d attempts: %s",
            post.post_id,
            self.max_retries,
            last_error,
        )
        return ScoredPost(
            post=post,
            score=0.0,
            matched_keywords=[],
            ai_metadata={
                "is_relevant": 0,
                "error": "provider_failure",
                "error_detail": last_error,
            },
        )

    def _build_user_prompt(self, post: ScorablePost) -> str:
        """Build the user prompt from a post's title and body."""
        body = post.body or ""
        return f"Title: {post.title}\n\nBody: {body}"

    def _parse_response(self, content: str) -> Optional[dict]:
        """Parse the AI response into a dict.

        Tries the whole content as JSON first, then falls back to extracting
        the first {...} block. Returns None on failure.
        """
        if not content:
            return None

        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        match = _JSON_BLOCK_RE.search(content)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

        return None