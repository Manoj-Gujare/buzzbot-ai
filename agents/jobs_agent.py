"""
jobs_agent.py — Collects current AI job openings in India via Tavily.

Uses targeted India-specific queries then an LLM pass to extract
clean structured listings.

Returns: jobs
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from state import NewsletterState
import config
from tools.tavily_tools import search_ai_news


def _year() -> int:
    return datetime.now().year


_JOB_QUERIES = [
    "AI machine learning engineer job opening India {year} Bangalore Mumbai Hyderabad",
    "artificial intelligence researcher data scientist hiring India {year} apply",
    "LLM generative AI engineer job India remote {year}",
    "AI product manager ML engineer India {year} job opening",
]


def _extract_jobs(raw_results: list[dict], llm) -> list[dict]:
    """LLM pass: extract clean India-based AI job listings from raw Tavily results."""
    if not raw_results:
        return []

    snippets = "\n\n".join(
        f"[{i+1}] TITLE: {r['title']}\n"
        f"     URL: {r['url']}\n"
        f"     CONTENT: {r['content'][:300]}"
        for i, r in enumerate(raw_results[:12])
    )

    prompt = f"""From these web results, extract up to 6 specific AI/ML job openings based in India.

{snippets}

STRICT RULES:
- Only include actual job postings — not articles about jobs, not job board homepages
- Location must be in India (Bangalore, Mumbai, Hyderabad, Delhi, Pune, Chennai, Remote-India, etc.)
- Extract the specific role title, not the page title
- If a result is clearly not an individual job listing, skip it

Return a JSON array with EXACTLY these keys:
[
  {{
    "role": "Specific job title (e.g. Senior ML Engineer, AI Researcher)",
    "company": "Company name",
    "location": "City, India or Remote (India)",
    "type": "Full-time or Contract or Internship",
    "url": "URL to the listing"
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
            jobs = json.loads(match.group())
            seen: set[str] = set()
            clean: list[dict] = []
            for j in jobs:
                url = j.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    clean.append(j)
            return clean[:6]
    except Exception:
        pass
    return []


def jobs_agent(state: NewsletterState) -> dict:
    errors: list[str] = []
    year = _year()

    all_results: list[dict] = []
    seen_urls: set[str] = set()

    for query_template in _JOB_QUERIES:
        query = query_template.format(year=year)
        results = search_ai_news(query, max_results=4)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    if not all_results:
        errors.append("jobs_agent: No India AI job results found via Tavily.")
        return {"jobs": [], "errors": errors}

    llm = config.get_llm(temperature=0.1, max_tokens=1000)
    jobs = _extract_jobs(all_results, llm)

    if not jobs:
        errors.append("jobs_agent: LLM could not extract clean India job listings from results.")

    return {"jobs": jobs, "errors": errors}
