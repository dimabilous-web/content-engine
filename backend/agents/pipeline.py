"""
LangGraph pipeline — wires all nodes into a StateGraph.

Flow:
  discovery → dedup → scoring → select → transform → output

Cost optimisations baked in:
  - dedup runs BEFORE any Claude calls
  - keyword rotation via run_index (7 of 14 queries per run)
  - 150-post hard cap from discovery
  - top-25 selection before transform (caps Claude idea-gen to ~50 calls)
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langgraph.graph import StateGraph, END

from agents.discovery import discovery_node
from agents.scoring import dedup_node, scoring_node, select_node
from agents.transform import transform_node
from agents.output import output_node
from services.apify_service import select_queries_for_run

logger = logging.getLogger(__name__)

PipelineStateDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def _route_after_discovery(state: PipelineStateDict) -> str:
    if state.get("error") or not state.get("raw_posts"):
        logger.warning("Discovery returned no posts or errored — jumping to output")
        return "output"
    return "dedup"


def _route_after_dedup(state: PipelineStateDict) -> str:
    if not state.get("deduped_posts"):
        logger.info("No new posts after dedup — jumping to output")
        return "output"
    return "scoring"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_pipeline() -> Any:
    graph = StateGraph(PipelineStateDict)

    graph.add_node("discovery", discovery_node)
    graph.add_node("dedup",     dedup_node)
    graph.add_node("scoring",   scoring_node)
    graph.add_node("select",    select_node)
    graph.add_node("transform", transform_node)
    graph.add_node("output",    output_node)

    graph.set_entry_point("discovery")

    graph.add_conditional_edges("discovery", _route_after_discovery, {
        "dedup":  "dedup",
        "output": "output",
    })
    graph.add_conditional_edges("dedup", _route_after_dedup, {
        "scoring": "scoring",
        "output":  "output",
    })
    graph.add_edge("scoring",   "select")
    graph.add_edge("select",    "transform")
    graph.add_edge("transform", "output")
    graph.add_edge("output",    END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_pipeline(
    airtable_service: Any,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute the full pipeline.
    Handles run_index rotation, Airtable run record lifecycle, error capture.
    """
    run_id = run_id or str(uuid.uuid4())[:8]
    logger.info(f"Pipeline starting: run_id={run_id}")

    # ------------------------------------------------------------------ #
    # Rotation index = number of completed runs so far                   #
    # ------------------------------------------------------------------ #
    try:
        run_index = airtable_service.count_completed_runs()
    except Exception as e:
        logger.warning(f"Could not fetch run count for rotation: {e}")
        run_index = 0

    queries_this_run = select_queries_for_run(run_index)
    logger.info(f"[{run_id}] run_index={run_index}, queries={queries_this_run}")

    # ------------------------------------------------------------------ #
    # Dedup: load seen post IDs BEFORE starting (cheap, saves LLM cost)  #
    # ------------------------------------------------------------------ #
    try:
        seen_post_ids = airtable_service.get_seen_post_ids()
        logger.info(f"[{run_id}] Loaded {len(seen_post_ids)} seen post IDs")
    except Exception as e:
        logger.warning(f"[{run_id}] Could not fetch seen IDs: {e}")
        seen_post_ids = set()

    # ------------------------------------------------------------------ #
    # Create run record in Airtable                                       #
    # ------------------------------------------------------------------ #
    try:
        run_record      = airtable_service.create_run(run_id, run_index=run_index)
        run_airtable_id = run_record["id"]
        logger.info(f"[{run_id}] Created run record {run_airtable_id}")
    except Exception as e:
        logger.error(f"[{run_id}] Failed to create run record: {e}")
        run_airtable_id = None

    initial_state: PipelineStateDict = {
        "run_id":               run_id,
        "run_index":            run_index,
        "status":               "Running",
        "raw_posts":            [],
        "deduped_posts":        [],
        "scored_posts":         [],
        "selected_posts":       [],
        "ideas":                [],
        "error":                None,
        "posts_discovered":     0,
        "ideas_generated":      0,
        "fast_lane_count":      0,
        "apify_compute_units":  0.0,
        "queries_run":          queries_this_run,
        "seen_post_ids":        seen_post_ids,
        "airtable_service":     airtable_service,
        "run_airtable_id":      run_airtable_id,
    }

    pipeline = build_pipeline()

    try:
        final = await pipeline.ainvoke(initial_state)
        logger.info(
            f"[{run_id}] Pipeline complete | "
            f"posts={final.get('posts_discovered')} | "
            f"ideas={final.get('ideas_generated')} | "
            f"fast_lane={final.get('fast_lane_count')} | "
            f"apify_CU={final.get('apify_compute_units', 0):.4f}"
        )
        return final
    except Exception as e:
        logger.error(f"[{run_id}] Pipeline crashed: {e}", exc_info=True)
        if run_airtable_id:
            try:
                airtable_service.update_run(run_airtable_id, {
                    "status": "Failed",
                    "notes":  str(e),
                })
            except Exception:
                pass
        return {**initial_state, "status": "Failed", "error": str(e)}
