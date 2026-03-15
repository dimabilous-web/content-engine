'use client';

import { useState, useEffect, useCallback } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { FilterBar, type FilterValues } from '@/components/FilterBar';
import { IdeaCard } from '@/components/IdeaCard';
import { Zap, ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import { getIdeas, type Idea, type IdeaStatus } from '@/lib/api';

const PAGE_SIZE = 12;

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterValues>({ sort: 'score' });
  const [hasFastLane, setHasFastLane] = useState(false);

  const loadIdeas = useCallback(async (f: FilterValues, p: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIdeas({
        status: (f.status as IdeaStatus) || undefined,
        post_type: f.post_type as any || undefined,
        topic_cluster: f.topic_cluster as any || undefined,
        effort: f.effort as any || undefined,
        page: p,
        limit: PAGE_SIZE,
      });
      setIdeas(data.ideas);
      setTotal(data.total);
      setHasFastLane(data.ideas.some((i) => i.fast_lane));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load ideas');
      setIdeas([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadIdeas(filters, page);
  }, [filters, page, loadIdeas]);

  const handleFilterChange = (f: FilterValues) => {
    setFilters(f);
    setPage(1);
  };

  const handleStatusChange = (id: string, status: IdeaStatus) => {
    setIdeas((prev) => prev.map((i) => (i.idea_id === id ? { ...i, status } : i)));
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Sort ideas client-side based on sort filter
  const sortedIdeas = [...ideas].sort((a, b) => {
    if (filters.sort === 'recency') return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    if (filters.sort === 'engagement') return (b.source_reactions || 0) - (a.source_reactions || 0);
    return (b.score || 0) - (a.score || 0); // default: score
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Ideas Feed</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {total > 0 ? `${total} idea${total !== 1 ? 's' : ''}` : 'No ideas yet'} — click a card to open the full editor
        </p>
      </div>

      {hasFastLane && (
        <Alert className="border-yellow-500/50 bg-yellow-500/10">
          <Zap className="w-4 h-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300 font-medium">
            ⚡ Breaking news ideas available in this batch. Act fast.
          </AlertDescription>
        </Alert>
      )}

      <FilterBar values={filters} onChange={handleFilterChange} />

      {error && (
        <Alert className="border-red-500/50 bg-red-500/10">
          <AlertDescription className="text-red-300">{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : sortedIdeas.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="text-5xl mb-4">💡</div>
          <h2 className="text-xl font-semibold mb-2">No ideas yet</h2>
          <p className="text-muted-foreground text-sm max-w-md">
            Run the pipeline to get your first batch of ideas. Head to the Dashboard and hit "Run Now".
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {sortedIdeas.map((idea) => (
              <IdeaCard key={idea.idea_id} idea={idea} onStatusChange={handleStatusChange} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="gap-1"
              >
                <ChevronLeft className="w-4 h-4" /> Prev
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="gap-1"
              >
                Next <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
