#!/usr/bin/env python3
"""
Content Engine — Airtable one-time setup script.

Two setup paths:

  PATH A (new base, you have a workspace ID):
      python3 setup.py --workspace-id wspmK5bdNNFplwVVE

  PATH B (you created a blank base manually — RECOMMENDED for fresh accounts):
      python3 setup.py --base-id appXXXXXXXXXXXXXX

  PATH C (base ID is already in .env):
      python3 setup.py          ← auto-detects AIRTABLE_BASE_ID

--------------------------------------------------------------------
How to create a blank Airtable base (Path B):
  1. Go to https://airtable.com
  2. Click "+ Add a base" → "Start from scratch"
  3. Name it "Content Engine"
  4. Copy the base ID from the URL:
       https://airtable.com/appXXXXXXXXXXXXXX/...
       → the "app..." part is your base ID
  5. Run:  python3 setup.py --base-id appXXXXXXXXXXXXXX
--------------------------------------------------------------------

The script will create all 4 tables with the correct schema:
  - Raw Posts
  - Generated Ideas
  - Runs
  - Published Posts

It writes AIRTABLE_BASE_ID to .env when done.
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ---------------------------------------------------------------------------
# Table schema (fields only — tables are created one at a time)
# ---------------------------------------------------------------------------

TABLES: list[dict] = [
    {
        "name": "Raw Posts",
        "fields": [
            {"name": "post_id",       "type": "singleLineText"},
            {"name": "author_name",   "type": "singleLineText"},
            {"name": "author_url",    "type": "url"},
            {"name": "post_url",      "type": "url"},
            {"name": "post_text",     "type": "multilineText"},
            {"name": "reactions",     "type": "number",   "options": {"precision": 0}},
            {"name": "comments",      "type": "number",   "options": {"precision": 0}},
            {"name": "posted_at",     "type": "singleLineText"},
            {"name": "scraped_at",    "type": "singleLineText"},
            {"name": "score",         "type": "number",   "options": {"precision": 1}},
            {"name": "topic_cluster", "type": "singleSelect", "options": {"choices": [
                {"name": "sales-outbound"}, {"name": "marketing-content"},
                {"name": "gtm-engineer"}, {"name": "new-tools"}, {"name": "systems-playbooks"},
            ]}},
            {"name": "fast_lane",     "type": "checkbox", "options": {"icon": "check", "color": "yellowBright"}},
            {"name": "batch_id",      "type": "singleLineText"},
        ],
    },
    {
        "name": "Generated Ideas",
        "fields": [
            {"name": "idea_id",         "type": "singleLineText"},
            {"name": "hook",            "type": "singleLineText"},
            {"name": "outline",         "type": "multilineText"},
            {"name": "post_type",       "type": "singleSelect", "options": {"choices": [
                {"name": "CTA Post"}, {"name": "Hot Take"}, {"name": "System Reveal"},
                {"name": "Feature Drop"}, {"name": "Trend Post"}, {"name": "Story"},
            ]}},
            {"name": "topic_cluster",   "type": "singleSelect", "options": {"choices": [
                {"name": "sales-outbound"}, {"name": "marketing-content"},
                {"name": "gtm-engineer"}, {"name": "new-tools"}, {"name": "systems-playbooks"},
            ]}},
            {"name": "effort",          "type": "singleSelect", "options": {"choices": [
                {"name": "Quick Edit"}, {"name": "Medium"}, {"name": "Heavy"},
            ]}},
            {"name": "cta_word",          "type": "singleLineText"},
            {"name": "source_post_id",    "type": "singleLineText"},
            {"name": "source_reactions",  "type": "number", "options": {"precision": 0}},
            {"name": "source_author",     "type": "singleLineText"},
            {"name": "status",            "type": "singleSelect", "options": {"choices": [
                {"name": "New"}, {"name": "Approved"}, {"name": "Skipped"},
                {"name": "Draft"}, {"name": "Published"},
            ]}},
            {"name": "generated_draft", "type": "multilineText"},
            {"name": "dima_notes",      "type": "multilineText"},
            {"name": "batch_id",        "type": "singleLineText"},
            {"name": "created_at",      "type": "singleLineText"},
        ],
    },
    {
        "name": "Runs",
        "fields": [
            {"name": "run_id",               "type": "singleLineText"},
            {"name": "triggered_at",         "type": "singleLineText"},
            {"name": "status",               "type": "singleSelect", "options": {"choices": [
                {"name": "Running"}, {"name": "Done"}, {"name": "Failed"},
            ]}},
            {"name": "posts_discovered",     "type": "number", "options": {"precision": 0}},
            {"name": "ideas_generated",      "type": "number", "options": {"precision": 0}},
            {"name": "fast_lane_count",      "type": "number", "options": {"precision": 0}},
            {"name": "apify_compute_units",  "type": "number", "options": {"precision": 4}},
            {"name": "run_index",            "type": "number", "options": {"precision": 0}},
            {"name": "queries_run",          "type": "multilineText"},
            {"name": "notes",                "type": "multilineText"},
        ],
    },
    {
        "name": "Published Posts",
        "fields": [
            {"name": "post_id",           "type": "singleLineText"},
            {"name": "final_text",        "type": "multilineText"},
            {"name": "platform",          "type": "singleSelect", "options": {"choices": [
                {"name": "LinkedIn"}, {"name": "X"},
            ]}},
            {"name": "posted_at",         "type": "singleLineText"},
            {"name": "reactions",         "type": "number", "options": {"precision": 0}},
            {"name": "comments",          "type": "number", "options": {"precision": 0}},
            {"name": "idea_id",           "type": "singleLineText"},
            {"name": "performance_notes", "type": "multilineText"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import httpx


async def create_tables_in_base(token: str, base_id: str) -> list[str]:
    """
    Create all Content Engine tables in an existing Airtable base.
    Returns list of created table names.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    created: list[str] = []

    # First, find which tables already exist
    existing_names: set[str] = set()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(
            f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
            headers=headers,
        )
        if r.status_code == 200:
            for t in r.json().get("tables", []):
                existing_names.add(t["name"])
            print(f"  Existing tables: {existing_names or 'none'}")
        else:
            print(f"  Could not list existing tables: {r.status_code} {r.text[:200]}")

        for table in TABLES:
            name = table["name"]
            if name in existing_names:
                print(f"  ✓ {name} (already exists)")
                created.append(name)
                continue
            resp = await c.post(
                f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
                headers=headers,
                json=table,
            )
            if resp.status_code in (200, 201):
                print(f"  ✓ {name} (created)")
                created.append(name)
            else:
                print(f"  ✗ {name}: {resp.status_code} {resp.text[:200]}")

    return created


