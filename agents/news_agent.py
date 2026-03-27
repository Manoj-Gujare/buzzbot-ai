"""
news_agent.py — Collects and curates the week's top AI news stories.

Runs 5 Tavily queries, deduplicates, then makes ONE LLM call to:
  - rank the top 5 most newsworthy stories with why_it_matters
  - identify 4 quick hits with one-liners
  - extract up to 3 notable quotes from AI leaders

Returns: top_news, quick_hits, ai_quotes
"""

from __future__ import annotations

import json
import sys
import os


from datetime import datetime

from state import NewsletterState
import config
from tools.tavily_tools import search_ai_news


def _build_queries(week_label: str) -> list[str]:
    year = datetime.now().year
    return [
        f"biggest AI announcement this week {week_label} {year}",
        f"new AI model released this week {week_label} {year}",
        f"AI government regulation policy this week {year}",
        f"AI startup funding deal this week {year}",
        f"AI safety controversy debate this week {year}",
    ]


def _parse_json(text: str) -> dict:
    """Robustly extract JSON from LLM response."""
    text = text.strip()
    # Strip markdown code fences
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
    # Try to find first {...} block
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


_QUOTE_QUERIES = [
    'Sam Altman Demis Hassabis Yann LeCun said statement quote {year}',
    'AI CEO founder researcher quote interview {week} {year}',
    'artificial intelligence leader opinion statement said {year}',
]


def _fetch_quotes(week_label: str, errors: list[str]) -> list[dict]:
    """Dedicated Tavily search + LLM extraction for real AI leader quotes."""
    year = datetime.now().year
    raw: list[dict] = []
    seen_urls: set[str] = set()

    for template in _QUOTE_QUERIES:
        query = template.format(year=year, week=week_label)
        results = search_ai_news(query, max_results=4)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw.append(r)

    if not raw:
        return []

    snippets = "\n\n".join(
        f"[{i+1}] TITLE: {r['title']}\n"
        f"     URL: {r['url']}\n"
        f"     CONTENT: {r['content'][:500]}"
        for i, r in enumerate(raw[:10])
    )

    prompt = f"""Extract up to 3 real quotes from AI leaders from these articles.
Week: {week_label}

{snippets}

STRICT RULES — all must be true for a quote to be included:
- The quote itself must be ABOUT artificial intelligence, machine learning, LLMs, AI safety, AI regulation, AI products, or the tech industry — not about sports, personal life, hobbies, or unrelated topics
- Speaker must be a named AI researcher, CEO, founder, or policymaker
- Quote must be a direct or close paraphrase from the article content — never invented
- If fewer than 1 qualifying AI-topic quote exists, return an empty array

Return a JSON array:
[
  {{
    "quote": "The quote text — must be about AI or tech",
    "speaker": "Full name",
    "title": "Job title and company",
    "source_url": "URL of the article"
  }}
]

Return ONLY the JSON array. No preamble."""

    try:
        import re as _re
        llm = config.get_llm(temperature=0.1, max_tokens=800)
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a precise JSON extractor. Return only valid JSON. Never invent quotes."),
            HumanMessage(content=prompt),
        ])
        text = response.content.strip()
        match = _re.search(r"\[.*\]", text, _re.DOTALL)
        if match:
            quotes = json.loads(match.group())
            return [q for q in quotes if q.get("speaker") and q.get("quote")][:3]
    except Exception as e:
        errors.append(f"news_agent quote fetch failed: {e}")
    return []


def news_agent(state: NewsletterState) -> dict:
    errors: list[str] = []

    # ── Step 1: Run all 5 Tavily queries ─────────────────────────────────────
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    week_label = state.get("week_label", "")
    for query in _build_queries(week_label):
        results = search_ai_news(query, max_results=5)
        for r in results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    if not all_results:
        errors.append("news_agent: All Tavily news queries returned empty results.")
        return {"top_news": [], "quick_hits": [], "ai_quotes": [], "errors": errors}

    # ── Step 2: Single LLM call to curate everything ──────────────────────────
    articles_text = "\n\n".join(
        f"[{i+1}] TITLE: {r['title']}\n"
        f"    SOURCE: {r['source']}\n"
        f"    DATE: {r['date']}\n"
        f"    URL: {r['url']}\n"
        f"    CONTENT: {r['content'][:400]}"
        for i, r in enumerate(all_results[:20])
    )

    prompt = f"""You are a senior AI journalist curating a weekly newsletter for a technical audience.

NEWSLETTER WEEK: {week_label}
TODAY: {datetime.now().strftime("%B %d, %Y")}

Below are {min(len(all_results), 20)} raw news snippets. STRONGLY PREFER articles from the past 7 days.
Only fall back to older articles if there is genuinely nothing recent. Analyze them carefully.

{articles_text}

Return a JSON object with EXACTLY these keys:

{{
  "top_news": [
    {{
      "rank": 1,
      "title": "Punchy headline",
      "source": "Publication name",
      "date": "DD Month YYYY",
      "url": "original URL",
      "summary": "2-3 sentences explaining what happened clearly",
      "why_it_matters": "2-3 sentences on the real-world impact for developers, businesses, or end users"
    }}
    // ... 5 items total, ranked by newsworthiness
  ],
  "quick_hits": [
    {{
      "title": "Story title",
      "url": "URL",
      "source": "Source name",
      "one_liner": "One sentence takeaway"
    }}
    // ... 4 items from the remaining stories
  ],
  "ai_quotes": [
    {{
      "quote": "Exact or paraphrased quote from an AI leader mentioned in the articles",
      "speaker": "Full name",
      "title": "Their job title",
      "source_url": "URL"
    }}
    // ... up to 3 quotes; if none found, return an empty array
  ]
}}

Return ONLY the JSON object. No explanation, no markdown, no preamble."""

    try:
        llm = config.get_llm(temperature=0.4, max_tokens=3000)
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a precise JSON-returning AI journalist. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])
        data = _parse_json(response.content)
        top_news = data.get("top_news", [])[:5]
        quick_hits = data.get("quick_hits", [])[:4]
        ai_quotes = data.get("ai_quotes", [])[:3]
    except Exception as e:
        errors.append(f"news_agent LLM call failed: {e}")
        top_news = [
            {
                "rank": i + 1,
                "title": r["title"],
                "source": r["source"],
                "date": r["date"],
                "url": r["url"],
                "summary": r["content"][:300],
                "why_it_matters": "See full article for details.",
            }
            for i, r in enumerate(all_results[:5])
        ]
        quick_hits = [
            {
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "one_liner": r["content"][:120],
            }
            for r in all_results[5:9]
        ]
        ai_quotes = []

    # ── Step 3: Dedicated quote search if LLM found none ─────────────────────
    if not ai_quotes:
        ai_quotes = _fetch_quotes(week_label, errors)

    return {
        "top_news": top_news,
        "quick_hits": quick_hits,
        "ai_quotes": ai_quotes,
        "errors": errors,
    }
