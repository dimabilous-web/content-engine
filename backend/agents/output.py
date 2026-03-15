"""
Output node — writes raw posts, ideas, and run metadata to Airtable.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def output_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: persist everything to Airtable and close the run record.
    """
    run_id          = state["run_id"]
    svc             = state.get("airtable_service")
    run_airtable_id = state.get("run_airtable_id")

    if svc is None:
        logger.error(f"[{run_id}] output_node: no airtable_service in state")
        return {**state, "error": "No airtable_service in pipeline state"}

    # ------------------------------------------------------------------ #
    # 1. Write scored raw posts to Airtable                               #
    # ------------------------------------------------------------------ #
    posts_to_write: list[dict] = state.get("scored_posts", [])
    logger.info(f"[{run_id}] output_node: writing {len(posts_to_write)} raw posts")

    raw_records: list[dict] = []
    for post in posts_to_write:
        raw_records.append({
            "post_id":       post.get("post_id", ""),
            "author_name":   post.get("author_name", ""),
            "author_url":    post.get("author_url", "") or "",
            "post_url":      post.get("post_url", "") or "",
            "post_text":     (post.get("post_text", "") or "")[:100_000],
            "reactions":     int(post.get("reactions", 0)),
            "comments":      int(post.get("comments", 0)),
            "posted_at":     post.get("posted_at") or "",
            "scraped_at":    svc.now_iso(),
            "score":         float(post.get("score", 0)),
            "topic_cluster": post.get("topic_cluster", "") or "",
            "fast_lane":     bool(post.get("fast_lane", False)),
            "batch_id":      run_id,
        })

    svc.upsert_raw_posts(raw_records)

    # ------------------------------------------------------------------ #
    # 2. Write generated ideas                                            #
    # ------------------------------------------------------------------ #
    ideas: list[dict] = state.get("ideas", [])
    logger.info(f"[{run_id}] output_node: writing {len(ideas)} ideas")
    svc.create_ideas(ideas)

    # ------------------------------------------------------------------ #
    # 3. Update run record with final stats + Apify cost                  #
    # ------------------------------------------------------------------ #
    apify_cu     = float(state.get("apify_compute_units", 0.0))
    queries_run  = state.get("queries_run", [])

    if run_airtable_id:
        try:
            svc.update_run(run_airtable_id, {
                "status":               "Done",
                "posts_discovered":     state.get("posts_discovered", len(posts_to_write)),
                "ideas_generated":      state.get("ideas_generated", len(ideas)),
                "fast_lane_count":      state.get("fast_lane_count", 0),
                "apify_compute_units":  apify_cu,
                "queries_run":          json.dumps(queries_run),
            })
            logger.info(
                f"[{run_id}] Run closed: Done | "
                f"apify_CU={apify_cu:.4f} | "
                f"queries={len(queries_run)}"
            )
        except Exception as e:
            logger.error(f"[{run_id}] Failed to update run record: {e}")

    return {
        **state,
        "status": "Done",
    }
