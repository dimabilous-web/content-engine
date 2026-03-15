'use client';

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import type { IdeaStatus, PostType, TopicCluster, EffortLevel } from '@/lib/api';

export interface FilterValues {
  status?: IdeaStatus | '';
  post_type?: PostType | '';
  topic_cluster?: TopicCluster | '';
  effort?: EffortLevel | '';
  sort?: 'score' | 'recency' | 'engagement';
}

interface FilterBarProps {
  values: FilterValues;
  onChange: (values: FilterValues) => void;
}

export function FilterBar({ values, onChange }: FilterBarProps) {
  const set = (key: keyof FilterValues, val: string) => {
    onChange({ ...values, [key]: val === 'all' ? '' : val });
  };

  const hasFilters = values.status || values.post_type || values.topic_cluster || values.effort;

  const clear = () => onChange({ sort: values.sort });

  return (
    <div className="flex flex-wrap gap-2 items-center">
      <Select value={values.status || 'all'} onValueChange={(v) => set('status', v as string)}>
        <SelectTrigger className="w-36 h-9 text-sm">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Statuses</SelectItem>
          <SelectItem value="New">New</SelectItem>
          <SelectItem value="Approved">Approved</SelectItem>
          <SelectItem value="Draft">Draft</SelectItem>
          <SelectItem value="Skipped">Skipped</SelectItem>
          <SelectItem value="Published">Published</SelectItem>
        </SelectContent>
      </Select>

      <Select value={values.post_type || 'all'} onValueChange={(v) => set('post_type', v as string)}>
        <SelectTrigger className="w-40 h-9 text-sm">
          <SelectValue placeholder="Post Type" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Types</SelectItem>
          <SelectItem value="CTA Post">CTA Post</SelectItem>
          <SelectItem value="Hot Take">Hot Take</SelectItem>
          <SelectItem value="System Reveal">System Reveal</SelectItem>
          <SelectItem value="Feature Drop">Feature Drop</SelectItem>
          <SelectItem value="Trend Post">Trend Post</SelectItem>
          <SelectItem value="Story">Story</SelectItem>
        </SelectContent>
      </Select>

      <Select value={values.topic_cluster || 'all'} onValueChange={(v) => set('topic_cluster', v as string)}>
        <SelectTrigger className="w-44 h-9 text-sm">
          <SelectValue placeholder="Topic" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Topics</SelectItem>
          <SelectItem value="sales-outbound">Sales Outbound</SelectItem>
          <SelectItem value="marketing-content">Marketing Content</SelectItem>
          <SelectItem value="gtm-engineer">GTM Engineer</SelectItem>
          <SelectItem value="new-tools">New Tools</SelectItem>
          <SelectItem value="systems-playbooks">Systems & Playbooks</SelectItem>
        </SelectContent>
      </Select>

      <Select value={values.effort || 'all'} onValueChange={(v) => set('effort', v as string)}>
        <SelectTrigger className="w-36 h-9 text-sm">
          <SelectValue placeholder="Effort" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Effort</SelectItem>
          <SelectItem value="Quick Edit">Quick Edit</SelectItem>
          <SelectItem value="Medium">Medium</SelectItem>
          <SelectItem value="Heavy">Heavy</SelectItem>
        </SelectContent>
      </Select>

      <Select value={values.sort || 'score'} onValueChange={(v) => set('sort', v as string)}>
        <SelectTrigger className="w-40 h-9 text-sm">
          <SelectValue placeholder="Sort by" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="score">Sort: Score</SelectItem>
          <SelectItem value="recency">Sort: Recency</SelectItem>
          <SelectItem value="engagement">Sort: Engagement</SelectItem>
        </SelectContent>
      </Select>

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={clear} className="gap-1 h-9 text-muted-foreground">
          <X className="w-3.5 h-3.5" /> Clear
        </Button>
      )}
    </div>
  );
}
