"""
Content Engine — FastAPI backend
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from agents.pipeline import run_pipeline
from models.schemas import (
    ConfigResponse,
    GeneratePostRequest,
    GeneratePostResponse,
    HealthResponse,
    IdeaDraftUpdate,
    IdeaStatusUpdate,
    TriggerRunResponse,
)
from services.airtable_service import AirtableService, get_or_create_base
from services.apify_service import MONITORED_PROFILES, ALL_KEYWORD_QUERIES, select_queries_for_run
from services.claude_service import generate_full_post

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("content_engine")

# ---------------------------------------------------------------------------
# App state
# ---------------------------------------------------------------------------

_airtable: Optional[AirtableService] = None
_run_status: dict[str, dict[str, Any]] = {}  # in-memory run status cache


# ---------------------------------------------------------------------------
# Lifespan (startup)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _airtable
    logger.info("Starting Content Engine backend…")
    try:
        base_id = await get_or_create_base()
        _airtable = AirtableService(base_id)
        logger.info(f"Airtable connected. Base ID: {base_id}")
    except Exception as e:
        logger.warning(
            f"Airtable not initialised on startup: {e}\n"
            "→ Set AIRTABLE_BASE_ID in .env, or run: python3 setup.py"
        )
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Content Engine API",
    description="Dima's personal LinkedIn Content Engine backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_airtable() -> AirtableService:
    if _airtable is None:
        raise HTTPException(status_code=503, detail="Airtable not initialised")
    return _airtable


# ---------------------------------------------------------------------------
# Background pipeline runner
# ---------------------------------------------------------------------------

async def _run_pipeline_bg(run_id: str, svc: AirtableService):
    _run_status[run_id] = {
        "run_id":               run_id,
        "status":               "Running",
        "triggered_at":         datetime.now(timezone.utc).isoformat(),
        "posts_discovered":     0,
        "ideas_generated":      0,
        "fast_lane_count":      0,
        "apify_compute_units":  0.0,
    }
    try:
        final = await run_pipeline(airtable_service=svc, run_id=run_id)
        _run_status[run_id].update({
            "status":               final.get("status", "Done"),
            "posts_discovered":     final.get("posts_discovered", 0),
            "ideas_generated":      final.get("ideas_generated", 0),
            "fast_lane_count":      final.get("fast_lane_count", 0),
            "apify_compute_units":  final.get("apify_compute_units", 0.0),
            "queries_run":          final.get("queries_run", []),
            "run_index":            final.get("run_index", 0),
            "error":                final.get("error"),
        })
    except Exception as e:
        logger.error(f"Background pipeline {run_id} crashed: {e}", exc_info=True)
        _run_status[run_id].update({"status": "Failed", "error": str(e)})


# ---------------------------------------------------------------------------
# Routes — Run management
# ---------------------------------------------------------------------------

@app.post("/run/trigger", response_model=TriggerRunResponse, tags=["Runs"])
async def trigger_run(
    background_tasks: BackgroundTasks,
    svc: AirtableService = Depends(get_airtable),
):
    """Start a new pipeline run (async — returns immediately with run_id)."""
    run_id = str(uuid.uuid4())[:8]
    background_tasks.add_task(_run_pipeline_bg, run_id, svc)
    return TriggerRunResponse(
        run_id=run_id,
        status="Running",
        message=f"Pipeline started. Poll /run/{run_id}/status for updates.",
    )


@app.get("/run/{run_id}/status", tags=["Runs"])
async def get_run_status(
    run_id: str,
    svc: AirtableService = Depends(get_airtable),
):
    """Check the status of a pipeline run."""
    # Check in-memory first (faster)
    if run_id in _run_status:
        return _run_status[run_id]

    # Fall back to Airtable
    record = svc.get_run_by_run_id(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return record["fields"]


@app.get("/runs", tags=["Runs"])
async def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    svc: AirtableService = Depends(get_airtable),
):
    """List recent pipeline runs."""
    records = svc.list_runs(limit=limit)
    return [r["fields"] for r in records]


@app.get("/stats", tags=["Stats"])
async def get_stats(svc: AirtableService = Depends(get_airtable)):
    """Dashboard summary stats."""
    new_ideas      = svc.get_ideas(status="New",      limit=200)
    approved_ideas = svc.get_ideas(status="Approved", limit=200)
    published      = svc.get_ideas(status="Published", limit=200)
    # fast lane: any New idea with fast_lane flag
    fast_lane = [r for r in new_ideas if r["fields"].get("fast_lane") or r["fields"].get("fast_lane_flag")]
    # published this week
    from datetime import datetime, timezone, timedelta
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pub_week = [r for r in published if str(r["fields"].get("created_at","")) >= week_ago]
    return {
        "ideas_new":       len(new_ideas),
        "ideas_approved":  len(approved_ideas),
        "published_week":  len(pub_week),
        "has_fast_lane":   len(fast_lane) > 0,
    }


# ---------------------------------------------------------------------------
# Routes — Ideas
# ---------------------------------------------------------------------------

@app.get("/ideas", tags=["Ideas"])
async def get_ideas(
    status:        Optional[str] = Query(default=None),
    post_type:     Optional[str] = Query(default=None),
    topic_cluster: Optional[str] = Query(default=None),
    effort:        Optional[str] = Query(default=None),
    limit:         int           = Query(default=50, ge=1, le=200),
    offset:        int           = Query(default=0, ge=0),
    page:          int           = Query(default=1, ge=1),
    svc: AirtableService = Depends(get_airtable),
):
    """Get ideas with optional filters. Returns { ideas: [...], total: N }."""
    # Support both offset and page (page takes priority if > 1)
    effective_offset = offset if page == 1 else (page - 1) * limit
    records = svc.get_ideas(
        status=status,
        post_type=post_type,
        topic_cluster=topic_cluster,
        effort=effort,
        limit=limit,
        offset=effective_offset,
    )
    items = [{"id": r["id"], **r["fields"]} for r in records]
    return {"ideas": items, "total": len(items)}


@app.get("/ideas/{idea_id}", tags=["Ideas"])
async def get_idea(
    idea_id: str,
    svc: AirtableService = Depends(get_airtable),
):
    """Get a single idea by idea_id."""
    record = svc.get_idea(idea_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    return {"id": record["id"], **record["fields"]}


@app.post("/ideas/{idea_id}/generate", response_model=GeneratePostResponse, tags=["Ideas"])
async def generate_post_for_idea(
    idea_id: str,
    body: GeneratePostRequest = GeneratePostRequest(),
    svc: AirtableService = Depends(get_airtable),
):
    """Generate a full LinkedIn post for an idea. Saves draft to Airtable."""
    record = svc.get_idea(idea_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")

    fields = record["fields"]

    # Fetch source post for context
    source_context = ""
    source_post_id = fields.get("source_post_id", "")
    if source_post_id:
        try:
            raw_records = svc.get_raw_posts()
            for rr in raw_records:
                if rr["fields"].get("post_id") == source_post_id:
                    source_context = rr["fields"].get("post_text", "")[:1000]
                    break
        except Exception:
            pass

    draft = await generate_full_post(
        hook=fields.get("hook", ""),
        outline=fields.get("outline", ""),
        post_type=fields.get("post_type", "CTA Post"),
        topic_cluster=fields.get("topic_cluster", "sales-outbound"),
        cta_word=fields.get("cta_word", "SYSTEM"),
        source_context=source_context,
    )

    # Save draft back to Airtable
    try:
        svc.update_idea(record["id"], {"generated_draft": draft})
    except Exception as e:
        logger.warning(f"Could not save draft to Airtable: {e}")

    return GeneratePostResponse(idea_id=idea_id, generated_draft=draft)


@app.patch("/ideas/{idea_id}/status", tags=["Ideas"])
async def update_idea_status(
    idea_id: str,
    body: IdeaStatusUpdate,
    svc: AirtableService = Depends(get_airtable),
):
    """Update an idea's status (New/Approved/Skipped/Draft/Published)."""
    record = svc.get_idea(idea_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    updated = svc.update_idea(record["id"], {"status": body.status.value})
    return {"id": updated["id"], **updated["fields"]}


@app.patch("/ideas/{idea_id}/draft", tags=["Ideas"])
async def save_idea_draft(
    idea_id: str,
    body: IdeaDraftUpdate,
    svc: AirtableService = Depends(get_airtable),
):
    """Save edited draft text (and optional notes) for an idea."""
    record = svc.get_idea(idea_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Idea {idea_id} not found")
    fields_to_update: dict[str, Any] = {"generated_draft": body.draft}
    if body.notes is not None:
        fields_to_update["dima_notes"] = body.notes
    updated = svc.update_idea(record["id"], fields_to_update)
    return {"id": updated["id"], **updated["fields"]}


# ---------------------------------------------------------------------------
# Routes — Raw Posts
# ---------------------------------------------------------------------------

@app.get("/posts/raw", tags=["Posts"])
async def get_raw_posts(
    batch_id: Optional[str] = Query(default=None),
    limit:    int           = Query(default=50, ge=1, le=200),
    offset:   int           = Query(default=0, ge=0),
    svc: AirtableService = Depends(get_airtable),
):
    """Browse raw scraped posts with pagination."""
    records = svc.get_raw_posts(batch_id=batch_id, limit=limit, offset=offset)
    return [{"id": r["id"], **r["fields"]} for r in records]


# ---------------------------------------------------------------------------
# Routes — Config
# ---------------------------------------------------------------------------

@app.get("/config", tags=["Config"])
async def get_config():
    """
    Get current config: monitored profiles, full keyword list,
    and which queries are active for the NEXT run.
    """
    # Determine next run index for rotation preview
    run_index = 0
    if _airtable is not None:
        try:
            run_index = _airtable.count_completed_runs()
        except Exception:
            run_index = 0

    next_queries = select_queries_for_run(run_index)

    return {
        "monitored_profiles": MONITORED_PROFILES,
        "search_queries": ALL_KEYWORD_QUERIES,         # full list (editable in dashboard)
        "next_run_queries": next_queries,               # what the next run will use
        "next_run_index": run_index,
        "queries_per_run": 7,
        "topic_clusters": [
            "sales-outbound",
            "marketing-content",
            "gtm-engineer",
            "new-tools",
            "systems-playbooks",
        ],
        "discovery_strategy": {
            "primary": "keyword viral search (80%, cap 120 posts)",
            "secondary": "6 monitored profiles (20%, cap 30 posts, 5/profile)",
            "total_cap": 150,
            "cadence": "weekly (manual trigger available)",
        },
        "cost_estimate": {
            "apify_per_run": "$0.50-2.00",
            "claude_per_run": "$0.10-0.30",
            "total_per_week": "<$3",
        },
    }


# ---------------------------------------------------------------------------
# Routes — Setup
# ---------------------------------------------------------------------------

@app.post("/setup/init-airtable", tags=["Setup"])
async def init_airtable(base_id: Optional[str] = None, workspace_id: Optional[str] = None):
    """
    One-time setup: connect to Airtable and create all tables.

    Provide EITHER:
    - base_id: ID of a blank base you created manually at airtable.com
      (find it in the URL: https://airtable.com/appXXXXXXXX/...)
    - workspace_id: your workspace ID if you want the base auto-created
      (find it in the URL: https://airtable.com/wspmK5bdNNFplwVVE/...)

    Example (recommended — create blank base first):
      POST /setup/init-airtable?base_id=appXXXXXXXXXXXXXX
    """
    global _airtable

    token = os.environ.get("AIRTABLE_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="AIRTABLE_TOKEN not configured")

    if _airtable is not None:
        return {
            "status":  "already_initialised",
            "base_id": _airtable.base_id,
            "message": "Airtable already connected.",
        }

    if not base_id and not workspace_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide base_id (recommended) or workspace_id. "
                "Create a blank base at airtable.com and copy the app... ID from the URL."
            ),
        )

    import httpx as _httpx
    from services.airtable_service import _persist_base_id

    # --- Path A: use existing base, create tables in it ---
    if base_id:
        actual_base_id = base_id.strip()
    else:
        # --- Path B: create base via workspace ---
        from pyairtable import Api
        from services.airtable_service import TABLE_SCHEMAS, BASE_NAME
        try:
            api      = Api(token)
            new_base = api.create_base(workspace_id.strip(), BASE_NAME, [])
            actual_base_id = new_base.id
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create base: {e}")

    # Create tables in the base
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    from setup import TABLES
    created_tables: list[str] = []
    async with _httpx.AsyncClient(timeout=30) as client:
        # Check existing tables
        r = await client.get(
            f"https://api.airtable.com/v0/meta/bases/{actual_base_id}/tables",
            headers=headers,
        )
        existing = set()
        if r.status_code == 200:
            existing = {t["name"] for t in r.json().get("tables", [])}

        for table in TABLES:
            if table["name"] in existing:
                created_tables.append(table["name"])
                continue
            tr = await client.post(
                f"https://api.airtable.com/v0/meta/bases/{actual_base_id}/tables",
                headers=headers,
                json=table,
            )
            if tr.status_code in (200, 201):
                created_tables.append(table["name"])
            else:
                logger.warning(f"Table creation failed: {table['name']}: {tr.text[:200]}")

    _persist_base_id(actual_base_id)
    _airtable = AirtableService(actual_base_id)
    logger.info(f"Airtable initialised via /setup: base={actual_base_id}, tables={created_tables}")

    return {
        "status":         "ready",
        "base_id":        actual_base_id,
        "tables_created": created_tables,
        "message":        f"Connected. {len(created_tables)}/4 tables ready.",
    }


@app.get("/setup/status", tags=["Setup"])
async def setup_status():
    """Check what still needs to be configured."""
    issues = []
    config = {}

    for key in ["AIRTABLE_TOKEN", "AIRTABLE_BASE_ID", "APIFY_API_KEY", "ANTHROPIC_API_KEY"]:
        val = os.environ.get(key, "")
        config[key] = "set" if val else "MISSING"
        if not val:
            issues.append(key)

    airtable_ok = _airtable is not None
    if not airtable_ok and "AIRTABLE_BASE_ID" not in issues:
        issues.append("Airtable not connected (check AIRTABLE_BASE_ID is valid)")

    return {
        "ready":         len(issues) == 0 and airtable_ok,
        "airtable_ok":   airtable_ok,
        "env_vars":      config,
        "issues":        issues,
        "next_step": (
            "Run: python3 setup.py  (or POST /setup/init-airtable?workspace_id=wsp...)"
            if not airtable_ok else "All good!"
        ),
    }


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """Health check — also verifies Airtable connectivity."""
    airtable_ok = False
    if _airtable is not None:
        try:
            _airtable.list_runs(limit=1)
            airtable_ok = True
        except Exception:
            airtable_ok = False

    return HealthResponse(
        status="ok",
        version="1.0.0",
        airtable_connected=airtable_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
