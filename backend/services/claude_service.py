"""
Claude service — Anthropic API calls for scoring + content generation.
Uses claude-sonnet-4-6 (claude-sonnet-4-6).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# System prompt for Transform Agent (verbatim from ARCHITECTURE.md)
# ---------------------------------------------------------------------------

TRANSFORM_SYSTEM_PROMPT = """\
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
- Quality bar: Dima could copy-paste, tweak for 5 minutes, and post\
"""

# ---------------------------------------------------------------------------
# Scoring prompt
# ---------------------------------------------------------------------------

SCORING_SYSTEM_PROMPT = """\
You are a content scoring assistant for Dima Bilous, a LinkedIn creator focused on AI agents for GTM, sales automation, and outbound systems.

Dima's 5 topic pillars:
1. sales-outbound: AI agents for outbound, signal-based targeting, SDR replacement
2. marketing-content: Content systems, competitor monitoring, content repurposing
3. gtm-engineer: New GTM roles, RevOps automation, future of sales
4. new-tools: MCP servers, new model releases, AI tool launches, feature drops
5. systems-playbooks: Giveaways, step-by-step frameworks, case studies with real numbers

Score the post 0-100 based on:
- Topic Relevance (40%): How closely does this align with Dima's pillars? 
  0=unrelated, 40=perfect fit
- Engagement (25%): 100-499 reactions = 15 pts; 500+ = 25 pts; 50-99 = 8 pts; <50 = 3 pts
- Recency (20%): <24h = 20 pts; 24-48h = 18 pts; 2-7 days = 12 pts; >7 days = 5 pts
- Quality (15%): Is it a real insight/takeaway (not an ad, not spam, not bot engagement)?
  0=spam/ad, 15=genuine expert insight

Return ONLY valid JSON, no markdown, no explanation:
{
  "score": <integer 0-100>,
  "topic_cluster": "<sales-outbound|marketing-content|gtm-engineer|new-tools|systems-playbooks>",
  "relevance_score": <integer 0-40>,
  "engagement_score": <integer 0-25>,
  "recency_score": <integer 0-20>,
  "quality_score": <integer 0-15>,
  "reasoning": "<one sentence>"
}\
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _extract_json(text: str) -> Any:
    """Strip markdown code fences and parse JSON."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def score_post(
    post_text: str,
    reactions: int,
    comments: int,
    posted_at: str,
) -> dict[str, Any]:
    """
    Score a single post 0-100 using Claude.
    Returns dict with score, topic_cluster, sub-scores, reasoning.
    """
    client = _get_client()

    user_msg = (
        f"Post text:\n{post_text[:3000]}\n\n"
        f"Reactions: {reactions}\n"
        f"Comments: {comments}\n"
        f"Posted at: {posted_at or 'unknown'}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=SCORING_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text
        result = _extract_json(raw)
        return result
    except Exception as e:
        logger.error(f"Claude scoring failed: {e}")
        return {
            "score": 0,
            "topic_cluster": "sales-outbound",
            "relevance_score": 0,
            "engagement_score": 0,
            "recency_score": 0,
            "quality_score": 0,
            "reasoning": f"Scoring error: {e}",
        }


async def generate_ideas(
    post_text: str,
    author_name: str,
    reactions: int,
    topic_cluster: str,
) -> list[dict[str, Any]]:
    """
    Generate 2 idea variations for a source post.
    Returns list of idea dicts.
    """
    client = _get_client()

    user_msg = (
        f"Source post by {author_name} ({reactions} reactions):\n\n"
        f"{post_text[:3000]}\n\n"
        f"Topic cluster: {topic_cluster}\n\n"
        "Generate 2 idea variations. Return ONLY valid JSON array:\n"
        "[\n"
        "  {\n"
        '    "hook": "<opening line>",\n'
        '    "outline": "<full post structure with sections>",\n'
        '    "post_type": "<CTA Post|Hot Take|System Reveal|Feature Drop|Trend Post|Story>",\n'
        '    "topic_cluster": "<sales-outbound|marketing-content|gtm-engineer|new-tools|systems-playbooks>",\n'
        '    "effort": "<Quick Edit|Medium|Heavy>",\n'
        '    "cta_word": "<single word>"\n'
        "  },\n"
        "  { ... }\n"
        "]"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=TRANSFORM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text
        ideas = _extract_json(raw)
        if not isinstance(ideas, list):
            logger.warning("Claude returned non-list ideas response")
            return []
        # Validate required fields
        valid_ideas = []
        required = {"hook", "outline", "post_type", "topic_cluster", "effort", "cta_word"}
        for idea in ideas:
            if required.issubset(idea.keys()):
                valid_ideas.append(idea)
            else:
                missing = required - idea.keys()
                logger.warning(f"Idea missing fields {missing}, skipping")
        return valid_ideas[:2]  # max 2
    except Exception as e:
        logger.error(f"Claude idea generation failed: {e}")
        return []


async def generate_full_post(
    hook: str,
    outline: str,
    post_type: str,
    topic_cluster: str,
    cta_word: str,
    source_context: str = "",
) -> str:
    """
    Generate a full LinkedIn post from an idea card.
    This is what fires when Dima clicks "Generate Post".
    """
    client = _get_client()

    user_msg = (
        f"Write a full LinkedIn post based on this idea:\n\n"
        f"Hook: {hook}\n\n"
        f"Outline:\n{outline}\n\n"
        f"Post type: {post_type}\n"
        f"Topic cluster: {topic_cluster}\n"
        f"CTA word: {cta_word}\n"
    )
    if source_context:
        user_msg += f"\nSource context for reference:\n{source_context[:1000]}"

    user_msg += (
        "\n\nWrite the complete post. Follow all tone rules and formatting guidelines. "
        "End with the CTA pattern using the provided CTA word."
    )

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=TRANSFORM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude full post generation failed: {e}")
        return f"[Generation failed: {e}]"
