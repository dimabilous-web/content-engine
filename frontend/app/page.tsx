'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Zap, Inbox, CheckCircle, Send } from 'lucide-react';
import { RunStatus, RecentRunsTable } from '@/components/RunStatus';
import { getRuns, getStats, type Run, type Stats } from '@/lib/api';

export default function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [stats, setStats] = useState<Stats>({ ideas_new: 0, ideas_approved: 0, published_this_week: 0, has_fast_lane: false });
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [runsData, statsData] = await Promise.allSettled([
        getRuns(),
        getStats(),
      ]);

      if (runsData.status === 'fulfilled') setRuns(runsData.value.slice(0, 10));
      if (statsData.status === 'fulfilled') setStats(statsData.value);
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
                <p className="text-2xl font-bold">{loading ? '—' : stats.published_this_week}</p>
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
