'use client';

import { useEffect, useState } from 'react';
import { PostEditor } from '@/components/PostEditor';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { getIdea, type Idea } from '@/lib/api';

interface PageProps {
  params: { id: string };
}

export default function IdeaEditorPage({ params }: PageProps) {
  const [idea, setIdea] = useState<Idea | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIdea(params.id)
      .then(setIdea)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load idea'))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !idea) {
    return (
      <Alert className="border-red-500/50 bg-red-500/10">
        <AlertDescription className="text-red-300">{error || 'Idea not found'}</AlertDescription>
      </Alert>
    );
  }

  return <PostEditor idea={idea} />;
}
