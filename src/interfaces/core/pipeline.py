# src/interfaces/core/pipeline.py
"""Core fetch-and-score pipeline, independent of any interface.

The same flow can be driven by the CLI, a scheduled job, or an HTTP
endpoint without duplication. Interfaces are responsible for I/O and
presentation; this module only orchestrates fetch -> filter -> dedupe
-> keyword gate -> AI relevance, and reports structured results.
"""

import logging
from dataclasses import dataclass, field, replace
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
class RejectedPost:
    """Wrapper for a rejected post with its rejection reason."""
    scored_post: ScoredPost
    reason: str


@dataclass
class FetchReport:
    """Structured result of a single pipeline run.

    `accepted` holds the final kept posts (is_relevant=1, or keyword-passed
    when AI is disabled). `rejected` holds everything dropped after the
    keyword stage (keyword-failed plus AI-irrelevant), preserved for audit.
    """

    total_fetched: int = 0
    filtered_out: int = 0
    duplicates: int = 0
    keyword_passed: int = 0
    ai_enabled: bool = False
    accepted: list[ScoredPost] = field(default_factory=list)
    rejected: list[RejectedPost] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


class FetchPipeline:
    """Build the processing stages from config and run them on demand.

    Wiring is done once in the constructor; `run` is side-effect free
    except for network calls, and `persist` is the only DB-writing step.
    The AI stage is optional: if the AI layer is disabled or has no usable
    provider, the keyword gate becomes the final accept decision.
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
        self.post_filter = PostFilter(filters=config.filters)
        self.keyword_scorer = KeywordScorer(
            keywords=config.keywords,
            min_score=0.0,
        )
        self.keyword_threshold = config.scoring.keyword_threshold

        # The manager self-reports usability via `.enabled`; only build an
        # AI scorer when there is at least one configured, enabled provider.
        self.ai_manager = AIProviderManager(config.ai_providers, config.network)
        self.ai_scorer: Optional[AIScorer] = None
        if self.ai_manager.enabled:
            self.ai_scorer = AIScorer(
                manager=self.ai_manager,
                system_prompt=self._build_system_prompt(config),
            )

    @staticmethod
    def _build_system_prompt(config: AppConfig) -> str:
        """Fill the configured prompt template.

        The prompt is supplied entirely by config to keep the AI layer
        domain-agnostic. The only substitution is the optional {skills}
        placeholder, filled from the keyword list. If the template uses
        placeholders we don't provide, it is passed through unchanged
        rather than failing the run.
        """
        template = config.scoring.ai_system_prompt
        if not template:
            return ""
        skills = ", ".join(config.keywords.keys())
        try:
            return template.format(skills=skills)
        except (KeyError, IndexError, ValueError):
            logger.warning(
                "ai_system_prompt has unsupported placeholders; "
                "using it verbatim"
            )
            return template

    def run(self, progress: Optional[ProgressCallback] = None) -> FetchReport:
        """Execute the full pipeline and return a structured report.

        Raises:
            AIScoringError: AI provider failed repeatedly; the batch is
                aborted by the AI scorer and the error propagates here.
        """
        report = FetchReport(ai_enabled=self.ai_scorer is not None)

        posts = self.fetcher.fetch_posts()
        report.total_fetched = len(posts)

        filtered = self.post_filter.filter_posts(posts)
        report.filtered_out = report.total_fetched - len(filtered)
        if not filtered:
            return report

        unique = [p for p in filtered if not self.db.post_exists(p.post_id)]
        report.duplicates = len(filtered) - len(unique)
        if not unique:
            return report

        # Stage 1: keyword gate (cheap, local).
        keyword_scored = [self.keyword_scorer.score_post(p) for p in unique]
        passed = [
            sp for sp in keyword_scored if sp.score >= self.keyword_threshold
        ]
        report.rejected.extend(
            RejectedPost(sp, f"keyword_score_below_threshold (score: {sp.score:.2f}, threshold: {self.keyword_threshold})")
            for sp in keyword_scored if sp.score < self.keyword_threshold
        )
        report.keyword_passed = len(passed)
        if not passed:
            return report

        # Keyword-only mode: the gate is the final accept decision.
        if self.ai_scorer is None:
            report.accepted = sorted(
                passed, key=lambda sp: sp.score, reverse=True
            )
            return report

        # Stage 2: AI relevance decision (expensive, remote).
        total = len(passed)
        for idx, kw in enumerate(passed, start=1):
            scored = self.ai_scorer.fake_score_post(kw.post)
            # ScoredPost is frozen; rebuild it with the stage-1 keyword hits.
            scored = replace(scored, matched_keywords=kw.matched_keywords)
            if progress is not None:
                progress(idx, total, scored)

            if scored.ai_metadata and scored.ai_metadata.get("is_relevant") == 1:
                report.accepted.append(scored)
            else:
                reason = "ai_marked_irrelevant"
                if scored.ai_metadata:
                    ai_reason = scored.ai_metadata.get("reason", "")
                    if ai_reason:
                        reason = f"ai_marked_irrelevant: {ai_reason}"
                report.rejected.append(RejectedPost(scored, reason))

        report.accepted.sort(key=lambda sp: sp.score, reverse=True)
        return report

    def persist(self, report: FetchReport) -> None:
        """Write accepted and rejected posts to the database."""
        for sp in report.accepted:
            self.db.save_post(
                post_id=sp.post.post_id,
                subreddit=sp.post.subreddit,
                title=sp.post.title,
                body=sp.post.body,
                url=sp.post.url,
                score=sp.score,
                matched_keywords=sp.matched_keywords,
                ai_metadata=sp.ai_metadata,
            )
        for rp in report.rejected:
            sp = rp.scored_post
            self.db.save_rejected_post(
                post_id=sp.post.post_id,
                subreddit=sp.post.subreddit,
                title=sp.post.title,
                body=sp.post.body,
                url=sp.post.url,
                score=sp.score,
                matched_keywords=sp.matched_keywords,
                ai_metadata=sp.ai_metadata,
                rejection_reason=rp.reason,
            )
