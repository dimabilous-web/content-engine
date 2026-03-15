# Dima's Personal Content Engine — Architecture Spec
**Version:** 1.0 | **Date:** March 2026 | **Status:** Pre-build

---

## What This Is

A personal content machine for LinkedIn (+ X later) that:
1. Discovers viral posts in Dima's space automatically
2. Scores and surfaces the best ones
3. Generates post ideas using Dima's exact voice, structure, and frameworks
4. Lets Dima pick, generate, tweak, and store — all in one dashboard

This is NOT a fully-automated posting bot. Dima stays in the loop. The system does the discovery and generation grunt work. Dima makes the creative calls.

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Agent Orchestration | LangGraph | Stateful pipeline, retries, conditional routing |
| Backend API | FastAPI | REST endpoints, pipeline triggers |
| Frontend Dashboard | Next.js + shadcn/ui | Clean, minimal, functional |
| LLM | Claude Sonnet 4.6 (Anthropic) | Scoring, idea gen, tone matching |
| Scraping | Apify | LinkedIn scrapers (profiles + keyword search) |
| Database | Airtable | Raw posts, scored posts, generated ideas, drafts |
| Backend Hosting | Railway | FastAPI + LangGraph |
| Frontend Hosting | Vercel | Next.js dashboard |
| Version Control | GitHub | Monorepo: /backend + /frontend |

---

## Discovery Strategy

### Tier 1: Monitored Profiles (High-Signal, Tracked Weekly)
These 6 profiles are scraped every 7 days. Posts from the last 14 days are pulled.

| Profile | Handle | Why Watch |
|---------|--------|-----------|
| Manthan | leadgenmanthan | Lead gen, AI outbound |
| Nick Saraev | nick-saraev | AI automation, agency |
| Alex Vacca | alex-vacca | ColdIQ founder, GTM/outbound |
| Charlie Hills | charlie-hills | AI GTM content |
| Suleiman Najim | suleiman-najim-87457a211 | AI agents, B2B |
| Luke Pierce | luke-pierce-boom-automations | Automation, agency ops |

### Tier 2: Keyword Discovery (Broad Viral Net)
Apify keyword searches across LinkedIn for posts matching Dima's topic pillars. Not tied to specific authors — catches viral posts from anyone. Run weekly.

**Search queries:**
- "AI agents sales outbound"
- "GTM engineer AI"
- "signal based outreach"
- "replace SDR AI agent"
- "AI marketing automation"
- "MCP server Claude"
- "LangGraph agent"
- "revenue automation AI"
- "cold outreach dead"
- "AI lead generation 2026"

**Filter:** 100+ reactions OR 50+ comments in last 14 days

### Tier 3: Breaking News Fast Lane
Separate lightweight agent that monitors:
- Anthropic blog/release notes
- New MCP server announcements
- Product Hunt AI launches
- Twitter/X trending AI tool launches

Posts from breaking news items get a **recency boost** in scoring if < 48h old. This is what keeps Dima always ahead.

---

## LangGraph Pipeline

```
[Trigger: Cron (daily) or Manual]
         ↓
  [Discovery Agent]
  - Tier 1: scrape 6 profiles
  - Tier 2: keyword search
  - Tier 3: breaking news check
         ↓
  [Dedup Agent]
  - Check against Airtable (already seen?)
  - Remove duplicates within batch
         ↓
  [Scoring Agent]
  - Score each post (0-100)
  - Tag topic cluster
  - Flag "fast lane" items
         ↓
  [Top 20 Selection]
  - Take top 20-25 by score
         ↓
  [Transform Agent]
  - Generate 2 idea variations per post
  - Apply Dima's hook patterns + tone rules
  - Output structured idea cards
         ↓
  [Write to Airtable]
  - Raw posts → Posts table
  - Idea cards → Ideas table
  - Run metadata → Runs table
```

---

## Scoring Model

Each post scored 0-100:

| Signal | Weight | Logic |
|--------|--------|-------|
| Topic Relevance | 40% | Claude scores fit to Dima's 5 pillars |
| Engagement | 25% | 100+ reactions = strong; 500+ = max |
| Recency | 20% | < 48h = max boost; > 7 days = discount |
| Quality | 15% | Not an ad, not bot engagement, real insight/takeaway |

