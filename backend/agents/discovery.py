"""
Discovery node — keyword-first, profile-second.

Priority:
  PRIMARY  (80%) — keyword viral search across all of LinkedIn
  SECONDARY (20%) — 6 monitored profiles (always watch, regardless of engagement)

run_index in state drives keyword rotation across weekly runs.
"""

from __future__ import annotations

import logging
from typing import Any

from services.apify_service import scrape_all

logger = logging.getLogger(__name__)


async def discovery_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node: scrape LinkedIn using keyword + profile strategy.

    Reads:
      state["run_id"]       — for logging
      state["run_index"]    — rotation index (how many previous runs in Airtable)
      state["profiles"]     — optional override list of profiles
      state["extra_queries"] — optional extra keyword queries

    Writes:
      state["raw_posts"]       — normalised post dicts
      state["posts_discovered"] — raw count before dedup
      state["apify_compute_units"] — float, for cost tracking
    """
    run_id       = state["run_id"]
    run_index    = state.get("run_index", 0)
    profiles     = state.get("profiles", None)
    extra_queries = state.get("extra_queries", None)

    logger.info(f"[{run_id}] discovery_node: run_index={run_index}")

    try:
        posts, compute_units = await scrape_all(
            run_index=run_index,
            profiles=profiles,
            extra_queries=extra_queries,
        )
        logger.info(
            f"[{run_id}] discovery_node: "
            f"{len(posts)} posts collected, CU={compute_units:.4f}"
        )
        return {
            **state,
            "raw_posts":           posts,
            "posts_discovered":    len(posts),
            "apify_compute_units": compute_units,
        }
    except Exception as e:
        logger.error(f"[{run_id}] discovery_node failed: {e}", exc_info=True)
        return {
            **state,
            "raw_posts":           [],
            "posts_discovered":    0,
            "apify_compute_units": 0.0,
            "error":               str(e),
        }
