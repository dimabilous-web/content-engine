'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/ideas', label: 'Ideas' },
  { href: '/drafts', label: 'Drafts' },
  { href: '/config', label: 'Config' },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-border bg-card sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-8">
        <Link href="/" className="flex items-center gap-2 font-bold text-lg">
          <Zap className="w-5 h-5 text-yellow-400" />
          <span>Content Engine</span>
        </Link>
        <nav className="flex gap-1">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                'px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                pathname === link.href
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-accent'
              )}
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
