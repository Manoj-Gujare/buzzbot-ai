"""
tavily_tools.py — All Tavily search helpers used by the newsletter agents.

Every function:
  • Wraps the API call in try/except
  • Returns [] on failure (never crashes the pipeline)
  • Deduplicates results by URL before returning
"""

from __future__ import annotations

import sys
import os
from datetime import datetime

from tavily import TavilyClient
import config


def _year() -> int:
    return datetime.now().year


def _get_client() -> TavilyClient:
    return TavilyClient(api_key=config.TAVILY_API_KEY)


def _dedup(items: list[dict], key: str = "url") -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item in items:
        val = item.get(key, "")
        if val and val not in seen:
            seen.add(val)
            out.append(item)
    return out


# ── 1. AI News ────────────────────────────────────────────────────────────────

def search_ai_news(query: str, max_results: int = 5) -> list[dict]:
    """Search for recent AI news. Returns title, url, content, source, date."""
    try:
        client = _get_client()
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", "Untitled"),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "source": r.get("url", "").split("/")[2] if r.get("url") else "Unknown",
                "date": r.get("published_date", ""),
            })
        return _dedup(results)
    except Exception as e:
        return []


# ── 2. AI Tools ───────────────────────────────────────────────────────────────

def search_ai_tools(week_label: str, max_results: int = 8) -> list[dict]:
    """Search for new AI tools launched this week."""
    try:
        client = _get_client()
        query = f"new AI tools launched {week_label} {_year()} product launch"
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
        )
        results = []
        for r in response.get("results", []):
            content = r.get("content", "")
            results.append({
                "name": r.get("title", "Unknown Tool"),
                "company": r.get("url", "").split("/")[2] if r.get("url") else "",
                "category": "AI Tool",
                "description": content[:300] if content else "No description available.",
                "pricing": "See website",
                "url": r.get("url", ""),
            })
        return _dedup(results)
    except Exception as e:
        return []


# ── 3. AI Jobs ────────────────────────────────────────────────────────────────

def search_ai_jobs(max_results: int = 6) -> list[dict]:
    """Search for current AI job openings."""
    try:
        client = _get_client()
        response = client.search(
            query=f"top AI machine learning jobs hiring {_year()} remote",
            search_depth="advanced",
            max_results=max_results,
        )
        results = []
        for r in response.get("results", []):
            title = r.get("title", "AI Role")
            results.append({
                "role": title,
                "company": r.get("url", "").split("/")[2] if r.get("url") else "Unknown",
                "location": "Remote / See listing",
                "type": "Full-time",
                "url": r.get("url", ""),
            })
        return _dedup(results)
    except Exception as e:
        return []


# ── 4. AI Events ──────────────────────────────────────────────────────────────

def search_ai_events(max_results: int = 5) -> list[dict]:
    """Search for upcoming AI conferences and events."""
    try:
        client = _get_client()
        response = client.search(
            query=f"upcoming AI conference summit event {_year()} register",
            search_depth="advanced",
            max_results=max_results,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "name": r.get("title", "AI Event"),
                "date": r.get("published_date", "TBD"),
                "location": "See event page",
                "url": r.get("url", ""),
            })
        return _dedup(results)
    except Exception as e:
        return []


# ── 5. AI Quotes ──────────────────────────────────────────────────────────────

def search_ai_quotes(week_label: str, max_results: int = 5) -> list[dict]:
    """Search for notable AI quotes from thought leaders this week."""
    try:
        client = _get_client()
        response = client.search(
            query=f'AI researcher CEO quote statement {week_label} {_year()}',
            search_depth="advanced",
            max_results=max_results,
        )
        results = []
        for r in response.get("results", []):
            results.append({
                "quote": r.get("content", "")[:200],
                "speaker": "AI Leader",
                "title": "Industry Expert",
                "source_url": r.get("url", ""),
            })
        return _dedup(results, key="source_url")
    except Exception as e:
        return []


# ── 6. Industry Use Cases ─────────────────────────────────────────────────────

_USECASE_QUERIES = [
    "Microsoft Google Amazon AI deployment results {year} reduced costs improved efficiency",
    "healthcare AI deployment hospital patient outcomes results {year}",
    "retail finance manufacturing AI automation case study results {year}",
    "startup company AI integration measurable results {year} productivity",
]


def search_industry_usecases(max_results: int = 5) -> list[dict]:
    """Search for real-world AI deployments across industries using multiple targeted queries."""
    try:
        client = _get_client()
        all_results: list[dict] = []
        seen_urls: set[str] = set()

        for query_template in _USECASE_QUERIES:
            query = query_template.format(year=_year())
            try:
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=max_results,
                )
                for r in response.get("results", []):
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append({
                            "title": r.get("title", ""),
                            "content": r.get("content", ""),
                            "url": url,
                        })
            except Exception:
                continue

        return all_results[:20]
    except Exception:
        return []


# ── 7. AI Stats ───────────────────────────────────────────────────────────────

def search_ai_stats(max_results: int = 5) -> list[dict]:
    """Search for notable AI statistics and metrics from this week."""
    try:
        client = _get_client()
        response = client.search(
            query=f"AI statistics data report numbers {_year()} billion users market size",
            search_depth="advanced",
            max_results=max_results,
        )
        results = []
        for r in response.get("results", []):
            content = r.get("content", "")
            results.append({
                "metric": r.get("title", "AI Metric"),
                "number": "See source",
                "context": content[:200] if content else "Growing AI adoption across sectors.",
            })
        return _dedup(results, key="metric")
    except Exception as e:
        return []
