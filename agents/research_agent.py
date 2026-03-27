"""
research_agent.py — Fetches and explains the week's top AI research papers.

1. Fetches recent arXiv papers (last 7 days, multi-category)
2. Ranks them with a batched LLM call
3. Writes plain-English summaries for the top 3
4. Remaining papers get a one-line TL;DR

Returns: research_papers (first 3 are featured with full writeups, rest are extras)
"""

from __future__ import annotations

import json
import re
import sys
import os


from state import NewsletterState
import config
from tools.arxiv_tools import fetch_recent_papers, score_and_rank_papers


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


def _write_paper_summary(paper: dict, llm) -> dict:
    """Use LLM to write a reader-friendly summary of one arXiv paper."""
    prompt = f"""Write a plain-English summary of this AI research paper for a newsletter audience that is technically curious but not specialists.

TITLE: {paper['title']}
AUTHORS: {paper['authors']}
ABSTRACT: {paper['abstract']}

Return a JSON object with EXACTLY these keys:
{{
  "what_its_about": "2-3 sentences explaining the paper like the reader is smart but not a specialist. What problem does it solve?",
  "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
  "real_world_impact": "1-2 sentences on why this research matters for the AI industry or society."
}}

Return ONLY the JSON. No preamble, no markdown."""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are an AI research communicator. Return only valid JSON."),
            HumanMessage(content=prompt),
        ])
        data = _parse_json(response.content)
        paper["what_its_about"] = data.get("what_its_about", paper["abstract"][:300])
        paper["key_findings"] = data.get("key_findings", ["See paper for details."])
        paper["real_world_impact"] = data.get("real_world_impact", "Significant implications for AI development.")
        paper["is_featured"] = True
    except Exception as e:
        paper["what_its_about"] = paper["abstract"][:300]
        paper["key_findings"] = ["See paper for details."]
        paper["real_world_impact"] = "See full paper."
        paper["is_featured"] = True
    return paper


def _write_tldr(paper: dict, llm) -> dict:
    """Generate a one-line TL;DR for an extra paper."""
    prompt = f"""Write a single sentence (max 20 words) summarising this AI paper for a newsletter.

TITLE: {paper['title']}
ABSTRACT: {paper['abstract'][:300]}

Return ONLY the sentence. No JSON, no preamble."""

    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        paper["tldr"] = response.content.strip()[:200]
    except Exception:
        paper["tldr"] = paper["abstract"][:120] + "..."
    paper["is_featured"] = False
    return paper


def research_agent(state: NewsletterState) -> dict:
    errors: list[str] = []
    llm = config.get_llm(temperature=0.3, max_tokens=2000)

    # ── Step 1: Fetch papers ──────────────────────────────────────────────────
    papers = fetch_recent_papers(max_results=15)

    if not papers:
        errors.append("research_agent: No arXiv papers found for the past 7 days.")
        return {"research_papers": [], "errors": errors}

    # ── Step 2: Score and rank ────────────────────────────────────────────────
    papers = score_and_rank_papers(papers, llm)

    # ── Step 3: Full writeups for top 3 ──────────────────────────────────────
    featured = []
    for paper in papers[:3]:
        featured.append(_write_paper_summary(paper, llm))

    # ── Step 4: One-liners for the rest ──────────────────────────────────────
    extras = []
    for paper in papers[3:]:
        extras.append(_write_tldr(paper, llm))

    return {"research_papers": featured + extras, "errors": errors}
