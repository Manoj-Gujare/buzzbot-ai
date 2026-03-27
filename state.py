"""
state.py — Shared state TypedDict for the LangGraph newsletter pipeline.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class NewsletterState(TypedDict):
    # ── Meta ──────────────────────────────────────────────────────────────────
    issue_number: int
    week_label: str          # e.g. "March 17–23, 2025"
    generated_at: str        # ISO timestamp

    # ── Raw data collected by agents ─────────────────────────────────────────
    top_news: list[dict]           # 5 main stories
    quick_hits: list[dict]         # 4 smaller stories
    research_papers: list[dict]    # 3 featured (full) + extras
    new_tools: list[dict]          # 1 featured (is_featured=True) + 5 table rows
    youtube_videos: list[dict]     # must_watch, tutorial, explainer
    jobs: list[dict]
    events: list[dict]
    ai_quotes: list[dict]
    industry_usecases: list[dict]
    ai_stats: list[dict]

    # ── LLM-written content ───────────────────────────────────────────────────
    editors_note: str
    deep_dive_title: str
    deep_dive_content: str
    prompt_of_the_week: str
    prompt_category: str
    prompt_use_case: str
    prompt_pro_tip: str
    closing_thoughts: str

    # ── Sentiment scores 0-100 ────────────────────────────────────────────────
    sentiment_hype: int
    sentiment_concern: int
    sentiment_optimism: int
    sentiment_skepticism: int
    sentiment_summary: str

    # ── Output ────────────────────────────────────────────────────────────────
    final_markdown: str
    # Annotated with operator.add so parallel agents can each append errors
    errors: Annotated[list[str], operator.add]


def default_state(issue_number: int, week_label: str, generated_at: str) -> NewsletterState:
    """Return a fully-initialized NewsletterState with safe defaults."""
    return NewsletterState(
        issue_number=issue_number,
        week_label=week_label,
        generated_at=generated_at,
        top_news=[],
        quick_hits=[],
        research_papers=[],
        new_tools=[],
        youtube_videos=[],
        jobs=[],
        events=[],
        ai_quotes=[],
        industry_usecases=[],
        ai_stats=[],
        editors_note="",
        deep_dive_title="",
        deep_dive_content="",
        prompt_of_the_week="",
        prompt_category="",
        prompt_use_case="",
        prompt_pro_tip="",
        closing_thoughts="",
        sentiment_hype=50,
        sentiment_concern=50,
        sentiment_optimism=50,
        sentiment_skepticism=50,
        sentiment_summary="",
        final_markdown="",
        errors=[],
    )
