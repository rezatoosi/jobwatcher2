"""Hybrid scorer combining keyword and AI-based scoring."""

import logging
from dataclasses import replace
from typing import List

from src.fetcher.reddit import RedditPost
from src.scoring.ai import AIScorer
from src.scoring.base import BaseScorer, ScoredPost
from src.scoring.keyword import KeywordScorer

logger = logging.getLogger(__name__)


class HybridScorer(BaseScorer):
    """Two-stage scorer: keyword pre-filter, then AI enrichment.

    Posts that don't meet the keyword threshold are dropped immediately.
    Posts that pass are sent to the AI scorer for final relevance decision.
    Only posts with `is_relevant=1` from AI are kept in the output.

    This scorer is reusable across domains: filtering logic is fixed, but
    the keyword list and AI prompt come from config.
    """

    def __init__(
        self,
        keyword_scorer: KeywordScorer,
        ai_scorer: AIScorer,
        keyword_threshold: float = 1.0,
    ) -> None:
        """Initialize the hybrid scorer.

        Args:
            keyword_scorer: Configured keyword scorer.
            ai_scorer: Configured AI scorer.
            keyword_threshold: Minimum keyword score to pass to AI stage.
        """
        super().__init__(min_score=0.0)
        self.keyword_scorer = keyword_scorer
        self.ai_scorer = ai_scorer
        self.keyword_threshold = keyword_threshold

    def score_posts(self, posts: List[RedditPost]) -> List[ScoredPost]:
        """Score a batch of posts through the two-stage pipeline.

        Stage 1: keyword filter (cheap, local).
        Stage 2: AI scoring (expensive, remote).
        Final filter: only keep posts with `is_relevant=1`.

        Raises:
            AIScoringError: AI provider failed repeatedly; batch is aborted.
        """
        if not posts:
            return []

        logger.info("Stage 1: keyword pre-filter on %d posts", len(posts))
        keyword_results = [self.keyword_scorer.score_post(p) for p in posts]
        passed = [
            r for r in keyword_results if r.score >= self.keyword_threshold
        ]
        dropped_count = len(posts) - len(passed)
        logger.info(
            "Keyword filter: %d passed, %d dropped (threshold=%.1f)",
            len(passed),
            dropped_count,
            self.keyword_threshold,
        )

        if not passed:
            return []

        logger.info("Stage 2: AI scoring on %d posts", len(passed))
        ai_results = []
        for idx, kw_result in enumerate(passed, start=1):
            logger.debug(
                "AI scoring post %d/%d: %s",
                idx,
                len(passed),
                kw_result.post.post_id,
            )
            ai_result = self.ai_scorer.score_post(kw_result.post)
            # ScoredPost is frozen; rebuild it with the stage-1 keyword hits.
            ai_result = replace(
                ai_result, matched_keywords=kw_result.matched_keywords
            )
            ai_results.append(ai_result)

        relevant = [
            r for r in ai_results
            if r.ai_metadata and r.ai_metadata.get("is_relevant") == 1
        ]
        dropped_ai = len(ai_results) - len(relevant)
        logger.info(
            "AI filter: %d relevant, %d irrelevant",
            len(relevant),
            dropped_ai,
        )

        return relevant

    def score_post(self, post: RedditPost) -> ScoredPost:
        """Score a single post (used by base class batch method).

        This is a simple wrapper around the two-stage flow for consistency
        with the BaseScorer interface. Prefer `score_posts` for batches.
        """
        kw_result = self.keyword_scorer.score_post(post)
        if kw_result.score < self.keyword_threshold:
            # Return a zero-score result flagged as irrelevant
            return ScoredPost(
                post=post,
                score=0.0,
                matched_keywords=[],
                ai_metadata={"is_relevant": 0, "reason": "keyword_threshold"},
            )

        ai_result = self.ai_scorer.score_post(post)
        return replace(ai_result, matched_keywords=kw_result.matched_keywords)
