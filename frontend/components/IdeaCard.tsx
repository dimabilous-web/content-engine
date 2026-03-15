'use client';

import { useState } from 'react';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { CheckCircle, SkipForward, FileText, Loader2, Zap, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';
import { generatePost, updateIdeaStatus, type Idea, type IdeaStatus } from '@/lib/api';
import { cn } from '@/lib/utils';

interface IdeaCardProps {
  idea: Idea;
  onStatusChange?: (id: string, status: IdeaStatus) => void;
}

const postTypeColors: Record<string, string> = {
  'CTA Post':      'bg-purple-500/20 text-purple-300 border-purple-500/30',
  'Hot Take':      'bg-red-500/20 text-red-300 border-red-500/30',
  'System Reveal': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  'Feature Drop':  'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  'Trend Post':    'bg-orange-500/20 text-orange-300 border-orange-500/30',
  'Story':         'bg-pink-500/20 text-pink-300 border-pink-500/30',
};

const effortColors: Record<string, string> = {
  'Quick Edit': 'bg-green-500/20 text-green-300 border-green-500/30',
  'Medium':     'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  'Heavy':      'bg-red-500/20 text-red-300 border-red-500/30',
};

export function IdeaCard({ idea, onStatusChange }: IdeaCardProps) {
  const [generating, setGenerating] = useState(false);
  const [draft, setDraft] = useState(idea.generated_draft || '');
  const [showDraft, setShowDraft] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [currentStatus, setCurrentStatus] = useState<IdeaStatus>(idea.status);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const { generated_draft } = await generatePost(idea.idea_id);
      setDraft(generated_draft);
      setShowDraft(true);
    } catch (e) {
      console.error('Generate failed', e);
    } finally {
      setGenerating(false);
    }
  };

  const handleStatus = async (status: IdeaStatus) => {
    setUpdatingStatus(true);
    try {
      await updateIdeaStatus(idea.idea_id, status);
      setCurrentStatus(status);
      onStatusChange?.(idea.idea_id, status);
    } catch (e) {
      console.error('Status update failed', e);
    } finally {
      setUpdatingStatus(false);
    }
  };

  return (
    <Card className={cn(
      'flex flex-col h-full transition-all hover:shadow-lg',
      idea.fast_lane && 'border-yellow-500/50',
      currentStatus === 'Approved' && 'border-green-500/30',
      currentStatus === 'Skipped' && 'opacity-60',
    )}>
      <CardContent className="flex-1 pt-4 pb-3 space-y-3">
        {/* Fast lane banner */}
        {idea.fast_lane && (
          <div className="flex items-center gap-1 text-xs text-yellow-400 font-medium">
            <Zap className="w-3.5 h-3.5" /> Breaking news
          </div>
        )}

        {/* Post type + effort badges */}
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="outline" className={cn('text-xs', postTypeColors[idea.post_type] || '')}>
            {idea.post_type}
          </Badge>
          <Badge variant="outline" className={cn('text-xs', effortColors[idea.effort] || '')}>
            {idea.effort}
          </Badge>
          {currentStatus !== 'New' && (
            <Badge variant="outline" className="text-xs bg-muted text-muted-foreground">
              {currentStatus}
            </Badge>
          )}
        </div>

        {/* Hook — the star */}
        <Link href={`/ideas/${idea.idea_id}`} className="block group">
          <p className="font-semibold text-sm leading-snug group-hover:text-primary transition-colors line-clamp-4">
            {idea.hook}
          </p>
        </Link>

        {/* Topic cluster + score */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
            {idea.topic_cluster}
          </span>
          {idea.score !== undefined && (
            <span className="text-xs text-muted-foreground">Score: {idea.score}</span>
          )}
        </div>

        {/* Source */}
        <p className="text-xs text-muted-foreground">
          {idea.source_author}
          {idea.source_reactions > 0 && (
            <span className="ml-1 text-orange-400">• {idea.source_reactions.toLocaleString()} reactions</span>
          )}
        </p>

        {/* Generated draft (collapsed/expanded) */}
        {draft && (
          <div>
            <Separator className="my-2" />
            <button
              onClick={() => setShowDraft(!showDraft)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors w-full text-left"
            >
              {showDraft ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {showDraft ? 'Hide draft' : 'Show generated draft'}
            </button>
            {showDraft && (
              <div className="mt-2 p-3 bg-muted rounded-md">
                <p className="text-xs text-foreground whitespace-pre-wrap leading-relaxed line-clamp-6">{draft}</p>
                <Link href={`/ideas/${idea.idea_id}`} className="text-xs text-primary mt-2 block hover:underline">
                  Open full editor →
                </Link>
              </div>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-0 pb-4 flex flex-col gap-2">
        {/* Generate button */}
        <Button
          size="sm"
          variant={draft ? 'outline' : 'default'}
          className="w-full gap-2"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
          {generating ? 'Generating...' : draft ? 'Regenerate' : 'Generate Post'}
        </Button>

        {/* Status buttons */}
        <div className="flex gap-2 w-full">
          <Button
            size="sm"
            variant={currentStatus === 'Approved' ? 'default' : 'outline'}
            className={cn('flex-1 gap-1 text-xs', currentStatus === 'Approved' && 'bg-green-600 hover:bg-green-700')}
            onClick={() => handleStatus('Approved')}
            disabled={updatingStatus || currentStatus === 'Approved'}
          >
            <CheckCircle className="w-3.5 h-3.5" /> Approve
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 gap-1 text-xs"
            onClick={() => handleStatus('Skipped')}
            disabled={updatingStatus || currentStatus === 'Skipped'}
          >
            <SkipForward className="w-3.5 h-3.5" /> Skip
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="flex-1 gap-1 text-xs"
            onClick={() => handleStatus('Draft')}
            disabled={updatingStatus || currentStatus === 'Draft'}
          >
            <FileText className="w-3.5 h-3.5" /> Draft
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
}
