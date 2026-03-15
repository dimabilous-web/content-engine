"""
Airtable service — wraps pyairtable v3 for all DB operations.
Uses the native create_base + Metadata API for provisioning.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pyairtable import Api

logger = logging.getLogger(__name__)

AIRTABLE_TOKEN = os.environ["AIRTABLE_TOKEN"]
BASE_NAME = "Content Engine"

# Table names
T_RAW_POSTS = "Raw Posts"
T_IDEAS     = "Generated Ideas"
T_RUNS      = "Runs"
T_PUBLISHED = "Published Posts"


# ---------------------------------------------------------------------------
# Schema definitions (passed to create_base)
# ---------------------------------------------------------------------------

TABLE_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": T_RAW_POSTS,
        "fields": [
            {"name": "post_id",       "type": "singleLineText"},
            {"name": "author_name",   "type": "singleLineText"},
            {"name": "author_url",    "type": "url"},
            {"name": "post_url",      "type": "url"},
            {"name": "post_text",     "type": "multilineText"},
            {"name": "reactions",     "type": "number",   "options": {"precision": 0}},
            {"name": "comments",      "type": "number",   "options": {"precision": 0}},
            {"name": "posted_at",     "type": "singleLineText"},
            {"name": "scraped_at",    "type": "singleLineText"},
            {"name": "score",         "type": "number",   "options": {"precision": 1}},
            {
                "name": "topic_cluster",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "sales-outbound"},
                        {"name": "marketing-content"},
                        {"name": "gtm-engineer"},
                        {"name": "new-tools"},
                        {"name": "systems-playbooks"},
                    ]
                },
            },
            {"name": "fast_lane",  "type": "checkbox", "options": {"icon": "check", "color": "yellowBright"}},
            {"name": "batch_id",   "type": "singleLineText"},
        ],
    },
    {
        "name": T_IDEAS,
        "fields": [
            {"name": "idea_id",         "type": "singleLineText"},
            {"name": "hook",            "type": "singleLineText"},
            {"name": "outline",         "type": "multilineText"},
            {
                "name": "post_type",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "CTA Post"},
                        {"name": "Hot Take"},
                        {"name": "System Reveal"},
                        {"name": "Feature Drop"},
                        {"name": "Trend Post"},
                        {"name": "Story"},
                    ]
                },
            },
            {
                "name": "topic_cluster",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "sales-outbound"},
                        {"name": "marketing-content"},
                        {"name": "gtm-engineer"},
                        {"name": "new-tools"},
                        {"name": "systems-playbooks"},
                    ]
                },
            },
            {
                "name": "effort",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Quick Edit"},
                        {"name": "Medium"},
                        {"name": "Heavy"},
                    ]
                },
            },
            {"name": "cta_word",          "type": "singleLineText"},
            {"name": "source_post_id",    "type": "singleLineText"},
            {"name": "source_reactions",  "type": "number", "options": {"precision": 0}},
            {"name": "source_author",     "type": "singleLineText"},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "New"},
                        {"name": "Approved"},
                        {"name": "Skipped"},
                        {"name": "Draft"},
                        {"name": "Published"},
                    ]
                },
            },
            {"name": "generated_draft", "type": "multilineText"},
            {"name": "dima_notes",      "type": "multilineText"},
            {"name": "batch_id",        "type": "singleLineText"},
            {"name": "created_at",      "type": "singleLineText"},
        ],
    },
    {
        "name": T_RUNS,
        "fields": [
            {"name": "run_id",            "type": "singleLineText"},
            {"name": "triggered_at",      "type": "singleLineText"},
            {
                "name": "status",
                "type": "singleSelect",
                "options": {
                    "choices": [
                        {"name": "Running"},
                        {"name": "Done"},
                        {"name": "Failed"},
                    ]
                },
            },
            {"name": "posts_discovered",  "type": "number", "options": {"precision": 0}},
            {"name": "ideas_generated",   "type": "number", "options": {"precision": 0}},
            {"name": "fast_lane_count",   "type": "number", "options": {"precision": 0}},
            # Cost tracking
            {"name": "apify_compute_units","type": "number", "options": {"precision": 4}},
            {"name": "queries_run",        "type": "multilineText"},  # JSON list of queries used
            {"name": "run_index",          "type": "number", "options": {"precision": 0}},
            {"name": "notes",              "type": "multilineText"},
        ],
    },
    {
        "name": T_PUBLISHED,
        "fields": [
            {"name": "post_id",           "type": "singleLineText"},
            {"name": "final_text",        "type": "multilineText"},
            {
                "name": "platform",
                "type": "singleSelect",
                "options": {"choices": [{"name": "LinkedIn"}, {"name": "X"}]},
            },
            {"name": "posted_at",         "type": "singleLineText"},
            {"name": "reactions",         "type": "number", "options": {"precision": 0}},
            {"name": "comments",          "type": "number", "options": {"precision": 0}},
            {"name": "idea_id",           "type": "singleLineText"},
            {"name": "performance_notes", "type": "multilineText"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Base provisioning
# ---------------------------------------------------------------------------

async def get_or_create_base() -> str:
    """
    Returns the Airtable base ID for Content Engine.

    Priority:
      1. AIRTABLE_BASE_ID env var — just use it (happy path after setup.py)
      2. Scan api.bases() for an existing 'Content Engine' base
      3. Try workspace-based creation if AIRTABLE_WORKSPACE_ID is set
      4. Raise a clear error with instructions

    Tables are NOT auto-provisioned here — run setup.py once for that.
    """
    # 1) Check env first
    base_id = os.environ.get("AIRTABLE_BASE_ID", "").strip()
    if base_id:
        logger.info(f"Using AIRTABLE_BASE_ID from env: {base_id}")
        return base_id

    api = Api(AIRTABLE_TOKEN)

    # 2) Scan existing bases
    try:
        bases = api.bases()
        for base in bases:
            if base.name == BASE_NAME:
                base_id = base.id
                logger.info(f"Found existing '{BASE_NAME}' base via API: {base_id}")
                _persist_base_id(base_id)
                return base_id
    except Exception as e:
        logger.warning(f"Could not list bases: {e}")

    # 3) Try workspace-based creation
    workspace_id = os.environ.get("AIRTABLE_WORKSPACE_ID", "").strip()
    if workspace_id:
        try:
            new_base = api.create_base(workspace_id, BASE_NAME, TABLE_SCHEMAS)
            base_id  = new_base.id
            logger.info(f"Created new Airtable base '{BASE_NAME}': {base_id}")
            _persist_base_id(base_id)
            return base_id
        except Exception as e:
            raise RuntimeError(f"Failed to create base in workspace {workspace_id}: {e}") from e

    # 4) Nothing worked
    raise RuntimeError(
        "Airtable not configured. Run setup:\n"
        "  python3 setup.py --base-id appXXXXXXXX\n"
        "Or set AIRTABLE_BASE_ID in .env after creating a base at airtable.com"
    )


async def _get_workspace_id(api: Api) -> Optional[str]:
    """Try to get a workspace ID via the Metadata API or from existing bases."""
    # Try from existing bases first
    try:
        bases = api.bases()
        if bases:
            # pyairtable Base objects have a workspace_id attribute
            for base in bases:
                wid = getattr(base, "workspace_id", None) or getattr(base, "workspaceId", None)
                if wid:
                    logger.info(f"Using workspace_id from existing base: {wid}")
                    return wid
    except Exception:
        pass

    # Fall back: Metadata API
    workspace_id = os.environ.get("AIRTABLE_WORKSPACE_ID", "").strip()
    if workspace_id:
        return workspace_id

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.airtable.com/v0/meta/workspaces",
                headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"},
            )
            if resp.status_code == 200:
                ws = resp.json().get("workspaces", [])
                if ws:
                    wid = ws[0]["id"]
                    logger.info(f"Found workspace via Metadata API: {wid}")
                    return wid
    except Exception as e:
        logger.warning(f"Workspace API call failed: {e}")

    return None


def _persist_base_id(base_id: str) -> None:
    """Write/update AIRTABLE_BASE_ID in .env and process env."""
    os.environ["AIRTABLE_BASE_ID"] = base_id
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    try:
        lines: list[str] = []
        found = False
        if os.path.exists(env_path):
            with open(env_path) as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith("AIRTABLE_BASE_ID="):
                    lines[i] = f"AIRTABLE_BASE_ID={base_id}\n"
                    found = True
                    break
        if not found:
            lines.append(f"AIRTABLE_BASE_ID={base_id}\n")
        with open(env_path, "w") as f:
            f.writelines(lines)
        logger.info(f"Persisted AIRTABLE_BASE_ID={base_id} to .env")
    except Exception as e:
        logger.warning(f"Could not write base ID to .env: {e}")


# ---------------------------------------------------------------------------
# AirtableService
# ---------------------------------------------------------------------------

class AirtableService:
    """Thin wrapper around pyairtable v3 for the four Content Engine tables."""

    def __init__(self, base_id: str):
        self.api = Api(AIRTABLE_TOKEN)
        self.base_id = base_id
        self._raw_posts = self.api.table(base_id, T_RAW_POSTS)
        self._ideas     = self.api.table(base_id, T_IDEAS)
        self._runs      = self.api.table(base_id, T_RUNS)
        self._published = self.api.table(base_id, T_PUBLISHED)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def make_post_id(post_url: str) -> str:
        return hashlib.sha256(post_url.encode()).hexdigest()[:16]

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Raw Posts
    # ------------------------------------------------------------------

    def get_seen_post_ids(self) -> set[str]:
        """Return all post_ids in Raw Posts (for global dedup)."""
        records = self._raw_posts.all(fields=["post_id"])
        return {
            r["fields"]["post_id"]
            for r in records
            if r["fields"].get("post_id")
        }

    def upsert_raw_posts(self, posts: list[dict[str, Any]]) -> list[dict]:
        """Batch-insert raw posts. Silently skips failures."""
        created: list[dict] = []
        for post in posts:
            try:
                record = self._raw_posts.create(post)
                created.append(record)
            except Exception as e:
                logger.warning(f"Failed to insert post {post.get('post_id')}: {e}")
        return created

    def get_raw_posts(
        self,
        batch_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        formula = f"{{batch_id}}='{batch_id}'" if batch_id else None
        kwargs: dict[str, Any] = {}
        if formula:
            kwargs["formula"] = formula
        records = self._raw_posts.all(**kwargs)
        return records[offset : offset + limit]

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(self, run_id: str, run_index: int = 0) -> dict:
        return self._runs.create({
            "run_id":               run_id,
            "triggered_at":         self.now_iso(),
            "status":               "Running",
            "posts_discovered":     0,
            "ideas_generated":      0,
            "fast_lane_count":      0,
            "apify_compute_units":  0.0,
            "run_index":            run_index,
        })

    def update_run(self, airtable_record_id: str, fields: dict[str, Any]) -> dict:
        return self._runs.update(airtable_record_id, fields)

    def get_run_by_run_id(self, run_id: str) -> Optional[dict]:
        records = self._runs.all(formula=f"{{run_id}}='{run_id}'")
        return records[0] if records else None

    def list_runs(self, limit: int = 20) -> list[dict]:
        # Sort descending by triggered_at
        records = self._runs.all(sort=[{"field": "triggered_at", "direction": "desc"}])
        return records[:limit]

    def count_completed_runs(self) -> int:
        """Return total number of Done/Failed runs (used to compute rotation index)."""
        records = self._runs.all(
            formula="OR({status}='Done', {status}='Failed')",
            fields=["run_id"],
        )
        return len(records)

    # ------------------------------------------------------------------
    # Ideas
    # ------------------------------------------------------------------

    def create_ideas(self, ideas: list[dict[str, Any]]) -> list[dict]:
        created: list[dict] = []
        for idea in ideas:
            try:
                record = self._ideas.create(idea)
                created.append(record)
            except Exception as e:
                logger.warning(f"Failed to create idea: {e}")
        return created

    def get_ideas(
        self,
        status:        Optional[str] = None,
        post_type:     Optional[str] = None,
        topic_cluster: Optional[str] = None,
        effort:        Optional[str] = None,
        limit:         int = 50,
        offset:        int = 0,
    ) -> list[dict]:
        parts: list[str] = []
        if status:        parts.append(f"{{status}}='{status}'")
        if post_type:     parts.append(f"{{post_type}}='{post_type}'")
        if topic_cluster: parts.append(f"{{topic_cluster}}='{topic_cluster}'")
        if effort:        parts.append(f"{{effort}}='{effort}'")

        formula = (
            "AND(" + ", ".join(parts) + ")" if len(parts) > 1
            else parts[0] if parts
            else None
        )

        kwargs: dict[str, Any] = {
            "sort": [{"field": "created_at", "direction": "desc"}],
        }
        if formula:
            kwargs["formula"] = formula

        records = self._ideas.all(**kwargs)
        return records[offset : offset + limit]

    def get_idea(self, idea_id: str) -> Optional[dict]:
        records = self._ideas.all(formula=f"{{idea_id}}='{idea_id}'")
        return records[0] if records else None

    def update_idea(self, airtable_record_id: str, fields: dict[str, Any]) -> dict:
        return self._ideas.update(airtable_record_id, fields)

    # ------------------------------------------------------------------
    # Published Posts
    # ------------------------------------------------------------------

    def create_published_post(self, post: dict[str, Any]) -> dict:
        return self._published.create(post)
