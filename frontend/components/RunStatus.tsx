'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Play, RefreshCw, CheckCircle, XCircle, Loader2, Zap } from 'lucide-react';
import { triggerRun, getRunStatus, getRuns, type Run } from '@/lib/api';

interface RunStatusProps {
  onRunComplete?: () => void;
}

export function RunStatus({ onRunComplete }: RunStatusProps) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRuns = useCallback(async () => {
    try {
      const data = await getRuns();
      setRuns(data);
    } catch {
      // silently ignore if API not up
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Poll active run
  useEffect(() => {
    if (!activeRunId) return;
    const interval = setInterval(async () => {
      try {
        const run = await getRunStatus(activeRunId);
        setActiveRun(run);
        if (run.status !== 'Running') {
          setActiveRunId(null);
          clearInterval(interval);
          loadRuns();
          onRunComplete?.();
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [activeRunId, loadRuns, onRunComplete]);

  const handleTrigger = async () => {
    setTriggering(true);
    setError(null);
    try {
      const { run_id } = await triggerRun();
      setActiveRunId(run_id);
      setActiveRun({ run_id, triggered_at: new Date().toISOString(), status: 'Running', posts_discovered: 0, ideas_generated: 0, fast_lane_count: 0 });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to trigger run');
    } finally {
      setTriggering(false);
    }
  };

  const lastRun = runs[0];
  const isRunning = activeRun?.status === 'Running' || !!activeRunId;

  return (
    <div className="space-y-4">
      {/* Active run alert */}
      {isRunning && activeRun && (
        <Alert className="border-blue-500/50 bg-blue-500/10">
          <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
          <AlertDescription className="text-blue-300">
            Pipeline running... <span className="font-mono text-xs">{activeRun.run_id}</span>
          </AlertDescription>
        </Alert>
      )}

      {activeRun && activeRun.status !== 'Running' && (
        <Alert className={activeRun.status === 'Done' ? 'border-green-500/50 bg-green-500/10' : 'border-red-500/50 bg-red-500/10'}>
          {activeRun.status === 'Done' ? <CheckCircle className="w-4 h-4 text-green-400" /> : <XCircle className="w-4 h-4 text-red-400" />}
          <AlertDescription className={activeRun.status === 'Done' ? 'text-green-300' : 'text-red-300'}>
            {activeRun.status === 'Done'
              ? `Run complete. ${activeRun.posts_discovered} posts discovered, ${activeRun.ideas_generated} ideas generated.${activeRun.fast_lane_count > 0 ? ` ⚡ ${activeRun.fast_lane_count} fast lane items.` : ''}`
              : `Run failed. ${activeRun.notes || 'Check logs.'}`}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert className="border-red-500/50 bg-red-500/10">
          <XCircle className="w-4 h-4 text-red-400" />
          <AlertDescription className="text-red-300">{error}</AlertDescription>
        </Alert>
      )}

      {/* Last run card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Last Run</CardTitle>
          <Button
            size="sm"
            onClick={handleTrigger}
            disabled={triggering || isRunning}
            className="gap-2"
          >
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'Running...' : 'Run Now'}
          </Button>
        </CardHeader>
        <CardContent>
          {lastRun ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Status</p>
                <StatusBadge status={lastRun.status} />
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">When</p>
                <p className="text-sm font-medium">{formatDate(lastRun.triggered_at)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Posts Found</p>
                <p className="text-sm font-medium">{lastRun.posts_discovered}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Ideas Generated</p>
                <p className="text-sm font-medium">{lastRun.ideas_generated}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No runs yet. Hit Run Now to start.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export function StatusBadge({ status }: { status: Run['status'] }) {
  if (status === 'Done') return <Badge className="bg-green-500/20 text-green-400 border-green-500/30"><CheckCircle className="w-3 h-3 mr-1" />Done</Badge>;
  if (status === 'Running') return <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30"><Loader2 className="w-3 h-3 mr-1 animate-spin" />Running</Badge>;
  return <Badge className="bg-red-500/20 text-red-400 border-red-500/30"><XCircle className="w-3 h-3 mr-1" />Failed</Badge>;
}

export function RecentRunsTable({ runs }: { runs: Run[] }) {
  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">No runs yet.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground text-xs">
            <th className="text-left pb-2 font-medium">Run ID</th>
            <th className="text-left pb-2 font-medium">Date</th>
            <th className="text-left pb-2 font-medium">Status</th>
            <th className="text-right pb-2 font-medium">Posts</th>
            <th className="text-right pb-2 font-medium">Ideas</th>
            <th className="text-right pb-2 font-medium">Fast Lane</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {runs.map((run) => (
            <tr key={run.run_id} className="hover:bg-accent/50 transition-colors">
              <td className="py-2 font-mono text-xs text-muted-foreground">{run.run_id.slice(0, 12)}...</td>
              <td className="py-2">{formatDate(run.triggered_at)}</td>
              <td className="py-2"><StatusBadge status={run.status} /></td>
              <td className="py-2 text-right">{run.posts_discovered}</td>
              <td className="py-2 text-right">{run.ideas_generated}</td>
              <td className="py-2 text-right">
                {run.fast_lane_count > 0 ? (
                  <span className="text-yellow-400">⚡ {run.fast_lane_count}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(dateStr: string) {
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return dateStr;
  }
}
