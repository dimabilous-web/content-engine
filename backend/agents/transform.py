"""
Transform node — generate 2 idea variations per selected post using Claude.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from services.claude_service import generate_ideas

logger = logging.getLogger(__name__)


def _idea_id() -> str:
    return str(uuid.uuid4())[:8]


async def transform_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: for each of the top 25 posts, generate 2 idea cards.
    Populates state["ideas"] with flat list of idea dicts ready for Airtable.
    """
    run_id = state["run_id"]
    posts: list[dict] = state.get("selected_posts", [])
    batch_id = state.get("run_id")

    logger.info(f"[{run_id}] transform_node: generating ideas for {len(posts)} posts")

    now_iso = datetime.now(timezone.utc).isoformat()

    async def _process_one(post: dict) -> list[dict]:
        variations = await generate_ideas(
            post_text=post.get("post_text", ""),
            author_name=post.get("author_name", "Unknown"),
            reactions=post.get("reactions", 0),
            topic_cluster=post.get("topic_cluster", "sales-outbound"),
        )
        ideas = []
        for v in variations:
            idea = {
                "idea_id":          _idea_id(),
                "hook":             v.get("hook", ""),
                "outline":          v.get("outline", ""),
                "post_type":        v.get("post_type", "CTA Post"),
                "topic_cluster":    v.get("topic_cluster", post.get("topic_cluster", "sales-outbound")),
                "effort":           v.get("effort", "Medium"),
                "cta_word":         v.get("cta_word", "SYSTEM"),
                "source_post_id":   post.get("post_id", ""),
                "source_reactions": post.get("reactions", 0),
                "source_author":    post.get("author_name", ""),
                "status":           "New",
                "batch_id":         batch_id,
                "created_at":       now_iso,
            }
            ideas.append(idea)
        return ideas

    # Process all posts concurrently (Claude API handles parallelism well)
    # Batch of 10 at a time to respect rate limits, with small pause between batches
    all_ideas: list[dict] = []
    batch_size = 10
    for i in range(0, len(posts), batch_size):
        batch = posts[i : i + batch_size]
        results = await asyncio.gather(*[_process_one(p) for p in batch])
        for idea_list in results:
            all_ideas.extend(idea_list)
        if i + batch_size < len(posts):
            await asyncio.sleep(1)

    logger.info(f"[{run_id}] transform_node: generated {len(all_ideas)} ideas")
    return {
        **state,
        "ideas": all_ideas,
        "ideas_generated": len(all_ideas),
    }
