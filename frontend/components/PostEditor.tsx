'use client';

import { useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { ArrowLeft, RefreshCw, Copy, Save, CheckCircle, Loader2, Zap } from 'lucide-react';
import Link from 'next/link';
import { generatePost, updateIdeaStatus, saveDraft, type Idea } from '@/lib/api';
import { cn } from '@/lib/utils';

const postTypeColors: Record<string, string> = {
  'CTA Post':      'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'Hot Take':      'bg-red-500/20 text-red-300 border-red-500/30',
  'System Reveal': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'Feature Drop':  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'Trend Post':    'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'Story':         'bg-pink-500/20 text-pink-300 border-pink-500/30',
};

interface PostEditorProps {
  idea: Idea;
}

export function PostEditor({ idea }: PostEditorProps) {
  const [draft, setDraft] = useState(idea.generated_draft || '');
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [currentStatus, setCurrentStatus] = useState(idea.status);

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setErrorMsg(null);
    try {
      const { generated_draft } = await generatePost(idea.idea_id);
      setDraft(generated_draft);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = useCallback(async () => {
    if (!draft) return;
    await navigator.clipboard.writeText(draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [draft]);

  const handleSaveDraft = async () => {
    setSaving(true);
    setErrorMsg(null);
    try {
      await saveDraft(idea.idea_id, draft);
      await updateIdeaStatus(idea.idea_id, 'Draft');
      setCurrentStatus('Draft');
      showSuccess('Draft saved.');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleMarkPublished = async () => {
    setSaving(true);
    setErrorMsg(null);
    try {
      await saveDraft(idea.idea_id, draft);
      await updateIdeaStatus(idea.idea_id, 'Published');
      setCurrentStatus('Published');
      showSuccess('Marked as published! 🎉');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center justify-between">
        <Link href="/ideas" className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="w-4 h-4" /> Back to Ideas
        </Link>
        <Badge variant="outline" className="text-xs">{currentStatus}</Badge>
      </div>

      {successMsg && (
        <Alert className="border-green-500/50 bg-green-500/10">
          <CheckCircle className="w-4 h-4 text-green-400" />
          <AlertDescription className="text-green-300">{successMsg}</AlertDescription>
        </Alert>
      )}
      {errorMsg && (
        <Alert className="border-red-500/50 bg-red-500/10">
          <AlertDescription className="text-red-300">{errorMsg}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left panel: idea details */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                Content Brief
                {idea.fast_lane && <span className="text-yellow-400 text-sm flex items-center gap-1"><Zap className="w-3.5 h-3.5" /> Fast Lane</span>}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Badges */}
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="outline" className={cn('text-xs', postTypeColors[idea.post_type] || '')}>
                  {idea.post_type}
                </Badge>
                <Badge variant="outline" className="text-xs bg-muted text-muted-foreground">
                  {idea.topic_cluster}
                </Badge>
                <Badge variant="outline" className="text-xs bg-muted text-muted-foreground">
                  {idea.effort}
                </Badge>
              </div>

              {/* Hook */}
              <div>
                <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wide">Hook</p>
                <p className="font-semibold text-sm leading-snug">{idea.hook}</p>
              </div>

              {/* Outline */}
              {idea.outline && (
                <>
                  <Separator />
                  <div>
                    <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wide">Outline</p>
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">{idea.outline}</p>
                  </div>
                </>
              )}

              {/* Source */}
              <Separator />
              <div>
                <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wide">Source</p>
                <p className="text-sm">
                  {idea.source_author}
                  {idea.source_reactions > 0 && (
                    <span className="ml-1 text-orange-400">• {idea.source_reactions.toLocaleString()} reactions</span>
                  )}
                </p>
              </div>

              {idea.cta_word && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1 uppercase tracking-wide">Suggested CTA Word</p>
                  <code className="text-sm font-mono bg-muted px-2 py-1 rounded">{idea.cta_word}</code>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right panel: editor */}
        <div className="space-y-3">
          <Card className="h-full">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Generated Post</CardTitle>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={handleGenerate} disabled={generating} className="gap-1.5">
                    {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                    {draft ? 'Regenerate' : 'Generate'}
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleCopy} disabled={!draft} className="gap-1.5">
                    <Copy className="w-3.5 h-3.5" />
                    {copied ? 'Copied!' : 'Copy'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {draft ? (
                <Textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  className="min-h-[400px] text-sm leading-relaxed font-mono resize-none"
                  placeholder="Generated post will appear here..."
                />
              ) : (
                <div className="min-h-[400px] flex flex-col items-center justify-center text-center p-8 border border-dashed border-border rounded-lg">
                  <p className="text-muted-foreground text-sm mb-3">No post generated yet.</p>
                  <Button onClick={handleGenerate} disabled={generating} className="gap-2">
                    {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    {generating ? 'Generating...' : 'Generate Post'}
                  </Button>
                </div>
              )}

              {draft && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleSaveDraft}
                    disabled={saving}
                    className="flex-1 gap-1.5"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    Save Draft
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleMarkPublished}
                    disabled={saving || currentStatus === 'Published'}
                    className="flex-1 gap-1.5 bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    {currentStatus === 'Published' ? 'Published ✓' : 'Mark Published'}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