**Fast Lane Bonus:** Breaking news items (< 48h) get +20 points added before ranking.

**Topic Cluster Tags:**
- `sales-outbound` — AI agents for outbound, signal-based, SDR replacement
- `marketing-content` — Content systems, competitor monitoring, repurposing
- `gtm-engineer` — New roles, future of sales, RevOps
- `new-tools` — MCP servers, new model releases, feature drops
- `systems-playbooks` — Giveaways, frameworks, case studies

---

## Airtable Schema

### Table 1: Raw Posts
| Field | Type | Notes |
|-------|------|-------|
| post_id | Text | Unique ID (URL hash) |
| author_name | Text | |
| author_url | Text | LinkedIn profile URL |
| post_url | Text | |
| post_text | Long text | Full post content |
| reactions | Number | |
| comments | Number | |
| posted_at | Date | |
| scraped_at | Date | |
| score | Number | 0-100 |
| topic_cluster | Select | sales-outbound / marketing-content / etc |
| fast_lane | Checkbox | Breaking news flag |
| batch_id | Text | Links to Runs table |

### Table 2: Generated Ideas
| Field | Type | Notes |
|-------|------|-------|
| idea_id | Text | |
| hook | Text | Opening line(s) |
| outline | Long text | Full post structure |
| post_type | Select | CTA Post / Hot Take / System Reveal / Feature Drop / Trend Post / Story |
| topic_cluster | Select | |
| effort | Select | Quick Edit / Medium / Heavy |
| cta_word | Text | Suggested CTA word |
| source_post_id | Link | → Raw Posts |
| source_reactions | Number | |
| source_author | Text | |
| status | Select | New / Approved / Skipped / Draft / Published |
| generated_draft | Long text | Full generated post (populated when Dima clicks "Generate") |
| dima_notes | Long text | Editable notes/tweaks |
| batch_id | Text | |
| created_at | Date | |

### Table 3: Runs
| Field | Type | Notes |
|-------|------|-------|
| run_id | Text | |
| triggered_at | Date | |
| status | Select | Running / Done / Failed |
| posts_discovered | Number | |
| ideas_generated | Number | |
| fast_lane_count | Number | Breaking news items |
| notes | Long text | Any errors or flags |

### Table 4: Published Posts
| Field | Type | Notes |
|-------|------|-------|
| post_id | Text | |
| final_text | Long text | What actually got posted |
| platform | Select | LinkedIn / X |
| posted_at | Date | |
| reactions | Number | (manually updated or via future API) |
| comments | Number | |
| idea_id | Link | → Ideas |
| performance_notes | Long text | |

---

## Dashboard (Next.js)

### Page 1: Dashboard Home
- Last run status + timestamp
- "Run Now" button (triggers pipeline manually)
- Quick stats: ideas in queue, approved, published this week
- Fast lane alert banner if breaking news items exist

### Page 2: Ideas Feed
- Card layout, one card per idea
- Each card shows:
  - Hook (big, prominent)
  - Post type tag + topic tag + effort badge
  - Source: author name + reaction count
  - "Generate Post" button → calls API, streams generated post into card
  - Status buttons: ✅ Approve / ⏭ Skip / 📝 Draft
- Filters: post type, topic cluster, effort level, status
- Sort: by score, by recency, by source engagement

### Page 3: Post Editor
- Triggered when Dima clicks "Generate Post" on an idea
- Left: idea card + source post reference
- Right: generated post (editable rich text)
- Regenerate button (get a different version)
- Save as Draft / Mark as Published
- Copy to clipboard button

### Page 4: Drafts & Published
- All saved drafts
- Published post history
- Basic performance tracking (manual entry for now)

### Page 5: Config
- Manage monitored profiles (add/remove)
- Manage keyword searches
- Run schedule settings
- View/edit tone rules (for future fine-tuning)

---

## FastAPI Endpoints

```
POST /run/trigger          - Start a pipeline run
GET  /run/{run_id}/status  - Check run status
GET  /runs                 - List all runs with metadata

GET  /ideas                - Get latest batch of ideas (with filters)
GET  /ideas/{idea_id}      - Get single idea
POST /ideas/{idea_id}/generate  - Generate full post for an idea
PATCH /ideas/{idea_id}/status   - Update status (approve/skip/draft)
PATCH /ideas/{idea_id}/draft    - Save edited draft text

GET  /posts/raw            - Browse raw scraped posts
GET  /config               - Get current config (profiles, keywords)
PATCH /config              - Update config
```

