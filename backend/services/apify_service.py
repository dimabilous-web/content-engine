"""
Apify service — cost-optimised LinkedIn scrapers.

Uses supreme_coder~linkedin-post actor for BOTH keyword search and profile posts.
Actor input: { "urls": [...LinkedIn search/profile URLs], "maxResults": N }

Discovery strategy:
  PRIMARY  (80%) — keyword viral search, cap ~120 posts
  SECONDARY (20%) — 6 monitored profiles, cap ~30 posts
  TOTAL cap: 150 raw posts per run
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from urllib.parse import quote_plus
from typing import Any

import httpx

logger = logging.getLogger(__name__)

APIFY_API_KEY = os.environ["APIFY_API_KEY"]
APIFY_BASE    = "https://api.apify.com/v2"

# supreme_coder/linkedin-post — verified working, PAY_PER_EVENT $1/1k
ACTOR_ID = "supreme_coder~linkedin-post"

# Monitored profiles (secondary signal)
MONITORED_PROFILES: list[dict[str, str]] = [
    {"handle": "leadgenmanthan",               "name": "Manthan"},
    {"handle": "nick-saraev",                  "name": "Nick Saraev"},
    {"handle": "alex-vacca",                   "name": "Alex Vacca"},
    {"handle": "charlie-hills",                "name": "Charlie Hills"},
    {"handle": "suleiman-najim-87457a211",     "name": "Suleiman Najim"},
    {"handle": "luke-pierce-boom-automations", "name": "Luke Pierce"},
]

# 14 keyword queries — rotate 7 per run
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

MAX_POSTS_PER_PROFILE  = 10
MAX_KEYWORD_POSTS      = 120
TOTAL_POST_CAP         = 150
QUERIES_PER_RUN        = 7
# Engagement thresholds for keyword posts (profile posts bypass filter)
MIN_REACTIONS_KEYWORD  = 50
MIN_COMMENTS_KEYWORD   = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _int(val: Any) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _build_keyword_url(query: str) -> str:
    """LinkedIn search URL for a keyword query sorted by recency."""
    encoded = quote_plus(query)
    return f"https://www.linkedin.com/search/results/content/?keywords={encoded}&sortBy=date_posted"


def _build_profile_url(handle: str) -> str:
    """LinkedIn profile recent-activity URL for a handle."""
    return f"https://www.linkedin.com/in/{handle}/recent-activity/shares/"


def _normalise(item: dict, source_type: str = "keyword") -> dict:
    """
    Normalise supreme_coder~linkedin-post output.

    Key fields from this actor:
      text, url, numLikes (str), numComments (str),
      postedAtISO, authorName, authorProfileUrl,
      authorHeadline, authorProfileId
    """
    return {
        "author_name":  item.get("authorName") or "Unknown",
        "author_url":   item.get("authorProfileUrl") or "",
        "post_url":     item.get("url") or "",
        "post_text":    item.get("text") or "",
        "reactions":    _int(item.get("numLikes") or item.get("numReactions") or 0),
        "comments":     _int(item.get("numComments") or 0),
        "posted_at":    item.get("postedAtISO") or item.get("postedAt") or "",
        "source_type":  source_type,
    }


def _passes_engagement_filter(post: dict, source_type: str = "keyword") -> bool:
    """Profile posts bypass the engagement filter (always include)."""
    if source_type == "profile":
        return True
    return (
        post["reactions"] >= MIN_REACTIONS_KEYWORD
        or post["comments"] >= MIN_COMMENTS_KEYWORD
    )


# ---------------------------------------------------------------------------
# Core actor runner
# ---------------------------------------------------------------------------

async def _run_actor(
    urls: list[str],
    max_results: int = 30,
    timeout_secs: int = 180,
    memory_mb: int = 512,
) -> tuple[list[dict], float]:
    """
    Run supreme_coder~linkedin-post with a list of URLs.
    Returns (items, compute_units).
    """
    input_data = {"urls": urls, "maxResults": max_results}
    params = {
        "token":   APIFY_API_KEY,
        "memory":  memory_mb,
        "timeout": timeout_secs,
    }

    async with httpx.AsyncClient(timeout=timeout_secs + 60) as client:
        # Start run
        resp = await client.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            params=params,
            json=input_data,
        )
        if resp.status_code >= 400:
            logger.error(f"Apify start failed {resp.status_code}: {resp.text[:200]}")
            return [], 0.0

        run_id = resp.json()["data"]["id"]
        logger.info(f"Apify run started: {run_id} | urls={len(urls)} | maxResults={max_results}")

        # Poll
        poll_url   = f"{APIFY_BASE}/acts/{ACTOR_ID}/runs/{run_id}"
        deadline   = time.monotonic() + timeout_secs
        poll_delay = 5.0

        while time.monotonic() < deadline:
            await asyncio.sleep(poll_delay)
            pr = await client.get(poll_url, params={"token": APIFY_API_KEY})
            pr.raise_for_status()
            run_data = pr.json()["data"]
            status   = run_data.get("status", "")

            if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
                cu = (run_data.get("stats") or {}).get("computeUnits", 0.0)
                logger.info(f"Run {run_id}: {status} | CU={cu:.4f}")

                if status != "SUCCEEDED":
                    return [], cu

                ds_id  = run_data["defaultDatasetId"]
                dr = await client.get(
                    f"{APIFY_BASE}/datasets/{ds_id}/items",
                    params={"token": APIFY_API_KEY, "clean": "true", "format": "json"},
                )
                dr.raise_for_status()
                items = dr.json()
                if not isinstance(items, list):
                    items = items.get("items", [])
                logger.info(f"  → {len(items)} items")
                return items, cu

            poll_delay = min(poll_delay * 1.4, 30.0)

        logger.warning(f"Run {run_id} client timeout after {timeout_secs}s")
        return [], 0.0


# ---------------------------------------------------------------------------
# Query rotation
# ---------------------------------------------------------------------------

def select_queries_for_run(run_index: int, n: int = QUERIES_PER_RUN) -> list[str]:
    total  = len(ALL_KEYWORD_QUERIES)
    start  = (run_index * n) % total
    indices = [(start + i) % total for i in range(n)]
    selected = [ALL_KEYWORD_QUERIES[i] for i in indices]
    logger.info(f"Rotation run_index={run_index}: queries → {selected}")
    return selected


# ---------------------------------------------------------------------------
# PRIMARY: keyword viral search
# ---------------------------------------------------------------------------

async def scrape_keywords(
    queries: list[str],
    cap: int = MAX_KEYWORD_POSTS,
) -> tuple[list[dict], float]:
    """
    Batch all keyword queries into one actor run (multiple search URLs).
    Filters by engagement threshold. Returns (posts, compute_units).
    """
    per_query = max(10, cap // max(len(queries), 1))
    urls = [_build_keyword_url(q) for q in queries]

    try:
        items, cu = await _run_actor(
            urls=urls,
            max_results=min(cap, per_query * len(queries)),
            timeout_secs=180,
            memory_mb=512,
        )
    except Exception as e:
        logger.error(f"Keyword scrape error: {e}")
        return [], 0.0

    posts: list[dict] = []
    seen:  set[str]   = set()

    for item in items:
        post = _normalise(item, source_type="keyword")
        url  = post["post_url"]
        if not url or url in seen:
            continue
        if not _passes_engagement_filter(post, "keyword"):
            continue
        seen.add(url)
        posts.append(post)
        if len(posts) >= cap:
            break

    logger.info(f"Keyword search ({len(queries)} queries): {len(posts)} posts after filter (CU={cu:.4f})")
    return posts, cu


# ---------------------------------------------------------------------------
# SECONDARY: profile monitor
# ---------------------------------------------------------------------------

async def scrape_profiles(
    profiles: list[dict] | None = None,
    max_posts_per_profile: int  = MAX_POSTS_PER_PROFILE,
) -> tuple[list[dict], float]:
    """
    Scrape recent posts from all monitored profiles in one batched actor run.
    Profile posts bypass the engagement filter.
    Returns (posts, compute_units).
    """
    profiles = profiles or MONITORED_PROFILES
    urls = [_build_profile_url(p["handle"]) for p in profiles]

    try:
        items, cu = await _run_actor(
            urls=urls,
            max_results=max_posts_per_profile * len(profiles),
            timeout_secs=180,
            memory_mb=512,
        )
    except Exception as e:
        logger.error(f"Profile scrape error: {e}")
        return [], 0.0

    posts: list[dict] = []
    seen:  set[str]   = set()

    for item in items:
        post = _normalise(item, source_type="profile")
        url  = post["post_url"]
        if not url or url in seen:
            continue
        seen.add(url)
        posts.append(post)

    logger.info(f"Profile scrape ({len(profiles)} profiles): {len(posts)} posts (CU={cu:.4f})")
    return posts, cu


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------

async def scrape_all(
    run_index:    int               = 0,
    profiles:     list[dict] | None = None,
    extra_queries: list[str] | None = None,
) -> tuple[list[dict], float]:
    """
    Full discovery run — keyword + profile in parallel.
    Returns (posts, total_compute_units).
    """
    queries = select_queries_for_run(run_index)
    if extra_queries:
        queries = list(dict.fromkeys(queries + extra_queries))[:QUERIES_PER_RUN + 2]

    keyword_task = asyncio.create_task(scrape_keywords(queries, cap=MAX_KEYWORD_POSTS))
    profile_task = asyncio.create_task(scrape_profiles(profiles=profiles))

    (keyword_posts, kw_cu), (profile_posts, prof_cu) = await asyncio.gather(
        keyword_task, profile_task
    )
    total_cu = kw_cu + prof_cu

    all_posts: list[dict] = []
    seen_urls: set[str]   = set()

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
