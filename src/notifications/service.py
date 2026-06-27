# src/notifications/service.py
import logging
from datetime import datetime
from typing import List

from src.notifiers.base import Notifier
from src.scoring.base import ScoredPost

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4000


def format_batch(posts: List[ScoredPost]) -> List[str]:
    messages = []
    current_message = ""
    post_number = 1

    for sp in posts:
        fetched_at = sp.post.fetched_at.strftime("%Y-%m-%d %H:%M") if sp.post.fetched_at else "N/A"
        scored_at = sp.post.scored_at.strftime("%Y-%m-%d %H:%M") if sp.post.scored_at else "N/A"

        lines = [
            f"{post_number}. [{sp.score:.1f}] {sp.post.title}",
            f"   r/{sp.post.subreddit}",
            f"   Post ID: {sp.post.post_id}",
            f"   Score: {sp.score:.1f} | Keywords: {', '.join(sp.matched_keywords)}",
            f"   URL: {sp.post.url}",
            f"   Fetched at: {fetched_at}"
        ]

        if sp.post.body:
            preview = sp.post.body.replace("\n", " ")[:150]
            if len(sp.post.body) > 150:
                preview += "..."
            lines.append(f"   Body: {preview}")

        if sp.ai_metadata:
            ai_reason = sp.ai_metadata.get("reason", "")
            if ai_reason:
                lines.append(f"   Reason: {ai_reason}")

        post_text = "\n".join(lines) + "\n\n"

        if len(current_message) + len(post_text) > MAX_MESSAGE_LENGTH:
            if current_message:
                messages.append(current_message.strip())
            current_message = post_text
        else:
            current_message += post_text

        post_number += 1

    if current_message:
        messages.append(current_message.strip())

    return messages


def notify_accepted_posts(notifiers: List[Notifier], posts: List[ScoredPost]) -> None:
    if not posts:
        logger.info("No posts to notify")
        return

    messages = format_batch(posts)
    logger.info(f"Formatted {len(posts)} posts into {len(messages)} message(s)")

    for notifier in notifiers:
        for idx, msg in enumerate(messages, 1):
            result = notifier.send(text=msg)
            if result.success:
                logger.info(
                    f"Sent message {idx}/{len(messages)} via {notifier.__class__.__name__} | ref: {result.message_ref}"
                )
            else:
                logger.error(
                    f"Failed to send message {idx}/{len(messages)} via {notifier.__class__.__name__}: {result.error}"
                )