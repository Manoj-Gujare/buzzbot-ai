"""
tools_agent.py — Finds and curates new AI tools launched this week.

Also collects industry use cases and AI stats (all Tavily-based, batched here
to avoid spawning extra Phase 1 nodes for lightweight searches).

Returns: new_tools, industry_usecases, ai_stats
"""

from __future__ import annotations

import json
import re
import sys
import os


from state import NewsletterState
import config
from tools.tavily_tools import search_ai_tools, search_industry_usecases, search_ai_stats


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


def _clean_usecases(raw: list[dict], llm) -> list[dict]:
    """Use LLM to extract clean industry/company/outcome rows from raw Tavily snippets."""
    if not raw:
        return []
    snippets = "\n\n".join(
        f"[{i+1}] TITLE: {r.get('title','')}\n"
        f"     CONTENT: {r.get('content','')[:400]}\n"
        f"     URL: {r.get('url','')}"
        for i, r in enumerate(raw[:15])
    )
    prompt = f"""From these web snippets about real-world AI deployments, extract up to 5 specific examples.

{snippets}

STRICT RULES:
- "company" must be a real, named company (e.g. "JPMorgan Chase", "Mayo Clinic", "Walmart") — never "Various", "See source", or a website domain
- "outcome" must be a specific measurable result (e.g. "Cut diagnosis time by 40%", "Saved $1.2B annually", "Reduced fraud by 60%") — never vague phrases
- "industry" must be one of: Healthcare, Finance, Retail, Manufacturing, Education, Legal, Energy, Agriculture, Technology, Logistics
- "use_case" must describe the specific AI application in max 50 chars (e.g. "AI-powered fraud detection", "Medical imaging diagnosis")
- Skip any result where you cannot identify a real company name and a specific outcome

Return a JSON array (only items that meet ALL rules):
[
  {{
    "industry": "Healthcare",
    "use_case": "AI radiology screening",
    "company": "Mayo Clinic",
    "outcome": "Detected early cancers 35% faster than radiologists",
    "url": "https://..."
  }}
]

Return ONLY the JSON array. No preamble."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        resp = llm.invoke([
            SystemMessage(content="You are a precise JSON extractor. Never invent data. Skip entries with vague or missing company/outcome."),
            HumanMessage(content=prompt),
        ])
        text = resp.content.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            results = json.loads(match.group())
            # Filter out any that slipped through with vague values
            clean = [
                r for r in results
                if r.get("company") and r["company"].lower() not in {"various", "see source", "unknown", ""}
                and r.get("outcome") and r["outcome"].lower() not in {"see source", "significant improvements reported.", ""}
            ]
            return clean[:5]
    except Exception:
        pass
    return []


def _clean_stats(raw: list[dict], llm) -> list[dict]:
    """Use LLM to extract clean metric/number/context rows from raw Tavily snippets."""
    if not raw:
        return []
    snippets = "\n\n".join(
        f"[{i+1}] {r.get('context','')[:300]}"
        for i, r in enumerate(raw[:6])
    )
    prompt = f"""From these web snippets about AI statistics, extract up to 5 specific, compelling data points.

{snippets}

Return a JSON array of objects with keys: metric (short label, max 40 chars), number (the actual figure e.g. "$200B", "1.8B users", "55%"), context (one sentence explaining what this means, max 100 chars).
Only include data points that have a real specific number. Return ONLY the JSON array."""
    try:
        from langchain_core.messages import HumanMessage
        resp = llm.invoke([HumanMessage(content=prompt)])
        text = resp.content.strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())[:5]
    except Exception:
        pass
    return raw[:5]


def tools_agent(state: NewsletterState) -> dict:
    errors: list[str] = []
    week_label = state.get("week_label", "this week")
    llm = config.get_llm(temperature=0.3, max_tokens=1500)

    # ── Fetch tools ───────────────────────────────────────────────────────────
    raw_tools = search_ai_tools(week_label, max_results=8)

    # ── Fetch and LLM-clean supporting data ───────────────────────────────────
    raw_usecases = search_industry_usecases(max_results=6)
    raw_stats = search_ai_stats(max_results=6)
    industry_usecases = _clean_usecases(raw_usecases, llm)
    ai_stats = _clean_stats(raw_stats, llm)

    if not raw_tools:
        errors.append("tools_agent: No AI tools found via Tavily.")
        return {
            "new_tools": [],
            "industry_usecases": industry_usecases,
            "ai_stats": ai_stats,
            "errors": errors,
        }

    # ── LLM: Pick Tool of the Week + enrich all tools ─────────────────────────
    tools_text = "\n\n".join(
        f"[{i+1}] NAME: {t['name']}\n"
        f"     DESCRIPTION: {t['description'][:250]}\n"
        f"     URL: {t['url']}"
        for i, t in enumerate(raw_tools[:8])
    )

    prompt = f"""You are an AI tools curator for a weekly newsletter. Review these new AI tools and:
1. Identify the single best "Tool of the Week" — the most innovative, useful, and widely applicable
2. For the Tool of the Week, write a compelling 2-3 sentence "why_we_love_it"
3. Assign a clean category (Writing, Coding, Image, Audio, Video, Productivity, Research, etc.)
4. Estimate pricing tier if not obvious (Free / Freemium / Paid)
5. Write a punchy one-liner description for each remaining tool

Tools:
{tools_text}

Return a JSON object with EXACTLY these keys:
{{
  "featured": {{
    "index": 1,
    "name": "Tool name",
    "company": "Company/developer name",
    "category": "Category",
    "description": "2-3 sentence expanded description",
    "why_we_love_it": "2-3 sentences on why this tool stands out",
    "pricing": "Free/Freemium/Paid – $X/mo",
    "best_for": "Developers / Marketers / Everyone / etc.",
    "url": "URL",
    "is_featured": true
  }},
  "table_tools": [
    {{
      "name": "Tool name",
      "category": "Category",
      "one_liner": "Max 15 word description",
      "pricing": "Free/Freemium/Paid",
      "url": "URL",
      "is_featured": false
    }}
    // up to 5 remaining tools
  ]
}}

Return ONLY the JSON. No preamble."""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a precise JSON-returning tech curator. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])
        data = _parse_json(response.content)
        featured = data.get("featured", {})
        # Back-fill URL from raw_tools if LLM didn't include it
        if featured and not featured.get("url"):
            idx = featured.get("index", 1) - 1
            if 0 <= idx < len(raw_tools):
                featured["url"] = raw_tools[idx]["url"]
        table = data.get("table_tools", [])
        # Back-fill URLs
        for tool in table:
            if not tool.get("url"):
                for rt in raw_tools:
                    if rt["name"].lower() in tool.get("name", "").lower():
                        tool["url"] = rt["url"]
                        break
        new_tools = ([featured] if featured else []) + table[:5]
    except Exception as e:
        errors.append(f"tools_agent LLM call failed: {e}")
        new_tools = []
        for i, t in enumerate(raw_tools[:6]):
            t["is_featured"] = i == 0
            if i == 0:
                t["why_we_love_it"] = t["description"][:200]
                t["best_for"] = "Everyone"
            else:
                t["one_liner"] = t["description"][:80]
            new_tools.append(t)

    return {
        "new_tools": new_tools,
        "industry_usecases": industry_usecases,
        "ai_stats": ai_stats,
        "errors": errors,
    }
