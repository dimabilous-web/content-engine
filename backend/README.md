# Content Engine — Backend

FastAPI + LangGraph backend for Dima's LinkedIn Content Engine.

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure .env

Copy `.env.example` → `.env` and fill in your credentials:

```
AIRTABLE_TOKEN=pat...
AIRTABLE_WORKSPACE_ID=wsp...   ← needed for first-time setup only
APIFY_API_KEY=apify_api_...
ANTHROPIC_API_KEY=sk-ant-...
```

**Finding your Airtable workspace ID:**
1. Go to https://airtable.com
2. Click your workspace in the left sidebar
3. Copy the `wsp...` part from the URL: `https://airtable.com/wspmK5bdNNFplwVVE/...`

### 3. First-time Airtable setup

```bash
python3 setup.py
```

This creates the "Content Engine" base + all 4 tables (Raw Posts, Generated Ideas, Runs, Published Posts) and writes `AIRTABLE_BASE_ID` back to `.env`.

After this, you never need `AIRTABLE_WORKSPACE_ID` again.

### 4. Start the server

```bash
uvicorn main:app --reload
```

API docs at: http://localhost:8000/docs

---

## API Endpoints

### Setup
| Method | Path | Description |
|--------|------|-------------|
| GET | `/setup/status` | Check what needs configuring |
| POST | `/setup/init-airtable?workspace_id=wsp...` | Create Airtable base |

### Pipeline
| Method | Path | Description |
|--------|------|-------------|
| POST | `/run/trigger` | Start a pipeline run (async) |
| GET | `/run/{run_id}/status` | Check run status |
| GET | `/runs` | List recent runs |

### Ideas
| Method | Path | Description |
|--------|------|-------------|
| GET | `/ideas` | Get ideas (filter by status, post_type, topic_cluster, effort) |
| GET | `/ideas/{idea_id}` | Get single idea |
| POST | `/ideas/{idea_id}/generate` | Generate full post draft |
| PATCH | `/ideas/{idea_id}/status` | Update status |
| PATCH | `/ideas/{idea_id}/draft` | Save edited draft |

### Posts & Config
| Method | Path | Description |
|--------|------|-------------|
| GET | `/posts/raw` | Browse raw scraped posts |
| GET | `/config` | Current config + rotation preview |
| GET | `/health` | Health check |

---

## Discovery Strategy

**Primary (80%):** Keyword viral search across all of LinkedIn  
- 14 keyword queries, 7 run per execution (rotates across runs)  
- Filter: 100+ reactions OR 50+ comments  
- Cap: 120 posts  

**Secondary (20%):** 6 monitored profiles  
- Always scraped regardless of engagement  
- Batched into 1 Apify actor call (not 6 separate runs)  
- Cap: 5 posts per profile = 30 posts  

**Total cap:** 150 posts per run  
**Dedup:** Runs BEFORE any Claude API calls  
**Cadence:** Weekly (manual trigger always available)

---

## Pipeline Flow

```
[Trigger]
    ↓
[discovery_node]  ← Apify (keyword + profile, batched, rotated)
    ↓
[dedup_node]      ← Filter already-seen post URLs (before Claude)
    ↓
[scoring_node]    ← Claude scores each post 0-100
    ↓
[select_node]     ← Top 25 by score
    ↓
[transform_node]  ← Claude generates 2 ideas per post (50 idea cards)
    ↓
[output_node]     ← Write to Airtable, close run record with costs
```

---

## Cost Estimates

| Source | Cost per run |
|--------|-------------|
| Apify (150 posts scraped) | ~$0.50–$2.00 |
| Claude (scoring 150 + 50 ideas) | ~$0.10–$0.30 |
| **Total per week** | **< $3** |

Apify compute units are stored in the Runs table per execution.

---

## Deploy to Railway

```bash
railway login
railway init
railway up
```

Set all env vars in Railway dashboard under Variables.

The `railway.toml` is pre-configured with health check on `/health`.

---

## Project Structure

```
backend/
├── main.py                  ← FastAPI app, all routes
├── setup.py                 ← One-time Airtable setup script
├── agents/
│   ├── pipeline.py          ← LangGraph graph definition + runner
│   ├── discovery.py         ← Discovery node (Apify)
│   ├── scoring.py           ← Dedup + scoring + select nodes
│   ├── transform.py         ← Idea generation node (Claude)
│   └── output.py            ← Write to Airtable node
├── services/
│   ├── airtable_service.py  ← Airtable CRUD + base provisioning
│   ├── apify_service.py     ← LinkedIn scrapers (profile + keyword)
│   └── claude_service.py    ← Scoring + idea gen + full post gen
├── models/
│   └── schemas.py           ← Pydantic v2 models
├── requirements.txt
├── .env                     ← Credentials (not committed)
├── .env.example
└── railway.toml
```
