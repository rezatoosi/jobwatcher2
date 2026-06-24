# src/scoring/keyword.py
"""Keyword-based scoring for Reddit posts."""

from src.scoring.base import BaseScorer, ScoredPost, ScorablePost


class KeywordScorer(BaseScorer):
    """Score posts based on keyword matches with configurable weights."""
    
    def __init__(self, keywords: dict[str, int], min_score: float = 0.0):
        """
        Initialize keyword scorer.
        
        Args:
            keywords: Dictionary mapping keywords to their weight scores
            min_score: Minimum score threshold for filtering
        """
        super().__init__(min_score)
        self.keywords = {k.lower(): v for k, v in keywords.items()}
    
    def score_post(self, post: ScorablePost) -> ScoredPost:
        """
        Score a post by matching keywords in title and body.
        
        Args:
            post: Post to score
            
        Returns:
            Scored post with matched keywords
        """
        text = f"{post.title} {post.body or ''}".lower()
        
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
            ai_metadata=None
        )