---

## Claude System Prompt (Transform Agent)

```
You are a content strategist writing LinkedIn posts for Dima Bilous, founder of Anfloy.

ABOUT DIMA:
- Builds and shares working AI agent systems for GTM, sales, marketing, and ops
- His angle: "I built this. It works. Here's exactly how."
- Audience: founders, sales leaders, RevOps/GTM engineers, SDRs/AEs
- He is always AHEAD - when a new tool drops, he finds the non-obvious angle

TONE RULES:
- Direct, confident, no hedging
- Casual but smart - like texting a founder friend
- Short sentences. Punchy.
- Specific numbers over vague claims
- First person, talk TO the reader with "you"

NEVER USE:
- Em dashes (—) or en dashes (–). Use hyphens (-) or periods.
- leverage, synergy, ecosystem, empower, cutting-edge, game-changing, revolutionary
- "In today's world", "As we all know"
- Hashtags in post body
- Emoji walls (zero or one max)
- Unverified stats or fake numbers

FORMAT:
- Arrow lists (→) not bullet points
- Unicode bold for section headers
- One thought per line, lots of white space
- CTA word in ALL CAPS

CTA PATTERN:
Drop/Comment "[WORD]" and I'll send you [specific thing].
♻️ Repost if your network needs this.

HOOK PATTERNS (use the most relevant):
1. "I stopped X. Now I Y." - for new approach replacing old one
2. "I built [N] [things] that [result]." - for multi-component systems
3. "You can literally [impressive thing] using [unexpected method]." - for surprising capabilities
4. "There's a new [thing] taking over [industry]." - for trends/roles
5. "Just wanted to introduce my new hire." - for single agent showcases
6. "[Tool] just dropped [feature] and nobody's talking about it." - for breaking news

When given a source post, generate 2 idea variations:
- Different angles on the same insight
- Each with: hook, full outline, post type, topic tag, suggested CTA word
- Quality bar: Dima could copy-paste, tweak for 5 minutes, and post
```

---

## Build Order

### Phase 1: Backend Foundation (Week 1)
1. FastAPI project setup on Railway
2. Airtable schema creation + API connection
3. Discovery Agent (Apify scraper for profiles + keywords)
4. Dedup logic
5. Scoring Agent
6. `/run/trigger` and `/run/status` endpoints

### Phase 2: Transform + Output (Week 1-2)
1. Transform Agent (Claude system prompt + structured output)
2. Write ideas to Airtable
3. `/ideas` endpoints (get, filter, update status)
4. `/ideas/{id}/generate` endpoint (full post generation)

### Phase 3: Dashboard (Week 2)
1. Next.js project setup on Vercel
2. Dashboard home + run trigger
3. Ideas feed with filters
4. Post editor (generate + tweak + save)
5. Drafts + config pages

### Phase 4: Breaking News Fast Lane (Week 3)
1. Lightweight news monitor (Anthropic blog, Product Hunt, etc.)
2. Fast lane scoring boost
3. Alert banner in dashboard

### Phase 5: X/Twitter (Future)
- Plug in X scraper as additional discovery source
- Adapt transform agent for X format (shorter, different CTA style)
- X-specific post editor

---

## What I Need From Dima

To start building:

| Item | Notes |
|------|-------|
| Airtable API key | From airtable.com/account |
| Airtable Base ID | Create the base first or I'll set it up |
| Apify API key | From console.apify.com |
| Anthropic API key | For Claude Sonnet 4.6 |
| Railway account | railway.app — connect GitHub |
| Vercel account | vercel.com — connect GitHub |
| GitHub repo | I'll create the monorepo structure |
| Dima's LinkedIn profile URL | For dedup (don't surface his own posts as inspiration) |

---

## Open Questions / Decisions Made

| Question | Decision |
|----------|----------|
| Database | Airtable (Dima's preference) |
| Hosting | Railway (backend) + Vercel (frontend) |
| Profiles to monitor | 6 confirmed (see Discovery section) |
| Lead magnets | Skipped for now |
| Instagram | Phase 2+ (modular, not in scope) |
| Auto-posting | NOT in scope - Dima approves everything |
| X/Twitter | Post-LinkedIn launch |
