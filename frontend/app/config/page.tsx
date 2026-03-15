'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, User, Search, Clock, Info } from 'lucide-react';
import { getConfig, type Config } from '@/lib/api';

// Fallback config (matches the architecture spec)
const FALLBACK_CONFIG: Config = {
  profiles: [
    { name: 'Manthan', handle: 'leadgenmanthan', why: 'Lead gen, AI outbound' },
    { name: 'Nick Saraev', handle: 'nick-saraev', why: 'AI automation, agency' },
    { name: 'Alex Vacca', handle: 'alex-vacca', why: 'ColdIQ founder, GTM/outbound' },
    { name: 'Charlie Hills', handle: 'charlie-hills', why: 'AI GTM content' },
    { name: 'Suleiman Najim', handle: 'suleiman-najim-87457a211', why: 'AI agents, B2B' },
    { name: 'Luke Pierce', handle: 'luke-pierce-boom-automations', why: 'Automation, agency ops' },
  ],
  search_queries: [
    'AI agents sales outbound',
    'GTM engineer AI',
    'signal based outreach',
    'replace SDR AI agent',
    'AI marketing automation',
    'MCP server Claude',
    'LangGraph agent',
    'revenue automation AI',
    'cold outreach dead',
    'AI lead generation 2026',
  ],
  schedule_note: 'Runs weekly by default. Use Run Now to trigger manually.',
};

export default function ConfigPage() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch(() => setConfig(FALLBACK_CONFIG))
      .finally(() => setLoading(false));
  }, []);

  const data = config || FALLBACK_CONFIG;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Config</h1>
        <p className="text-muted-foreground text-sm mt-1">Pipeline configuration — read only for now</p>
      </div>

      {/* Schedule note */}
      <Alert className="border-blue-500/30 bg-blue-500/5">
        <Clock className="w-4 h-4 text-blue-400" />
        <AlertDescription className="text-blue-300">
          {data.schedule_note}
        </AlertDescription>
      </Alert>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Monitored profiles */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <User className="w-4 h-4 text-muted-foreground" />
                Monitored Profiles
                <Badge variant="secondary" className="ml-auto text-xs">{data.profiles.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.profiles.map((profile) => (
                <div key={profile.handle} className="flex items-start justify-between gap-3 p-3 bg-muted/50 rounded-lg">
                  <div>
                    <p className="font-medium text-sm">{profile.name}</p>
                    <p className="text-xs text-muted-foreground font-mono mt-0.5">{profile.handle}</p>
                  </div>
                  <span className="text-xs text-muted-foreground text-right shrink-0 max-w-[40%]">{profile.why}</span>
                </div>
              ))}
              <div className="flex items-center gap-2 pt-1">
                <Info className="w-3.5 h-3.5 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">Scraped every 7 days. Posts from the last 14 days.</p>
              </div>
            </CardContent>
          </Card>

          {/* Search queries */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Search className="w-4 h-4 text-muted-foreground" />
                Keyword Search Queries
                <Badge variant="secondary" className="ml-auto text-xs">{data.search_queries.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.search_queries.map((query) => (
                <div key={query} className="flex items-center gap-2 p-2.5 bg-muted/50 rounded-lg">
                  <Search className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                  <p className="text-sm">{query}</p>
                </div>
              ))}
              <div className="flex items-center gap-2 pt-1">
                <Info className="w-3.5 h-3.5 text-muted-foreground" />
                <p className="text-xs text-muted-foreground">Filter: 100+ reactions OR 50+ comments in last 14 days.</p>
              </div>
            </CardContent>
          </Card>

          {/* Topic clusters */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Topic Clusters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {[
                  { label: 'sales-outbound', desc: 'AI agents for outbound, signal-based, SDR replacement' },
                  { label: 'marketing-content', desc: 'Content systems, competitor monitoring, repurposing' },
                  { label: 'gtm-engineer', desc: 'New roles, future of sales, RevOps' },
                  { label: 'new-tools', desc: 'MCP servers, new model releases, feature drops' },
                  { label: 'systems-playbooks', desc: 'Giveaways, frameworks, case studies' },
                ].map((cluster) => (
                  <div key={cluster.label} className="flex-1 min-w-[200px] p-3 bg-muted/50 rounded-lg">
                    <Badge variant="outline" className="text-xs mb-1.5">{cluster.label}</Badge>
                    <p className="text-xs text-muted-foreground">{cluster.desc}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
