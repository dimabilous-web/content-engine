"""
Apify service — cost-optimised LinkedIn scrapers.

Discovery strategy:
  PRIMARY  (80%) — keyword viral search across all of LinkedIn, cap ~120 posts
  SECONDARY (20%) — 6 monitored profiles batched in one actor call, cap ~30 posts
  TOTAL cap: 150 raw posts per run

Cost tracking:
  Each actor run returns Apify compute-unit usage → stored in Runs table.

Rotation:
  14 keyword queries defined; 7 run per pipeline execution (rotate via run index).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

APIFY_API_KEY = os.environ["APIFY_API_KEY"]
APIFY_BASE    = "https://api.apify.com/v2"

# ---------------------------------------------------------------------------
# Actor IDs (verified via Apify store — sorted by total runs)
# ---------------------------------------------------------------------------
# Profile posts: harvestapi (5M runs) — per-result billing $2/1k
PROFILE_ACTOR  = "harvestapi~linkedin-profile-posts"
# Keyword/search: curious_coder (5M runs) — most popular search scraper
KEYWORD_ACTOR  = "curious_coder~linkedin-post-search-scraper"

# ---------------------------------------------------------------------------
# Monitored profiles (secondary signal — always scraped, capped at 5 each)
# ---------------------------------------------------------------------------
MONITORED_PROFILES: list[dict[str, str]] = [
    {"handle": "leadgenmanthan",               "name": "Manthan"},
    {"handle": "nick-saraev",                  "name": "Nick Saraev"},
    {"handle": "alex-vacca",                   "name": "Alex Vacca"},
    {"handle": "charlie-hills",                "name": "Charlie Hills"},
    {"handle": "suleiman-najim-87457a211",     "name": "Suleiman Najim"},
    {"handle": "luke-pierce-boom-automations", "name": "Luke Pierce"},
]

LI_PROFILE_URL = "https://www.linkedin.com/in/{handle}"

# ---------------------------------------------------------------------------
# Keyword queries (14 total — rotate 7 per run)
# ---------------------------------------------------------------------------
ALL_KEYWORD_QUERIES: list[str] = [
    "AI agents sales",
    "AI agents outbound",
    "GTM engineer",
    "signal based outreach",
    "replace SDR AI",
    "AI marketing automation",
    "MCP server Claude",
    "AI lead generation",
    "revenue AI agents",
    "cold outreach dead",
    "LangGraph agents",
    "AI automation B2B",
    "AI agents revenue",
    "outbound automation 2026",
]

# Posts per profile in profile-scrape run
MAX_POSTS_PER_PROFILE = 5          # 6 profiles × 5 = 30 posts max
# Max posts from keyword search total
MAX_KEYWORD_POSTS = 120
# Total hard cap per run
TOTAL_POST_CAP = 150
# Queries to run per pipeline execution
QUERIES_PER_RUN = 7
# Minimum engagement for keyword results
MIN_REACTIONS_KEYWORD = 100
MIN_COMMENTS_KEYWORD  = 50


# ---------------------------------------------------------------------------
# ActorRun result dataclass
# ---------------------------------------------------------------------------

class ActorRunResult:
    __slots__ = ("items", "compute_units", "run_id", "status")

    def __init__(
        self,
        items: list[dict],
        compute_units: float = 0.0,
        run_id: str = "",
        status: str = "SUCCEEDED",
    ):
        self.items         = items
        self.compute_units = compute_units
        self.run_id        = run_id
        self.status        = status


# ---------------------------------------------------------------------------
# Low-level actor runner (async start → poll → fetch items + cost)
# ---------------------------------------------------------------------------

async def _run_actor(
    actor_id: str,
    input_data: dict[str, Any],
    timeout_secs: int = 180,
    memory_mb: int = 512,
) -> ActorRunResult:
    """
    Start an Apify actor run, wait for completion, return items + compute cost.
    Uses two-step (start + poll + dataset) so we can capture cost metadata.
    """
    headers = {"Content-Type": "application/json"}
    params_start = {
        "token":   APIFY_API_KEY,
        "memory":  memory_mb,
        "timeout": timeout_secs,
    }

    async with httpx.AsyncClient(timeout=timeout_secs + 60) as client:
        # 1. Start run
        start_url = f"{APIFY_BASE}/acts/{actor_id}/runs"
        logger.info(f"Starting Apify actor: {actor_id}")
        resp = await client.post(start_url, params=params_start, headers=headers, json=input_data)

        if resp.status_code == 400:
            logger.error(f"Apify 400 starting {actor_id}: {resp.text[:400]}")
            return ActorRunResult(items=[], status="FAILED")
        if resp.status_code == 404:
            logger.error(f"Actor not found: {actor_id}")
            return ActorRunResult(items=[], status="NOT_FOUND")
        resp.raise_for_status()

        run_obj = resp.json().get("data", resp.json())
        run_id  = run_obj["id"]

        # 2. Poll until SUCCEEDED / FAILED / TIMED-OUT
        poll_url   = f"{APIFY_BASE}/acts/{actor_id}/runs/{run_id}"
        deadline   = time.monotonic() + timeout_secs
        poll_delay = 5  # seconds between polls

        while time.monotonic() < deadline:
            await asyncio.sleep(poll_delay)
            poll_resp = await client.get(poll_url, params={"token": APIFY_API_KEY})
            poll_resp.raise_for_status()
            run_data   = poll_resp.json().get("data", {})
            run_status = run_data.get("status", "")
            logger.debug(f"  Actor {run_id} status: {run_status}")

            if run_status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
                # Extract compute units used
                stats = run_data.get("stats", {})
                compute_units = stats.get("computeUnits", 0.0)
                logger.info(
                    f"Actor {actor_id} [{run_id}] finished: "
                    f"status={run_status}, computeUnits={compute_units:.4f}"
                )

                if run_status != "SUCCEEDED":
                    return ActorRunResult(
                        items=[],
                        compute_units=compute_units,
                        run_id=run_id,
                        status=run_status,
                    )

                # 3. Fetch dataset items
                dataset_id  = run_data.get("defaultDatasetId", "")
                items_url   = f"{APIFY_BASE}/datasets/{dataset_id}/items"
                items_resp  = await client.get(
                    items_url,
                    params={"token": APIFY_API_KEY, "clean": "true", "format": "json"},
                )
                items_resp.raise_for_status()
                items = items_resp.json()
                if not isinstance(items, list):
                    items = items.get("items", [])

                logger.info(f"  → {len(items)} items from {actor_id}")
                return ActorRunResult(
                    items=items,
                    compute_units=compute_units,
                    run_id=run_id,
                    status="SUCCEEDED",
                )

            poll_delay = min(poll_delay * 1.5, 30)  # back-off up to 30s

        logger.warning(f"Actor {run_id} timed out in client after {timeout_secs}s")
        return ActorRunResult(items=[], run_id=run_id, status="TIMED-OUT")


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _extract_reactions(item: dict) -> int:
    """
    Try every known field path for reaction/like counts across all actors.
    harvestapi:    item["socialContent"]["reactionsCount"] or item["reactions"]["total"]
    curious_coder: item["numLikes"] or item["likeCount"]
    fallback:      item["likesCount"], item["reactions"], item["numReactions"]
    """
    # harvestapi nested paths
    sc = item.get("socialContent") or {}
    if sc.get("reactionsCount") is not None:
        return _int(sc["reactionsCount"])
    reactions_obj = item.get("reactions")
    if isinstance(reactions_obj, dict):
        if reactions_obj.get("total") is not None:
            return _int(reactions_obj["total"])
    # Flat fields
    for key in ("numLikes", "likeCount", "likesCount", "numReactions",
                "reactionCount", "totalReactionCount"):
        if item.get(key) is not None:
            return _int(item[key])
    # curious_coder may return a plain int under "reactions"
    if isinstance(reactions_obj, int):
        return reactions_obj
    return 0


def _extract_comments(item: dict) -> int:
    """Try every known field path for comment counts."""
    sc = item.get("socialContent") or {}
    if sc.get("commentsCount") is not None:
        return _int(sc["commentsCount"])
    for key in ("numComments", "commentCount", "commentsCount", "totalCommentCount"):
        if item.get(key) is not None:
            return _int(item[key])
    return 0


def _extract_posted_at(item: dict) -> str:
    """Normalise timestamp to ISO string."""
    # harvestapi: item["postedAt"]["date"]
    pa = item.get("postedAt")
    if isinstance(pa, dict):
        return pa.get("date") or pa.get("timestamp") or ""
    if isinstance(pa, str):
        return pa
    # curious_coder: item["postedAtISO"]
    return item.get("postedAtISO") or item.get("timestamp") or ""


def _normalise_profile_post(item: dict, profile_meta: dict) -> dict:
    """
    Normalise harvestapi~linkedin-profile-posts output.
    Fields: linkedinUrl, content, author.name, author.linkedinUrl, postedAt.date
    """
    author = item.get("author") or {}
    return {
        "author_name":  author.get("name") or item.get("authorName") or item.get("authorFullName") or profile_meta["name"],
        "author_url":   author.get("linkedinUrl") or item.get("authorProfileUrl") or LI_PROFILE_URL.format(handle=profile_meta["handle"]),
        "post_url":     item.get("linkedinUrl") or item.get("postUrl") or item.get("url") or "",
        "post_text":    item.get("content") or item.get("text") or item.get("postText") or "",
        "reactions":    _extract_reactions(item),
        "comments":     _extract_comments(item),
        "posted_at":    _extract_posted_at(item),
        "source_type":  "profile",
    }


def _normalise_keyword_post(item: dict) -> dict:
    """
    Normalise curious_coder~linkedin-post-search-scraper output.
    Fields: url, text, authorProfileUrl, authorName/authorFullName, postedAtISO
    """
    author = item.get("author") or {}
    return {
        "author_name":  (
            item.get("authorName") or item.get("authorFullName")
            or author.get("name") or "Unknown"
        ),
        "author_url":   (
            item.get("authorProfileUrl") or item.get("authorUrl")
            or author.get("linkedinUrl") or ""
        ),
        "post_url":     item.get("url") or item.get("postUrl") or item.get("linkedinUrl") or "",
        "post_text":    item.get("text") or item.get("content") or item.get("postText") or "",
        "reactions":    _extract_reactions(item),
        "comments":     _extract_comments(item),
        "posted_at":    _extract_posted_at(item),
        "source_type":  "keyword",
    }


def _int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _passes_engagement_filter(post: dict) -> bool:
    """Keyword posts must have 100+ reactions OR 50+ comments."""
    return post["reactions"] >= MIN_REACTIONS_KEYWORD or post["comments"] >= MIN_COMMENTS_KEYWORD


# ---------------------------------------------------------------------------
# Query rotation
# ---------------------------------------------------------------------------

def select_queries_for_run(run_index: int, n: int = QUERIES_PER_RUN) -> list[str]:
    """
    Rotate through ALL_KEYWORD_QUERIES so each run covers a different subset.
    run_index=0 → queries 0..6, run_index=1 → queries 7..13, etc.
    Wraps around when exhausted.
    total = 14, n = 7 → 2 distinct batches before full cycle.
    """
    total = len(ALL_KEYWORD_QUERIES)
    start = (run_index * n) % total
    # Slice with wrap-around
    indices = [(start + i) % total for i in range(n)]
    selected = [ALL_KEYWORD_QUERIES[i] for i in indices]
    logger.info(f"Rotation run_index={run_index}: queries → {selected}")
    return selected


# ---------------------------------------------------------------------------
# PRIMARY: Keyword viral search
# ---------------------------------------------------------------------------

async def scrape_keywords(
    queries: list[str],
    cap: int = MAX_KEYWORD_POSTS,
) -> tuple[list[dict], float]:
    """
    Run keyword searches across LinkedIn using curious_coder~linkedin-post-search-scraper.
    Runs one query at a time (actor is per-query), collects up to `cap` total posts.
    Returns (posts, total_compute_units).
    """
    all_posts: list[dict] = []
    total_cu:  float      = 0.0
    seen_urls: set[str]   = set()
    per_query  = max(10, cap // len(queries))  # spread cap across queries

    for query in queries:
        if len(all_posts) >= cap:
            break

        # curious_coder accepts: keywords, count (or maxItems)
        input_data = {
            "keywords": query,
            "count":    per_query,
        }

        try:
            result   = await _run_actor(KEYWORD_ACTOR, input_data, timeout_secs=120, memory_mb=256)
            total_cu += result.compute_units

            for item in result.items:
                post = _normalise_keyword_post(item)
                url  = post.get("post_url", "")
                if not url or url in seen_urls:
                    continue
                if not _passes_engagement_filter(post):
                    continue
                seen_urls.add(url)
                all_posts.append(post)
                if len(all_posts) >= cap:
                    break

        except Exception as e:
            logger.error(f"Keyword scrape failed for {query!r}: {e}")

    logger.info(f"Keyword search ({len(queries)} queries): {len(all_posts)} posts (CU={total_cu:.4f})")
    return all_posts, total_cu


# ---------------------------------------------------------------------------
# SECONDARY: Profile monitor (batched — one call per profile)
# ---------------------------------------------------------------------------

async def scrape_profiles(
    profiles: list[dict] | None = None,
    max_posts_per_profile: int  = MAX_POSTS_PER_PROFILE,
) -> tuple[list[dict], float]:
    """
    Scrape recent posts from all monitored profiles.
    harvestapi~linkedin-profile-posts accepts one profile URL at a time,
    so we run all 6 concurrently (keeps total Apify calls to 6 vs sequential).
    Returns (posts, compute_units).
    """
    profiles = profiles or MONITORED_PROFILES

    async def _scrape_one(profile: dict) -> tuple[list[dict], float]:
        url = LI_PROFILE_URL.format(handle=profile["handle"])
        # harvestapi input: profileUrl (singular) + maxItems
        input_data = {
            "profileUrl": url,
            "maxItems":   max_posts_per_profile,
        }
        try:
            result = await _run_actor(PROFILE_ACTOR, input_data, timeout_secs=120, memory_mb=256)
            posts = []
            seen: set[str] = set()
            for item in result.items:
                post     = _normalise_profile_post(item, profile)
                post_url = post.get("post_url", "")
                if post_url and post_url not in seen:
                    seen.add(post_url)
                    posts.append(post)
            return posts, result.compute_units
        except Exception as e:
            logger.error(f"Profile scrape failed for {profile['handle']}: {e}")
            return [], 0.0

    # Run all 6 profiles concurrently
    results = await asyncio.gather(*[_scrape_one(p) for p in profiles])

    all_posts: list[dict] = []
    total_cu:  float      = 0.0
    seen_urls: set[str]   = set()

    for posts, cu in results:
        total_cu += cu
        for post in posts:
            url = post.get("post_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_posts.append(post)

    logger.info(f"Profile scrape ({len(profiles)} profiles): {len(all_posts)} posts (CU={total_cu:.4f})")
    return all_posts, total_cu


# ---------------------------------------------------------------------------
# Combined discovery entry point
# ---------------------------------------------------------------------------

async def scrape_all(
    run_index:   int               = 0,
    profiles:    list[dict] | None = None,
    extra_queries: list[str] | None = None,
) -> tuple[list[dict], float]:
    """
    Full discovery run:
      1. Keyword viral search (PRIMARY, cap 120)
      2. Profile monitor (SECONDARY, cap 30)
      3. Merge, dedup URLs, enforce 150-post total cap.

    Returns (posts, total_compute_units).
    """
    # Select rotated keyword queries
    queries = select_queries_for_run(run_index)
    if extra_queries:
        queries = list(dict.fromkeys(queries + extra_queries))[:QUERIES_PER_RUN + 2]

    # Run both scrapers concurrently
    keyword_task = asyncio.create_task(
        scrape_keywords(queries, cap=MAX_KEYWORD_POSTS)
    )
    profile_task = asyncio.create_task(
        scrape_profiles(profiles=profiles)
    )

    (keyword_posts, kw_cu), (profile_posts, prof_cu) = await asyncio.gather(
        keyword_task, profile_task
    )
    total_cu = kw_cu + prof_cu

    # Merge: keyword first (primary), then profile posts
    all_posts:  list[dict] = []
    seen_urls:  set[str]   = set()

    for post in keyword_posts + profile_posts:
        url = post.get("post_url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        all_posts.append(post)
        if len(all_posts) >= TOTAL_POST_CAP:
            break

    logger.info(
        f"scrape_all: {len(keyword_posts)} keyword + {len(profile_posts)} profile "
        f"→ {len(all_posts)} unique (cap={TOTAL_POST_CAP}, total_CU={total_cu:.4f})"
    )
    return all_posts, total_cu
