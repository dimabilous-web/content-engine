'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, FileText, CheckCircle, SkipForward, ExternalLink } from 'lucide-react';
import { getIdeas, updateIdeaStatus, type Idea, type IdeaStatus } from '@/lib/api';
import { cn } from '@/lib/utils';

const postTypeColors: Record<string, string> = {
  'CTA Post':      'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'Hot Take':      'bg-red-500/20 text-red-300 border-red-500/30',
  'System Reveal': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'Feature Drop':  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'Trend Post':    'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'Story':         'bg-pink-500/20 text-pink-300 border-pink-500/30',
};

const statusColors: Record<string, string> = {
  'Draft':    'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  'Approved': 'bg-green-500/20 text-green-300 border-green-500/30',
};

export default function DraftsPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDrafts = useCallback(async () => {
    setLoading(true);
    try {
      const [drafts, approved] = await Promise.all([
        getIdeas({ status: 'Draft', limit: 100 }),
        getIdeas({ status: 'Approved', limit: 100 }),
      ]);
      const combined = [...drafts.ideas, ...approved.ideas].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setIdeas(combined);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load drafts');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDrafts();
  }, [loadDrafts]);

  const handleStatus = async (id: string, status: IdeaStatus) => {
    try {
      await updateIdeaStatus(id, status);
      setIdeas((prev) => prev.map((i) => (i.idea_id === id ? { ...i, status } : i)));
    } catch {
      // ignore
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Drafts & Approved</h1>
        <p className="text-muted-foreground text-sm mt-1">
          {ideas.length > 0 ? `${ideas.length} item${ideas.length !== 1 ? 's' : ''}` : 'Nothing here yet'}
        </p>
      </div>

      {error && (
        <Alert className="border-red-500/50 bg-red-500/10">
          <AlertDescription className="text-red-300">{error}</AlertDescription>
        </Alert>
      )}

      {ideas.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <div className="text-5xl mb-4">📝</div>
          <h2 className="text-xl font-semibold mb-2">No drafts yet</h2>
          <p className="text-muted-foreground text-sm max-w-md">
            Generate a post on an idea and save it as a draft. It'll show up here ready to polish and publish.
          </p>
          <Link href="/ideas" className="mt-4">
            <Button variant="outline" size="sm">Browse Ideas</Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {ideas.map((idea) => (
            <Card key={idea.idea_id} className="hover:border-border/80 transition-colors">
              <CardContent className="py-4">
                <div className="flex items-start gap-4">
                  {/* Icon */}
                  <div className="p-2 bg-muted rounded-lg mt-0.5 shrink-0">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                  </div>

                  {/* Main content */}
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex flex-wrap gap-1.5 items-center">
                      <Badge variant="outline" className={cn('text-xs', postTypeColors[idea.post_type] || '')}>
                        {idea.post_type}
                      </Badge>
                      <Badge variant="outline" className={cn('text-xs', statusColors[idea.status] || '')}>
                        {idea.status}
                      </Badge>
                      <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                        {idea.topic_cluster}
                      </span>
                    </div>

                    <Link href={`/ideas/${idea.idea_id}`} className="block group">
                      <p className="font-medium text-sm leading-snug group-hover:text-primary transition-colors line-clamp-2">
                        {idea.hook}
                      </p>
                    </Link>

                    <p className="text-xs text-muted-foreground">
                      {formatDate(idea.created_at)}
                      {idea.source_author && <span className="ml-2">· {idea.source_author}</span>}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 shrink-0">
                    <Link href={`/ideas/${idea.idea_id}`}>
                      <Button size="sm" variant="outline" className="gap-1 text-xs">
                        <ExternalLink className="w-3.5 h-3.5" /> Edit
                      </Button>
                    </Link>
                    {idea.status !== 'Approved' && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1 text-xs text-green-400 hover:text-green-300"
                        onClick={() => handleStatus(idea.idea_id, 'Approved')}
                      >
                        <CheckCircle className="w-3.5 h-3.5" /> Approve
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="gap-1 text-xs text-muted-foreground"
                      onClick={() => handleStatus(idea.idea_id, 'Published')}
                    >
                      <SkipForward className="w-3.5 h-3.5" /> Publish
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}
