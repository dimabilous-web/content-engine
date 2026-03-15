# Content Engine — Frontend Dashboard

Dima's personal LinkedIn Content Engine. Clean, minimal Next.js 14 dashboard.

## Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui components
- SWR via `swr`

## Setup

```bash
npm install
cp .env.local.example .env.local
# Edit .env.local and set NEXT_PUBLIC_API_URL to your Railway backend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — last run, stats, fast lane alert, run trigger |
| `/ideas` | Ideas feed — browse, filter, generate, approve |
| `/ideas/[id]` | Post editor — generate, tweak, copy, save, publish |
| `/drafts` | All drafts + approved ideas |
| `/config` | Config overview (monitored profiles, keywords) |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Backend FastAPI base URL | `http://localhost:8000` |

## Deploy to Vercel

1. Push to GitHub
2. Import repo in Vercel
3. Set `NEXT_PUBLIC_API_URL` in Vercel environment variables
4. Deploy

## API

All API calls are in `lib/api.ts`. The backend is a FastAPI service (see `../backend/`).
