"""
analysis_agent.py — Writes the Deep Dive section and scores the AI Sentiment Meter.

Runs AFTER news_agent so it has access to state["top_news"].
Uses the top story as the Deep Dive subject.
Falls back to "Week in AI" if top_news is empty.

Returns:
    deep_dive_title, deep_dive_content,
    sentiment_hype, sentiment_concern, sentiment_optimism, sentiment_skepticism,
    sentiment_summary
"""

from __future__ import annotations

import json
import re
import sys
import os


from state import NewsletterState
import config


def _parse_json(text: str) -> dict:
    text = text.strip()
    for fence in ["```json", "```"]:
        if fence in text:
            parts = text.split(fence)
            if len(parts) >= 3:
                text = parts[1].strip()
                break
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def analysis_agent(state: NewsletterState) -> dict:
    errors: list[str] = []

    # ── Determine Deep Dive subject ───────────────────────────────────────────
    top_news = state.get("top_news", [])
    if top_news:
        top_story = top_news[0]
        subject = top_story.get("title", "")
        context = top_story.get("summary", "") + "\n" + top_story.get("why_it_matters", "")
        source_url = top_story.get("url", "")
    else:
        # Fallback topic
        week_label = state.get("week_label", "this week")
        subject = f"The State of AI — {week_label}"
        context = "A broad look at the most significant AI developments, trends, and debates this week."
        source_url = ""

    prompt = f"""You are a senior AI analyst writing for THE AI PULSE newsletter — a balanced, non-hype, technically credible publication for AI professionals and enthusiasts.

DEEP DIVE SUBJECT: {subject}
CONTEXT: {context}
SOURCE: {source_url}

Write a thorough, balanced deep dive analysis. Then assess community sentiment.

Return a JSON object with EXACTLY these keys:

{{
  "deep_dive_title": "A punchy, specific, action-oriented headline (max 12 words)",
  "deep_dive_content": "400-600 words. Structure as 5 paragraphs:\\n\\n**Paragraph 1 (Set the stage):** Why this topic matters right now and what triggered it.\\n\\n**Paragraph 2 (Break it down):** The specific details — what exactly was announced, released, or changed? Use data and specifics.\\n\\n**Paragraph 3 (Multiple perspectives):** Present at least 2 different viewpoints — optimistic, skeptical, researcher perspective, industry perspective. Be fair.\\n\\n**Paragraph 4 (Synthesis):** What does all of this add up to? What is the net takeaway?\\n\\n**Paragraph 5 (What to watch):** Forward-looking — what should readers track in the coming days/weeks?",
  "sentiment_hype": 70,
  "sentiment_concern": 45,
  "sentiment_optimism": 65,
  "sentiment_skepticism": 40,
  "sentiment_summary": "1-2 sentences on the overall community mood and vibe around AI this week."
}}

IMPORTANT RULES:
- sentiment scores are integers 0-100 (not strings)
- deep_dive_content must be 400-600 words of actual prose, not bullet points
- Be balanced — avoid cheerleading or doom-saying
- Return ONLY the JSON. No preamble, no markdown fences."""

    try:
        llm = config.get_llm(temperature=0.6, max_tokens=3000)
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(
                content=(
                    "You are a senior AI analyst who writes for a balanced, non-hype newsletter. "
                    "You are precise, nuanced, and always cite specifics. Return only valid JSON."
                )
            ),
            HumanMessage(content=prompt),
        ])
        data = _parse_json(response.content)

        deep_dive_title = data.get("deep_dive_title", subject)
        deep_dive_content = data.get("deep_dive_content", context)
        sentiment_hype = int(data.get("sentiment_hype", 60))
        sentiment_concern = int(data.get("sentiment_concern", 40))
        sentiment_optimism = int(data.get("sentiment_optimism", 55))
        sentiment_skepticism = int(data.get("sentiment_skepticism", 35))
        sentiment_summary = data.get("sentiment_summary", "")

    except Exception as e:
        errors.append(f"analysis_agent LLM call failed: {e}")
        deep_dive_title = subject
        deep_dive_content = context
        sentiment_hype = 60
        sentiment_concern = 40
        sentiment_optimism = 55
        sentiment_skepticism = 35
        sentiment_summary = "The AI community remains cautiously optimistic with ongoing debates around safety and capability."

    return {
        "deep_dive_title": deep_dive_title,
        "deep_dive_content": deep_dive_content,
        "sentiment_hype": max(0, min(100, sentiment_hype)),
        "sentiment_concern": max(0, min(100, sentiment_concern)),
        "sentiment_optimism": max(0, min(100, sentiment_optimism)),
        "sentiment_skepticism": max(0, min(100, sentiment_skepticism)),
        "sentiment_summary": sentiment_summary,
        "errors": errors,
    }
