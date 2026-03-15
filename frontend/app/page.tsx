'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Zap, Inbox, CheckCircle, Send } from 'lucide-react';
import { RunStatus, RecentRunsTable } from '@/components/RunStatus';
import { getRuns, getIdeas, type Run } from '@/lib/api';

interface Stats {
  ideas_new: number;
  ideas_approved: number;
  published_week: number;
  has_fast_lane: boolean;
}

export default function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [stats, setStats] = useState<Stats>({ ideas_new: 0, ideas_approved: 0, published_week: 0, has_fast_lane: false });
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [runsData, newIdeas, approvedIdeas, publishedIdeas] = await Promise.allSettled([
        getRuns(),
        getIdeas({ status: 'New', limit: 1 }),
        getIdeas({ status: 'Approved', limit: 1 }),
        getIdeas({ status: 'Published', limit: 100 }),
      ]);

      if (runsData.status === 'fulfilled') setRuns(runsData.value.slice(0, 5));

      const newCount = newIdeas.status === 'fulfilled' ? newIdeas.value.total : 0;
      const approvedCount = approvedIdeas.status === 'fulfilled' ? approvedIdeas.value.total : 0;

      // Count published this week
      let publishedWeek = 0;
      let hasFastLane = false;
      if (publishedIdeas.status === 'fulfilled') {
        const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
        publishedWeek = publishedIdeas.value.ideas.filter(
          (i) => new Date(i.created_at).getTime() > weekAgo
        ).length;
      }

      // Check for fast lane in new ideas
      const newFull = await getIdeas({ status: 'New', limit: 50 }).catch(() => ({ ideas: [], total: 0 }));
      hasFastLane = newFull.ideas.some((i) => i.fast_lane);

      setStats({ ideas_new: newCount, ideas_approved: approvedCount, published_week: publishedWeek, has_fast_lane: hasFastLane });
    } catch {
      // gracefully handle API down
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Your LinkedIn Content Engine</p>
      </div>

      {/* Fast lane alert */}
      {stats.has_fast_lane && (
        <Alert className="border-yellow-500/50 bg-yellow-500/10">
          <Zap className="w-4 h-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300 font-medium">
            ⚡ Breaking news ideas available — check the Ideas feed for fast lane content.
          </AlertDescription>
        </Alert>
      )}

      {/* Run status + trigger */}
      <RunStatus onRunComplete={loadData} />

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-5 pb-5">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-500/20 rounded-lg">
                <Inbox className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{loading ? '—' : stats.ideas_new}</p>
                <p className="text-xs text-muted-foreground">Ideas in queue</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 pb-5">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-500/20 rounded-lg">
                <CheckCircle className="w-4 h-4 text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{loading ? '—' : stats.ideas_approved}</p>
                <p className="text-xs text-muted-foreground">Approved</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-5 pb-5">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-500/20 rounded-lg">
                <Send className="w-4 h-4 text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{loading ? '—' : stats.published_week}</p>
                <p className="text-xs text-muted-foreground">Published this week</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent runs */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Recent Runs</CardTitle>
        </CardHeader>
        <CardContent>
          <RecentRunsTable runs={runs} />
        </CardContent>
      </Card>
    </div>
  );
}
