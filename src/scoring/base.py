# src/scoring/base.py
"""Base classes for scoring Reddit posts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from src.fetcher.reddit import RedditPost


@dataclass(frozen=True)
class ScoredPost:
    """Represents a scored Reddit post with metadata."""
    
    post: RedditPost
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
    def score_post(self, post: RedditPost) -> ScoredPost:
        """
        Score a single post.
        
        Args:
            post: Reddit post to score
            
        Returns:
            Scored post with metadata
        """
        pass
    
    def score_posts(self, posts: list[RedditPost]) -> list[ScoredPost]:
        """
        Score multiple posts, filter by min_score, and sort descending.
        
        Args:
            posts: List of Reddit posts to score
            
        Returns:
            Filtered and sorted list of scored posts
        """
        scored = [self.score_post(post) for post in posts]
        filtered = [sp for sp in scored if sp.score >= self.min_score]
        return sorted(filtered, key=lambda sp: sp.score, reverse=True)
