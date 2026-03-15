const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ────────────────────────────────────────────────────────────────────

export type RunStatus = 'Running' | 'Done' | 'Failed';
export type IdeaStatus = 'New' | 'Approved' | 'Skipped' | 'Draft' | 'Published';
export type PostType = 'CTA Post' | 'Hot Take' | 'System Reveal' | 'Feature Drop' | 'Trend Post' | 'Story';
export type TopicCluster = 'sales-outbound' | 'marketing-content' | 'gtm-engineer' | 'new-tools' | 'systems-playbooks';
export type EffortLevel = 'Quick Edit' | 'Medium' | 'Heavy';

export interface Run {
  run_id: string;
  triggered_at: string;
  status: RunStatus;
  posts_discovered: number;
  ideas_generated: number;
  fast_lane_count: number;
  notes?: string;
}

export interface Idea {
  idea_id: string;
  hook: string;
  outline: string;
  post_type: PostType;
  topic_cluster: TopicCluster;
  effort: EffortLevel;
  cta_word?: string;
  source_post_id?: string;
  source_reactions: number;
  source_author: string;
  status: IdeaStatus;
  generated_draft?: string;
  dima_notes?: string;
  batch_id?: string;
  created_at: string;
  fast_lane?: boolean;
  score?: number;
}

export interface Config {
  profiles: Array<{
    name: string;
    handle: string;
    why: string;
  }>;
  search_queries: string[];
  schedule_note: string;
}

export interface Stats {
  ideas_new: number;
  ideas_approved: number;
  published_this_week: number;
  has_fast_lane: boolean;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Runs ─────────────────────────────────────────────────────────────────────

export async function getRuns(): Promise<Run[]> {
  return apiFetch<Run[]>('/runs');
}

export async function getRunStatus(runId: string): Promise<Run> {
  return apiFetch<Run>(`/run/${runId}/status`);
}

export async function triggerRun(): Promise<{ run_id: string }> {
  return apiFetch<{ run_id: string }>('/run/trigger', { method: 'POST' });
}

// ── Ideas ────────────────────────────────────────────────────────────────────

export interface IdeasFilters {
  status?: IdeaStatus;
  post_type?: PostType;
  topic_cluster?: TopicCluster;
  effort?: EffortLevel;
  page?: number;
  limit?: number;
}

export async function getIdeas(filters: IdeasFilters = {}): Promise<{ ideas: Idea[]; total: number }> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.post_type) params.set('post_type', filters.post_type);
  if (filters.topic_cluster) params.set('topic_cluster', filters.topic_cluster);
  if (filters.effort) params.set('effort', filters.effort);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.limit) params.set('limit', String(filters.limit));
  const qs = params.toString();
  return apiFetch<{ ideas: Idea[]; total: number }>(`/ideas${qs ? `?${qs}` : ''}`);
}

export async function getIdea(id: string): Promise<Idea> {
  return apiFetch<Idea>(`/ideas/${id}`);
}

export async function generatePost(id: string): Promise<{ generated_draft: string }> {
  return apiFetch<{ generated_draft: string }>(`/ideas/${id}/generate`, { method: 'POST' });
}

export async function updateIdeaStatus(id: string, status: IdeaStatus): Promise<Idea> {
  return apiFetch<Idea>(`/ideas/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export async function saveDraft(id: string, text: string): Promise<Idea> {
  return apiFetch<Idea>(`/ideas/${id}/draft`, {
    method: 'PATCH',
    body: JSON.stringify({ generated_draft: text }),
  });
}

// ── Config ───────────────────────────────────────────────────────────────────

export async function getConfig(): Promise<Config> {
  return apiFetch<Config>('/config');
}

// ── Stats (derived from ideas + runs) ────────────────────────────────────────

export async function getStats(): Promise<Stats> {
  return apiFetch<Stats>('/stats');
}
