# src/interfaces/core/pipeline.py
"""Core fetch-and-score pipeline, independent of any interface.

Fetch and scoring are now separate phases:
- FetchPipeline: fetches posts, checks duplicates, saves all new posts with status='pending'.
- ScoringPipeline: loads pending posts, applies filter + keyword + AI scoring,
  updates status to 'accepted' or 'rejected' with rejection_reason.

Interfaces are responsible for I/O and presentation; these modules only
orchestrate the domain logic and report structured results.
"""

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Callable, Optional

from src.ai.manager import AIProviderManager
from src.config.loader import AppConfig
from src.fetcher.reddit import RedditRSSFetcher
from src.scoring.filter import PostFilter
from src.scoring.ai import AIScorer
from src.scoring.base import ScoredPost
from src.scoring.keyword import KeywordScorer
from src.storage.database import Database

logger = logging.getLogger(__name__)

# Called once per AI-scored post: (index, total, scored_post).
ProgressCallback = Callable[[int, int, ScoredPost], None]


@dataclass
class FetchReport:
    """Structured result of a fetch run.
    
    Only reports what was fetched and saved; scoring is a separate phase.
    """
    total_fetched: int = 0
    duplicates: int = 0
    saved_pending: int = 0


@dataclass
class RejectedPost:
    """Wrapper for a rejected post with its rejection reason."""
    scored_post: ScoredPost
    reason: str


@dataclass
class ScoringReport:
    """Structured result of a scoring run.
    
    `accepted` holds posts marked relevant, `rejected` holds posts that
    failed filter, keyword threshold, or AI relevance check.
    """
    total_pending: int = 0
    filtered_out: int = 0
    keyword_passed: int = 0
    ai_enabled: bool = False
    accepted: list[ScoredPost] = field(default_factory=list)
    rejected: list[RejectedPost] = field(default_factory=list)
    still_pending: int = 0

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


class FetchPipeline:
    """Fetch posts from Reddit, check duplicates, save as pending.
    
    This phase is separate from scoring to avoid re-fetching when scoring
    fails or needs to be re-run with different parameters.
    """

    def __init__(self, config: AppConfig, db: Database) -> None:
        self.config = config
        self.db = db

        proxy_url = config.network.proxy or None
        self.fetcher = RedditRSSFetcher(
            subreddits=config.subreddits,
            limit=config.fetch_limit,
            request_delay=config.request_delay,
            proxy_http=proxy_url,
        )

    def run(self) -> FetchReport:
        """Fetch posts, dedupe, and save as pending.
        
        Returns:
            FetchReport with counts of fetched, duplicate, and saved posts.
        """
        report = FetchReport()

        # Fetch from Reddit
        posts = self.fetcher.fetch_posts()
        report.total_fetched = len(posts)
        logger.info(f"Fetched {report.total_fetched} posts")

        if not posts:
            return report

        # Check duplicates
        unique = [p for p in posts if not self.db.post_exists(p.post_id)]
        report.duplicates = len(posts) - len(unique)
        logger.info(f"Found {report.duplicates} duplicates")
        if not unique:
            return report

        # Save all unique posts with status='pending'
        fetched_at = datetime.utcnow()
        for post in unique:
            self.db.save_fetched_post(
                post_id=post.post_id,
                subreddit=post.subreddit,
                title=post.title,
                body=post.body,
                url=post.url,
                fetched_at=fetched_at,
            )
        report.saved_pending = len(unique)
        logger.info(f"Saved {report.saved_pending} posts as pending")

        return report