async def create_base_with_workspace(token: str, workspace_id: str) -> str:
    """Create a new base in an existing workspace. Returns base_id."""
    from pyairtable import Api
    api = Api(token)
    new_base = api.create_base(workspace_id, "Content Engine", [])  # empty, tables added next
    return new_base.id


def persist_base_id(base_id: str) -> None:
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
    lines: list[str] = []
    found = False
    if os.path.exists(env_path):
        with open(env_path) as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.startswith("AIRTABLE_BASE_ID="):
                lines[i] = f"AIRTABLE_BASE_ID={base_id}\n"
                found = True
                break
    if not found:
        lines.append(f"AIRTABLE_BASE_ID={base_id}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)
    os.environ["AIRTABLE_BASE_ID"] = base_id
    print(f"  ✓ AIRTABLE_BASE_ID={base_id} written to .env")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(argv: list[str]):
    token = os.environ.get("AIRTABLE_TOKEN", "").strip()
    if not token:
        print("ERROR: AIRTABLE_TOKEN not set in .env")
        sys.exit(1)

    # Parse args
    base_id      = ""
    workspace_id = ""
    for i, arg in enumerate(argv):
        if arg in ("--base-id", "-b") and i + 1 < len(argv):
            base_id = argv[i + 1].strip()
        elif arg in ("--workspace-id", "-w") and i + 1 < len(argv):
            workspace_id = argv[i + 1].strip()

    # Fall back to env
    if not base_id:
        base_id = os.environ.get("AIRTABLE_BASE_ID", "").strip()
    if not workspace_id:
        workspace_id = os.environ.get("AIRTABLE_WORKSPACE_ID", "").strip()

    print("=" * 60)
    print("  Content Engine — Airtable Setup")
    print("=" * 60)

    # ------------------------------------------------------------------ #
    # Step 1: Ensure we have a base_id                                   #
    # ------------------------------------------------------------------ #
    if base_id:
        print(f"\nUsing existing base ID: {base_id}")
    elif workspace_id:
        print(f"\nCreating base in workspace: {workspace_id} …")
        try:
            base_id = await create_base_with_workspace(token, workspace_id)
            print(f"  ✓ Base created: {base_id}")
            persist_base_id(base_id)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            sys.exit(1)
    else:
        print("""
ERROR: No base ID or workspace ID provided.

OPTION 1 — Create a blank Airtable base manually (easiest):
  1. Go to https://airtable.com
  2. Click "+ Add a base" → "Start from scratch"
  3. Name it "Content Engine"
  4. Copy the base ID from the URL:
       https://airtable.com/appXXXXXXXXXXXXXX/...
  5. Run:  python3 setup.py --base-id appXXXXXXXXXXXXXX

OPTION 2 — Provide your workspace ID:
  → Find it in your Airtable URL: https://airtable.com/wsp[WORKSPACE_ID]/...
  → Run:  python3 setup.py --workspace-id wspmK5bdNNFplwVVE
""")
        sys.exit(1)

    # ------------------------------------------------------------------ #
    # Step 2: Create all tables in the base                              #
    # ------------------------------------------------------------------ #
    print(f"\nCreating tables in base {base_id} …")
    created = await create_tables_in_base(token, base_id)

    if len(created) < len(TABLES):
        print(f"\n⚠ Only {len(created)}/{len(TABLES)} tables created. Check errors above.")
    else:
        print(f"\n✓ All {len(TABLES)} tables ready.")

    # ------------------------------------------------------------------ #
    # Step 3: Persist base ID                                            #
    # ------------------------------------------------------------------ #
    persist_base_id(base_id)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    Setup complete! ✓                         ║
╚══════════════════════════════════════════════════════════════╝

Base ID: {base_id}

Next steps:
  1. Start server:    uvicorn main:app --reload
  2. Check health:    curl http://localhost:8000/health
  3. Trigger run:     curl -X POST http://localhost:8000/run/trigger
  4. View ideas:      curl http://localhost:8000/ideas

Railway deployment:
  railway login && railway up
""")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
