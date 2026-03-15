"""
Pydantic v2 schemas for Content Engine backend.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    running = "Running"
    done = "Done"
    failed = "Failed"


class IdeaStatus(str, Enum):
    new = "New"
    approved = "Approved"
    skipped = "Skipped"
    draft = "Draft"
    published = "Published"


class PostType(str, Enum):
    cta_post = "CTA Post"
    hot_take = "Hot Take"
    system_reveal = "System Reveal"
    feature_drop = "Feature Drop"
    trend_post = "Trend Post"
    story = "Story"


class TopicCluster(str, Enum):
    sales_outbound = "sales-outbound"
    marketing_content = "marketing-content"
    gtm_engineer = "gtm-engineer"
    new_tools = "new-tools"
    systems_playbooks = "systems-playbooks"


class Effort(str, Enum):
    quick_edit = "Quick Edit"
    medium = "Medium"
    heavy = "Heavy"


class Platform(str, Enum):
    linkedin = "LinkedIn"
    x = "X"


# ---------------------------------------------------------------------------
# Raw Post
# ---------------------------------------------------------------------------

class RawPost(BaseModel):
    post_id: str
    author_name: str
    author_url: str
    post_url: str
    post_text: str
    reactions: int = 0
    comments: int = 0
    posted_at: Optional[str] = None
    scraped_at: Optional[str] = None
    score: Optional[float] = None
    topic_cluster: Optional[TopicCluster] = None
    fast_lane: bool = False
    batch_id: Optional[str] = None


class RawPostCreate(BaseModel):
    author_name: str
    author_url: str
    post_url: str
    post_text: str
    reactions: int = 0
    comments: int = 0
    posted_at: Optional[str] = None
    batch_id: Optional[str] = None


class RawPostResponse(BaseModel):
    id: str
    fields: dict[str, Any]


# ---------------------------------------------------------------------------
# Generated Idea
# ---------------------------------------------------------------------------

class IdeaVariation(BaseModel):
    hook: str
    outline: str
    post_type: PostType
    topic_cluster: TopicCluster
    effort: Effort
    cta_word: str


class GeneratedIdea(BaseModel):
    idea_id: Optional[str] = None
    hook: str
    outline: str
    post_type: PostType
    topic_cluster: TopicCluster
    effort: Effort
    cta_word: str
    source_post_id: str
    source_reactions: int = 0
    source_author: str
    status: IdeaStatus = IdeaStatus.new
    generated_draft: Optional[str] = None
    dima_notes: Optional[str] = None
    batch_id: Optional[str] = None
    created_at: Optional[str] = None


class IdeaStatusUpdate(BaseModel):
    status: IdeaStatus


class IdeaDraftUpdate(BaseModel):
    draft: str
    notes: Optional[str] = None


class IdeaFilterParams(BaseModel):
    status: Optional[IdeaStatus] = None
    post_type: Optional[PostType] = None
    topic_cluster: Optional[TopicCluster] = None
    effort: Optional[Effort] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class RunCreate(BaseModel):
    run_id: str
    triggered_at: str
    status: RunStatus = RunStatus.running
    posts_discovered: int = 0
    ideas_generated: int = 0
    fast_lane_count: int = 0
    notes: Optional[str] = None


class RunUpdate(BaseModel):
    status: Optional[RunStatus] = None
    posts_discovered: Optional[int] = None
    ideas_generated: Optional[int] = None
    fast_lane_count: Optional[int] = None
    notes: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    triggered_at: str
    status: RunStatus
    posts_discovered: int
    ideas_generated: int
    fast_lane_count: int
    apify_compute_units: float = 0.0
    run_index: int = 0
    queries_run: Optional[str] = None   # JSON-encoded list
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Published Post
# ---------------------------------------------------------------------------

class PublishedPost(BaseModel):
    post_id: Optional[str] = None
    final_text: str
    platform: Platform = Platform.linkedin
    posted_at: Optional[str] = None
    reactions: int = 0
    comments: int = 0
    idea_id: Optional[str] = None
    performance_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Pipeline State (LangGraph)
# ---------------------------------------------------------------------------

class PipelineState(BaseModel):
    run_id: str
    status: RunStatus = RunStatus.running
    raw_posts: list[dict[str, Any]] = Field(default_factory=list)
    deduped_posts: list[dict[str, Any]] = Field(default_factory=list)
    scored_posts: list[dict[str, Any]] = Field(default_factory=list)
    selected_posts: list[dict[str, Any]] = Field(default_factory=list)
    ideas: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None
    posts_discovered: int = 0
    ideas_generated: int = 0
    fast_lane_count: int = 0


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------

class TriggerRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class GeneratePostRequest(BaseModel):
    regenerate: bool = False


class GeneratePostResponse(BaseModel):
    idea_id: str
    generated_draft: str


class ConfigResponse(BaseModel):
    monitored_profiles: list[dict[str, str]]
    search_queries: list[str]             # full keyword list (14 total)
    next_run_queries: list[str]           # queries active for next run (7)
    next_run_index: int
    queries_per_run: int
    topic_clusters: list[str]
    discovery_strategy: dict[str, Any]
    cost_estimate: dict[str, str]


class HealthResponse(BaseModel):
    status: str
    version: str
    airtable_connected: bool
    timestamp: str