class ScoringPipeline:
    """Score pending posts with filter + keyword + AI, update status accordingly.

    Loads posts with status='pending', applies filter, keyword scoring, then
    optional AI scoring. Updates each post to 'accepted' or 'rejected'
    with appropriate metadata.
    """

    def __init__(self, config: AppConfig, db: Database) -> None:
        self.config = config
        self.db = db

        self.post_filter = PostFilter(filters=config.filters)
        self.keyword_scorer = KeywordScorer(
            keywords=config.keywords,
            min_score=0.0,
        )
        self.keyword_threshold = config.scoring.keyword_threshold

        # Build AI scorer if any provider is available
        self.ai_manager = AIProviderManager(config.ai_providers, config.network)
        self.ai_scorer: Optional[AIScorer] = None
        if self.ai_manager.enabled:
            self.ai_scorer = AIScorer(
                manager=self.ai_manager,
                system_prompt=self._build_system_prompt(config),
                max_tokens=config.ai_providers.max_tokens,
                max_retries=config.rate_limiting.max_retries,
                initial_backoff=config.rate_limiting.initial_backoff,
                max_backoff=config.rate_limiting.max_backoff,
                backoff_multiplier=config.rate_limiting.backoff_multiplier,
            )

    @staticmethod
    def _build_system_prompt(config: AppConfig) -> str:
        """Fill the configured prompt template with keywords."""
        template = config.scoring.ai_system_prompt
        if not template:
            return ""
        skills = ", ".join(config.keywords.keys())
        try:
            return template.format(skills=skills)
        except (KeyError, IndexError, ValueError):
            logger.warning(
                "ai_system_prompt has unsupported placeholders; using verbatim"
            )
            return template

    def run(self, progress: Optional[ProgressCallback] = None) -> ScoringReport:
        """Score all pending posts and update their status.
        
        Args:
            progress: Optional callback for AI scoring progress.
            
        Returns:
            ScoringReport with accepted and rejected counts and details.
        """
        report = ScoringReport(ai_enabled=self.ai_scorer is not None)

        # Load pending posts
        pending = self.db.get_pending_posts()
        report.total_pending = len(pending)
        logger.info(f"Loaded {report.total_pending} pending posts")
        if not pending:
            return report

        scored_at = datetime.utcnow()

        # Stage 1: filter (length, banned words, etc.)
        filtered = self.post_filter.filter_posts(pending)
        failed_filter = [p for p in pending if p not in filtered]
        report.filtered_out = len(failed_filter)
        logger.info(f"Filter: {len(filtered)} passed, {report.filtered_out} failed")

        # Reject posts that failed filter
        for post in failed_filter:
            reason = "failed_basic_filter"
            self.db.update_post_rejected(
                post_id=post.post_id,
                rejection_reason=reason,
                score=0.0,
                matched_keywords=[],
                scored_at=scored_at,
            )
            # Wrap as ScoredPost for consistency
            scored = ScoredPost(post=post, score=0.0, matched_keywords=[])
            report.rejected.append(RejectedPost(scored, reason))

        if not filtered:
            return report

        # Stage 2: keyword scoring (cheap, local)
        keyword_scored = [
            self.keyword_scorer.score_post(p) for p in filtered
        ]
        passed = [
            sp for sp in keyword_scored if sp.score >= self.keyword_threshold
        ]
        failed_keyword = [
            sp for sp in keyword_scored if sp.score < self.keyword_threshold
        ]
        
        report.keyword_passed = len(passed)
        logger.info(
            f"Keyword scoring: {len(passed)} passed, {len(failed_keyword)} failed"
        )

        # Reject posts that failed keyword threshold
        for sp in failed_keyword:
            reason = "keyword_score_low"
            self.db.update_post_rejected(
                post_id=sp.post.post_id,
                rejection_reason=reason,
                score=sp.score,
                matched_keywords=sp.matched_keywords,
                scored_at=scored_at,
            )
            report.rejected.append(RejectedPost(sp, reason))

        if not passed:
            return report

        # Keyword-only mode: accept all that passed keyword threshold
        if self.ai_scorer is None:
            for sp in passed:
                self.db.update_post_accepted(
                    post_id=sp.post.post_id,
                    score=sp.score,
                    matched_keywords=sp.matched_keywords,
                    scored_at=scored_at,
                )
                report.accepted.append(sp)
            logger.info(f"Keyword-only mode: accepted {len(passed)} posts")
            return report

        # Stage 3: AI relevance scoring (expensive, remote)
        total = len(passed)
        logger.info(f"Starting AI scoring for {total} posts")
        for idx, kw in enumerate(passed, start=1):
            scored = self.ai_scorer.score_post(kw.post)
            # Preserve keyword metadata from stage 2
            scored = replace(scored, matched_keywords=kw.matched_keywords)
            
            if progress is not None:
                progress(idx, total, scored)

            # Check for AI errors (provider failure or parse error)
            has_error = (
                scored.ai_metadata is not None
                and scored.ai_metadata.get("error") in ["provider_failure", "invalid_json"]
            )

            if has_error:
                # Keep post as pending for retry, don't mark rejected
                error_type = scored.ai_metadata.get("error")
                logger.warning(
                    f"Post {scored.post.post_id} stayed pending due to AI {error_type}"
                )
                report.still_pending += 1
                continue

            is_relevant = (
                scored.ai_metadata 
                and scored.ai_metadata.get("is_relevant") == 1
            )

            if is_relevant:
                self.db.update_post_accepted(
                    post_id=scored.post.post_id,
                    score=scored.score,
                    matched_keywords=scored.matched_keywords,
                    ai_metadata=scored.ai_metadata,
                    scored_at=scored_at,
                )
                report.accepted.append(scored)
            else:
                reason = "ai_rejected"
                if scored.ai_metadata:
                    ai_reason = scored.ai_metadata.get("reason", "")
                    if ai_reason:
                        reason = f"ai_rejected: {ai_reason}"
                self.db.update_post_rejected(
                    post_id=scored.post.post_id,
                    rejection_reason=reason,
                    score=scored.score,
                    matched_keywords=scored.matched_keywords,
                    ai_metadata=scored.ai_metadata,
                    scored_at=scored_at,
                )
                report.rejected.append(RejectedPost(scored, reason))

        logger.info(
            f"AI scoring complete: {len(report.accepted)} accepted, "
            f"{len(report.rejected)} rejected, "
            f"{report.still_pending} still pending"
        )
        return report
