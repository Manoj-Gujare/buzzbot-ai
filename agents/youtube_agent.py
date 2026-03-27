"""
youtube_agent.py — Finds and annotates the week's must-watch AI videos.

Falls back to Tavily-searched video URLs if YouTube API fails.

Returns: youtube_videos
"""

from __future__ import annotations

import sys
import os


from state import NewsletterState
import config
from tools.youtube_tools import find_weekly_ai_videos
from tools.tavily_tools import search_ai_news


_CATEGORY_LABELS = {
    "must_watch": "Must-Watch",
    "tutorial": "Tutorial",
    "explainer": "Research Explainer",
}


def _why_watch_prompt(video: dict) -> str:
    return f"""You are writing a short blurb for an AI newsletter about a YouTube video.

VIDEO TITLE: {video['title']}
CHANNEL: {video['channel']}
DESCRIPTION: {video['description'][:300]}
CATEGORY: {_CATEGORY_LABELS.get(video.get('category', 'must_watch'), 'Must-Watch')}

Write 1-2 sentences on why this video is worth watching this week. Be specific and energetic.
Return ONLY the sentences. No labels, no preamble."""


def _tavily_fallback() -> list[dict]:
    """Search Tavily for AI video links when YouTube API quota is exceeded."""
    results = search_ai_news("best AI YouTube video tutorial this week 2025", max_results=3)
    videos = []
    categories = ["must_watch", "tutorial", "explainer"]
    for i, r in enumerate(results[:3]):
        url = r.get("url", "")
        videos.append({
            "title": r["title"],
            "channel": r["source"],
            "video_id": "",
            "url": url,
            "description": r["content"][:200],
            "published_at": r.get("date", ""),
            "category": categories[i] if i < len(categories) else "must_watch",
            "duration": "N/A",
            "view_count": 0,
            "like_count": 0,
            "why_watch": "Featured video from this week in AI.",
        })
    return videos


def youtube_agent(state: NewsletterState) -> dict:
    errors: list[str] = []

    # ── Fetch videos ──────────────────────────────────────────────────────────
    videos = find_weekly_ai_videos()

    if not videos:
        errors.append("youtube_agent: YouTube API returned no results; falling back to Tavily.")
        videos = _tavily_fallback()
        return {"youtube_videos": videos, "errors": errors}

    # ── LLM: Write why_watch for each video ───────────────────────────────────
    try:
        llm = config.get_llm(temperature=0.6, max_tokens=300)
        from langchain_core.messages import HumanMessage
        for video in videos:
            try:
                response = llm.invoke([HumanMessage(content=_why_watch_prompt(video))])
                video["why_watch"] = response.content.strip()
            except Exception:
                video["why_watch"] = f"A great {_CATEGORY_LABELS.get(video.get('category', ''), 'AI')} video from {video['channel']}."
    except Exception as e:
        errors.append(f"youtube_agent LLM calls failed: {e}")
        for video in videos:
            video.setdefault("why_watch", f"Curated {video.get('category', 'AI')} video from this week.")

    return {"youtube_videos": videos, "errors": errors}
