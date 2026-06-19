# src/cli/commands.py
"""CLI commands for Reddit post monitoring."""

from pathlib import Path
from typing import Optional

from src.config import load_config
from src.fetcher.reddit import RedditRSSFetcher
from src.filtering.post_filter import PostFilter
from src.scoring.scorer import KeywordScorer
from src.storage.database import Database


def cmd_fetch(config_path: Path = Path("config.yaml")):
    """Fetch new posts from Reddit and process them."""
    config = load_config(config_path)
    
    print(f"Configuration loaded:")
    print(f"  Subreddits: {', '.join(config.subreddits)}")
    print(f"  Keywords: {len(config.keywords)} keywords")
    print(f"  Min score: {config.min_score}")
    print(f"  Fetch limit: {config.fetch_limit}")
    print()
    
    db = Database("posts.db")
    
    proxy_url = None
    # if config.network.proxy:
    #     proxy_url = config.network.proxy
    
    fetcher = RedditRSSFetcher(
        subreddits=config.subreddits,
        limit=config.fetch_limit,
        request_delay=config.request_delay,
        proxy_http=proxy_url
    )

    post_filter = PostFilter(filters=config.filters)
    
    scorer = KeywordScorer(keywords=config.keywords, min_score=config.min_score)
    
    print("Fetching posts from Reddit...")
    total_fetched = 0
    total_filtered_out = 0
    total_duplicates = 0
    total_scored = 0
    total_accepted = 0
    total_rejected = 0

    try: 
        # Stage 1: Fetch
        posts = fetcher.fetch_posts()
        total_fetched = len(posts)
        print(f"  Fetched {len(posts)} posts")

        # Stage 2: Pre-filter
        filtered_posts = post_filter.filter_posts(posts)
        total_filtered_out = total_fetched - len(filtered_posts)

        if total_filtered_out  > 0:
            print(f"  Filtered out {total_filtered_out} posts by rules")
        
        if not filtered_posts:
            print(f"  No posts passed filters")
            return
        
        # Stage 3: Remove duplicates
        unique_posts = [p for p in filtered_posts if not db.post_exists(p.post_id)]
        total_duplicates = len(filtered_posts) - len(unique_posts)
        
        if total_duplicates > 0:
            print(f"  Skipped {total_duplicates} duplicates")

        # Stage 4: Keyword scoring (score all posts once)
        all_scored = [scorer.score_post(p) for p in unique_posts]
        total_scored = len(all_scored)
        
        # Split by threshold
        accepted_posts = [sp for sp in all_scored if sp.score >= config.min_score]
        rejected_posts = [sp for sp in all_scored if sp.score < config.min_score]
        
        total_accepted = len(accepted_posts)
        total_rejected = len(rejected_posts)

    except Exception as e:
        print(f"  ✗ Error fetching: {e}")
    
    # Save accepted posts
    for scored_post in accepted_posts:
        post = scored_post.post
        print(f"  ✓ [{post.subreddit}] {post.title[:50]}...")
        print(f"    Score: {scored_post.score} | Keywords: {', '.join(scored_post.matched_keywords)}")
        
        db.save_post(
            post_id=post.post_id,
            subreddit=post.subreddit,
            title=post.title,
            body=post.body,
            url=post.url,
            score=scored_post.score,
            matched_keywords=scored_post.matched_keywords
        )
    
    # Save rejected posts
    for scored_post in rejected_posts:
        post = scored_post.post
        db.save_rejected_post(
            post_id=post.post_id,
            subreddit=post.subreddit,
            title=post.title,
            body=post.body,
            url=post.url,
            score=scored_post.score,
            matched_keywords=scored_post.matched_keywords
        )

    # Summary
    print()
    print("=== Fetch Summary ===\n")
    print(f"Total fetched:       {total_fetched}")
    print(f"Filtered out:        {total_filtered_out}")
    print(f"Duplicates skipped:  {total_duplicates}")
    print(f"Scored:              {total_scored}")
    print(f"Accepted:            {total_accepted}")
    print(f"Rejected (scored):   {total_rejected}")
    print("="*10)

    # TODO: add a file logger to log fetch info


def cmd_view(show_accepted: bool = True, show_rejected: bool = False, limit: Optional[int] = None):
    """View posts from database."""
    db = Database("posts.db")
    
    if show_accepted:
        print("=== Accepted Posts ===\n")
        posts = db.get_all_posts(limit=limit)
        
        if not posts:
            print("No accepted posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post['subreddit']}]: {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Created: {post['created_at']}")
                if post['body']:
                    body_preview = post['body'][:150].replace('\n', ' ')
                    print(f"   Body: {body_preview}{'...' if len(post['body']) > 150 else ''}")
                print()
    
    if show_rejected:
        print("=== Rejected Posts ===\n")
        posts = db.get_rejected_posts(limit=limit)
        
        if not posts:
            print("No rejected posts found.\n")
        else:
            for idx, post in enumerate(posts, 1):
                print(f"{idx}. [/r/{post['subreddit']}]: {post['title']}")
                print(f"   Score: {post['score']} | Keywords: {post['matched_keywords']}")
                print(f"   URL: {post['url']}")
                print(f"   Rejected: {post['rejected_at']}")
                print()


def cmd_stats():
    """Display database statistics."""
    db = Database("posts.db")
    
    accepted_count = db.count_posts()
    rejected_count = db.count_rejected_posts()
    
    print("=== Database Statistics ===\n")
    print(f"Accepted posts: {accepted_count}")
    print(f"Rejected posts: {rejected_count}")
    print(f"Total posts: {accepted_count + rejected_count}")
    print()
    
    # Top subreddits
    top_subreddits = db.get_top_subreddits(limit=5)
    if top_subreddits:
        print("Top subreddits (accepted):")
        for sr, count in top_subreddits:
            print(f"  r/{sr}: {count} posts")
