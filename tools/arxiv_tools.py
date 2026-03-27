"""
arxiv_tools.py — Fetch and rank recent AI research papers from arXiv.
"""

from __future__ import annotations

import json
import re
import sys
import os
from datetime import datetime, timedelta, timezone


import arxiv


_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "stat.ML"]


def fetch_recent_papers(max_results: int = 15) -> list[dict]:
    """
    Fetch arXiv papers from the last 7 days across major AI categories.
    Deduplicates by arXiv ID. Returns up to max_results papers sorted by date.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    client = arxiv.Client()
    seen_ids: set[str] = set()
    papers: list[dict] = []

    for category in _CATEGORIES:
        try:
            search = arxiv.Search(
                query=f"cat:{category}",
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )
            for result in client.results(search):
                # Normalise published to UTC-aware datetime
                pub = result.published
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)

                if pub < cutoff:
                    break  # results are sorted newest-first; stop early

                raw_id = result.entry_id.split("/")[-1]
                arxiv_id = re.sub(r"v\d+$", "", raw_id)

                if arxiv_id in seen_ids:
                    continue
                seen_ids.add(arxiv_id)

                authors = result.authors[:3]
                author_str = ", ".join(str(a) for a in authors)
                if len(result.authors) > 3:
                    author_str += " et al."

                papers.append({
                    "title": result.title.strip(),
                    "authors": author_str,
                    "abstract": result.summary.strip()[:400],
                    "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                    "pdf_url": result.pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
                    "published": pub.strftime("%Y-%m-%d"),
                    "primary_category": result.primary_category,
                    "score": 5,  # default; updated by score_and_rank_papers
                })
        except Exception:
            pass  # skip failed category silently

    # Sort by published date descending
    papers.sort(key=lambda p: p["published"], reverse=True)
    return papers[:max_results]


def score_and_rank_papers(papers: list[dict], llm) -> list[dict]:
    """
    Use a single batched LLM call to score all papers 1-10 on newsworthiness
    for a general AI audience. Returns papers sorted best-first.
    """
    if not papers:
        return []

    # Build a compact list for the LLM
    paper_list = "\n".join(
        f"{i+1}. TITLE: {p['title']}\n   ABSTRACT: {p['abstract'][:200]}"
        for i, p in enumerate(papers)
    )

    prompt = f"""You are an AI newsletter editor. Rate each paper 1-10 on how newsworthy and interesting it is for a general technical AI audience (10 = groundbreaking, 1 = highly niche).

Papers to rate:
{paper_list}

Return ONLY a valid JSON array of objects with keys "index" (1-based) and "score" (integer 1-10).
Example: [{{"index": 1, "score": 8}}, {{"index": 2, "score": 5}}]
Return ONLY the JSON array, no other text."""

    try:
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content=prompt)])
        text = response.content.strip()

        # Extract JSON array
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        if match:
            scores = json.loads(match.group())
            score_map = {item["index"]: item["score"] for item in scores}
            for i, paper in enumerate(papers):
                paper["score"] = score_map.get(i + 1, 5)
    except Exception:
        pass  # keep default score=5 if LLM fails

    return sorted(papers, key=lambda p: p["score"], reverse=True)
