"""Score Reddit posts based on keyword relevance."""

from dataclasses import dataclass
from typing import Dict

from src.fetcher.reddit import RedditPost


@dataclass(frozen=True)
class ScoredPost:
    """Represents a scored Reddit post."""

    post: RedditPost
    score: float
    matched_keywords: list[str]


class KeywordScorer:
    """Scores posts based on keyword matches in title and body."""

    def __init__(self, keywords: Dict[str, float], min_score: float = 0.0):
        """Initialize scorer with keywords and their weights.

        Args:
            keywords: Dictionary mapping keywords to their weights.
                      e.g., {"python": 1.5, "freelance": 2.0}
            min_score: Minimum score threshold for accepting posts.
        """
        self.keywords = {k.lower(): v for k, v in keywords.items()}
        self.min_score = min_score

    def score_post(self, post: RedditPost) -> ScoredPost:
        """Calculate relevance score for a post.

        Scoring logic:
        - Case-insensitive substring matching
        - Each keyword match contributes its weight to the total score
        - Searches both title and body (body)

        Args:
            post: RedditPost to score.

        Returns:
            ScoredPost with calculated score and matched keywords.
        """
        text = f"{post.title} {post.body}".lower()
        matched = []
        total_score = 0.0

        for keyword, weight in self.keywords.items():
            if keyword in text:
                matched.append(keyword)
                total_score += weight

        return ScoredPost(
            post=post,
            score=total_score,
            matched_keywords=matched,
        )

    def score_posts(self, posts: list[RedditPost]) -> list[ScoredPost]:
        """Score multiple posts.

        Args:
            posts: List of RedditPost instances.

        Returns:
            List of ScoredPost instances, sorted by score (descending).
        """
        scored = [self.score_post(post) for post in posts]
        filtered = [sp for sp in scored if sp.score >= self.min_score]
        return sorted(filtered, key=lambda sp: sp.score, reverse=True)
