"""
events_agent.py — Collects upcoming AI events and conferences via Tavily.

Uses targeted queries and an LLM pass to extract real event names, dates,
and locations from search results. Filters to future-dated events only.

Returns: events
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from state import NewsletterState
import config
from tools.tavily_tools import search_ai_news


def _year() -> int:
    return datetime.now().year


_EVENT_QUERIES = [
    "AI conference {year} registration open date location",
    "NeurIPS ICML ICLR machine learning conference {year} dates",
    "AI summit workshop {year} upcoming event tickets register",
    "artificial intelligence expo {year} upcoming",
]


def _extract_events(raw_results: list[dict], llm) -> list[dict]:
    """LLM pass: extract clean event name/date/location from raw Tavily results."""
    if not raw_results:
        return []

    year = _year()
    snippets = "\n\n".join(
        f"[{i+1}] TITLE: {r['title']}\n"
        f"     URL: {r['url']}\n"
        f"     CONTENT: {r['content'][:400]}"
        for i, r in enumerate(raw_results[:12])
    )

    prompt = f"""From these web results, extract up to 6 upcoming AI events or conferences.
Today is {datetime.now().strftime("%B %d, %Y")}.

{snippets}

Rules:
- Only include real named events (conferences, summits, workshops, expos)
- The event date must be in {year} or later — skip past events
- Extract the actual event name, not the page title
- For date, use format "Month DD, YYYY" or "Month DD–DD, YYYY" for multi-day events
- For location, use "City, Country" or "Virtual / Online" or "Hybrid"
- Skip generic article pages that list many events without specifics

Return a JSON array of objects with EXACTLY these keys:
[
  {{
    "name": "Full official event name",
    "date": "Month DD, YYYY or Month DD-DD, YYYY",
    "location": "City, Country or Virtual",
    "url": "direct URL to the event page"
  }}
]

Return ONLY the JSON array. No preamble."""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a precise JSON extractor. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])
        text = response.content.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            events = json.loads(match.group())
            # Deduplicate by name
            seen = set()
            clean = []
            for e in events:
                name = e.get("name", "").lower()
                if name and name not in seen:
                    seen.add(name)
                    clean.append(e)
            return clean[:6]
    except Exception:
        pass
    return []


def events_agent(state: NewsletterState) -> dict:
    errors: list[str] = []
    year = _year()

    # Pool results from multiple targeted queries
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for query_template in _EVENT_QUERIES:
        query = query_template.format(year=year)
        results = search_ai_news(query, max_results=4)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    if not all_results:
        errors.append("events_agent: No event results found via Tavily.")
        return {"events": [], "errors": errors}

    llm = config.get_llm(temperature=0.1, max_tokens=800)
    events = _extract_events(all_results, llm)

    if not events:
        errors.append("events_agent: LLM could not extract clean events from results.")

    return {"events": events, "errors": errors}
