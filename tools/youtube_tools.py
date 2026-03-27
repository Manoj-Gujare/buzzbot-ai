"""
youtube_tools.py — YouTube Data API v3 helpers for finding weekly AI videos.
"""

from __future__ import annotations

import sys
import os
import re
from datetime import datetime, timedelta, timezone


import config

# Quota tracking (estimates; YouTube's free daily limit is 10,000 units)
_QUOTA_USED = 0
_QUOTA_WARNING_THRESHOLD = 500


def _get_service():
    from googleapiclient.discovery import build
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)


def _track_quota(units: int):
    global _QUOTA_USED
    _QUOTA_USED += units
    if _QUOTA_USED >= _QUOTA_WARNING_THRESHOLD:
        print(
            f"[YouTube] ⚠  Estimated quota used: {_QUOTA_USED} units "
            f"(daily free limit: 10,000). Proceeding cautiously."
        )


def _iso_week_ago() -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=7)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _duration_to_human(iso_duration: str) -> str:
    """Convert ISO 8601 duration (PT1H23M45S) to MM:SS or HH:MM:SS."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration)
    if not match:
        return "N/A"
    h, m, s = (int(x) if x else 0 for x in match.groups())
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def search_youtube(
    query: str,
    max_results: int = 3,
    published_after: str | None = None,
) -> list[dict]:
    """
    Search YouTube for videos matching query published in the last 7 days.
    Returns title, channel, video_id, url, description, published_at.
    """
    try:
        youtube = _get_service()
        after = published_after or _iso_week_ago()

        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="relevance",
            relevanceLanguage="en",
            publishedAfter=after,
            maxResults=max_results,
        )
        response = request.execute()
        _track_quota(100)  # search = 100 units

        results = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            if not video_id:
                continue
            description = snippet.get("description", "")
            results.append({
                "title": snippet.get("title", "Untitled"),
                "channel": snippet.get("channelTitle", "Unknown Channel"),
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "description": description[:200],
                "published_at": snippet.get("publishedAt", ""),
            })
        return results
    except Exception:
        return []


def get_video_details(video_ids: list[str]) -> dict[str, dict]:
    """
    Fetch duration and stats for a list of video IDs.
    Returns a dict keyed by video_id.
    """
    if not video_ids:
        return {}
    try:
        youtube = _get_service()
        request = youtube.videos().list(
            part="contentDetails,statistics",
            id=",".join(video_ids),
        )
        response = request.execute()
        _track_quota(len(video_ids))  # videos.list = 1 unit per video

        details = {}
        for item in response.get("items", []):
            vid_id = item["id"]
            duration_iso = item.get("contentDetails", {}).get("duration", "PT0S")
            stats = item.get("statistics", {})
            details[vid_id] = {
                "duration": _duration_to_human(duration_iso),
                "view_count": int(stats.get("viewCount", 0)),
                "like_count": int(stats.get("likeCount", 0)),
            }
        return details
    except Exception:
        return {}


# Keywords that must appear in the VIDEO TITLE (not just description)
_TITLE_REQUIRED = {
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "gpt", "claude", "gemini", "chatgpt", "openai", "anthropic",
    "neural network", "model", "agent", "transformer", "diffusion",
    "generative ai", "nlp", "deepmind", "mistral", "llama", "copilot",
    "stable diffusion", "midjourney", "sora", "runway",
}

# Words that instantly disqualify a video regardless of other keywords
_BLOCKLIST = {
    "news highlights", "fox news", "cnn", "bbc news", "comedy", "late show",
    "tonight show", "daily show", "snl", "sports", "cricket", "football",
    "music", "song", "trailer", "movie review", "vlog",
}


def _is_ai_video(video: dict) -> bool:
    """
    Return True only if:
    - The video TITLE contains at least one AI-specific keyword, AND
    - The title does not contain any blocklist terms
    """
    title = video.get("title", "").lower()
    # Reject if any blocklist phrase is in the title
    if any(b in title for b in _BLOCKLIST):
        return False
    # Accept only if a real AI keyword is in the title
    return any(kw in title for kw in _TITLE_REQUIRED)


def find_weekly_ai_videos() -> list[dict]:
    """
    Run 3 targeted searches and return up to 3 categorised AI videos.
    Filters out non-AI videos. Tries up to max_results per query to find a valid one.
    """
    year = datetime.now().year
    searches = [
        (f"AI news recap this week {year}", "must_watch"),
        (f"AI tool tutorial how to use {year}", "tutorial"),
        (f"AI research paper explained {year}", "explainer"),
    ]

    seen_ids: set[str] = set()
    videos: list[dict] = []

    for query, category in searches:
        # Fetch more results so we can filter and still find one valid AI video
        results = search_youtube(query, max_results=5)
        for v in results:
            if v["video_id"] not in seen_ids and _is_ai_video(v):
                seen_ids.add(v["video_id"])
                v["category"] = category
                videos.append(v)
                break  # take first valid AI video per category

    # Enrich with duration + stats
    if videos:
        ids = [v["video_id"] for v in videos]
        details = get_video_details(ids)
        for v in videos:
            extra = details.get(v["video_id"], {})
            v["duration"] = extra.get("duration", "N/A")
            v["view_count"] = extra.get("view_count", 0)
            v["like_count"] = extra.get("like_count", 0)

    return videos[:3]
