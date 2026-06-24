# src/scoring/base.py
"""Base classes for scoring posts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ScorablePost(Protocol):
    """Structural contract for any post that scorers can consume.

    Both `RedditPost` (fetcher layer) and `PostRecord` (storage layer)
    satisfy this protocol, so scoring depends on neither concrete type.
    """

    post_id: str
    subreddit: str
    title: str
    body: Optional[str]
    url: str


@dataclass(frozen=True)
class ScoredPost:
    """Represents a scored post with metadata."""

    post: ScorablePost
    score: float
    matched_keywords: list[str]
    ai_metadata: Optional[dict] = None


class BaseScorer(ABC):
    """Abstract base class for all post scorers."""

    def __init__(self, min_score: float = 0.0):
        """
        Initialize scorer.

        Args:
            min_score: Minimum score threshold for filtering
        """
        self.min_score = min_score

    @abstractmethod
    def score_post(self, post: ScorablePost) -> ScoredPost:
        """
        Score a single post.

        Args:
            post: Post to score

        Returns:
            Scored post with metadata
        """
        pass

    def score_posts(self, posts: list[ScorablePost]) -> list[ScoredPost]:
        """
        Score multiple posts, filter by min_score, and sort descending.

        Args:
            posts: List of posts to score

        Returns:
            Filtered and sorted list of scored posts
        """
        scored = [self.score_post(post) for post in posts]
        filtered = [sp for sp in scored if sp.score >= self.min_score]
        return sorted(filtered, key=lambda sp: sp.score, reverse=True)
