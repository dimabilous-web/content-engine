"""
Dedup + Scoring nodes.

IMPORTANT ordering:
  dedup_node  → runs BEFORE any Claude calls (saves LLM cost on already-seen posts)
  scoring_node → only called on new, unseen posts
  select_node  → top 25 go to transform (Claude idea generation)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from services.claude_service import score_post

logger = logging.getLogger(__name__)

FAST_LANE_BONUS = 20
FAST_LANE_HOURS = 48


def _make_post_id(post_url: str) -> str:
    return hashlib.sha256(post_url.encode()).hexdigest()[:16]


def _is_fast_lane(posted_at: str | None) -> bool:
    """Returns True if the post is <48 hours old."""
    if not posted_at:
        return False
    try:
        # Try ISO format first
        ts = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        return age < timedelta(hours=FAST_LANE_HOURS)
    except Exception:
        return False


async def dedup_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: remove posts already seen in Airtable + within-batch dupes.
    Requires state["seen_post_ids"] to be populated by the caller (pipeline.py).
    """
    run_id = state["run_id"]
    raw_posts: list[dict] = state.get("raw_posts", [])
    seen_ids: set[str] = state.get("seen_post_ids", set())

    logger.info(f"[{run_id}] dedup_node: {len(raw_posts)} posts in, {len(seen_ids)} already seen")

    deduped: list[dict] = []
    batch_seen: set[str] = set()

    for post in raw_posts:
        url = post.get("post_url", "")
        if not url:
            continue
        pid = _make_post_id(url)
        if pid in seen_ids or pid in batch_seen:
            continue
        batch_seen.add(pid)
        post["post_id"] = pid
        deduped.append(post)

    logger.info(f"[{run_id}] dedup_node: {len(deduped)} unique new posts")
    return {**state, "deduped_posts": deduped}


async def scoring_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: score each post 0-100 using Claude.
    Applies fast-lane bonus for posts < 48h old.
    """
    run_id = state["run_id"]
    posts: list[dict] = state.get("deduped_posts", [])
    logger.info(f"[{run_id}] scoring_node: scoring {len(posts)} posts")

    async def _score_one(post: dict) -> dict:
        result = await score_post(
            post_text=post.get("post_text", ""),
            reactions=post.get("reactions", 0),
            comments=post.get("comments", 0),
            posted_at=post.get("posted_at", ""),
        )
        base_score = result.get("score", 0)
        fast_lane = _is_fast_lane(post.get("posted_at"))
        final_score = min(100, base_score + (FAST_LANE_BONUS if fast_lane else 0))

        return {
            **post,
            "score": final_score,
            "topic_cluster": result.get("topic_cluster", "sales-outbound"),
            "fast_lane": fast_lane,
            "score_reasoning": result.get("reasoning", ""),
        }

    # Score concurrently, but rate-limit to 5 at a time to respect API limits
    scored: list[dict] = []
    batch_size = 5
    for i in range(0, len(posts), batch_size):
        batch = posts[i : i + batch_size]
        results = await asyncio.gather(*[_score_one(p) for p in batch])
        scored.extend(results)
        if i + batch_size < len(posts):
            await asyncio.sleep(1)  # brief pause between batches

    fast_lane_count = sum(1 for p in scored if p.get("fast_lane"))
    logger.info(
        f"[{run_id}] scoring_node: done. fast_lane={fast_lane_count}"
    )

    return {
        **state,
        "scored_posts": scored,
        "fast_lane_count": fast_lane_count,
    }


async def select_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: take top 25 posts by score.
    """
    run_id = state["run_id"]
    scored: list[dict] = state.get("scored_posts", [])
    top = sorted(scored, key=lambda p: p.get("score", 0), reverse=True)[:25]
    logger.info(f"[{run_id}] select_node: selected top {len(top)} posts")
    return {**state, "selected_posts": top}
