"""
compiler_agent.py — Final agent: writes the editorial copy, renders the newsletter, and saves it.

Steps:
1. LLM call → editors_note (sets tone for this week)
2. LLM call → closing_thoughts (personal, memorable sign-off)
3. Jinja2 renders the newsletter from templates/newsletter.md.j2
4. Saves to outputs/newsletter_issue_{N}_{YYYY-MM-DD}.md
5. Prints a Rich success panel

Returns: final_markdown, editors_note, closing_thoughts
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


from jinja2 import Environment, FileSystemLoader, StrictUndefined
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from state import NewsletterState
import config

console = Console(legacy_windows=False)

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"   # buzzbot-ai/templates/
_OUTPUT_DIR = Path(__file__).parent.parent / "outputs"        # buzzbot-ai/outputs/


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


def _write_editors_note(state: NewsletterState, llm) -> str:
    top_news = state.get("top_news", [])
    headlines = "\n".join(f"- {s['title']}" for s in top_news[:3]) if top_news else "- General AI developments this week"
    week_label = state.get("week_label", "this week")

    prompt = f"""Write an Editor's Note for THE AI PULSE newsletter for the week of {week_label}.

Top stories this week:
{headlines}

Deep Dive topic: {state.get('deep_dive_title', 'AI this week')}

Write 3-4 conversational, personal sentences that:
- Set the tone and vibe for this week in AI (was it exciting? chaotic? a milestone week?)
- Hint at what's inside without spoiling it
- Sound like a real human editor who loves this space, not a press release
- End with an energising sentence that makes the reader want to keep reading

Return ONLY the note text. No JSON, no labels, no preamble."""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a witty, opinionated AI newsletter editor. Write in first person, naturally."),
            HumanMessage(content=prompt),
        ])
        return response.content.strip()
    except Exception:
        return (
            f"What a week in AI — {week_label} delivered headlines that are hard to ignore. "
            f"From breakthrough models to policy debates, the pace of change isn't slowing down. "
            f"I've curated the most important stories, research, and tools so you don't have to. "
            f"Grab your coffee — there's a lot to unpack this week."
        )


def _write_closing_thoughts(state: NewsletterState, llm) -> str:
    top_news = state.get("top_news", [])
    sentiment_summary = state.get("sentiment_summary", "")
    week_label = state.get("week_label", "this week")

    top_title = top_news[0]["title"] if top_news else "AI's rapid progress"
    prompt = f"""Write a closing section for THE AI PULSE newsletter, week of {week_label}.

Biggest story this week: {top_title}
Community sentiment: {sentiment_summary}

Write 2-3 personal, memorable closing sentences that:
- Reflect genuinely on what stood out most this week
- End with a bold, forward-looking statement, prediction, or challenge to the reader
- Feel human and authentic, not generic
- Make the reader look forward to next week's issue

Return ONLY the closing text. No labels, no preamble."""

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        response = llm.invoke([
            SystemMessage(content="You are a human AI newsletter writer. Close with authenticity and vision."),
            HumanMessage(content=prompt),
        ])
        return response.content.strip()
    except Exception:
        return (
            f"This week reminded us that AI isn't just moving fast — it's moving in ways we didn't predict. "
            f"Stay curious, stay critical, and keep building. "
            f"See you next week with more signal and less noise."
        )


def compiler_agent(state: NewsletterState) -> dict:
    errors: list[str] = list(state.get("errors", []))
    llm = config.get_llm(temperature=0.7, max_tokens=800)

    # ── Step 1: Editorial copy ─────────────────────────────────────────────────
    editors_note = _write_editors_note(state, llm)
    closing_thoughts = _write_closing_thoughts(state, llm)

    # ── Step 2: Jinja2 render ──────────────────────────────────────────────────
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    jinja_env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Build the full template context
    ctx = dict(state)
    ctx["editors_note"] = editors_note
    ctx["closing_thoughts"] = closing_thoughts
    ctx["newsletter_name"] = config.NEWSLETTER_NAME
    ctx["newsletter_author"] = config.NEWSLETTER_AUTHOR

    # Replace undefined fields with safe placeholders
    _LIST_DEFAULTS = [
        "top_news", "quick_hits", "research_papers", "new_tools",
        "youtube_videos", "jobs", "events", "ai_quotes",
        "industry_usecases", "ai_stats",
    ]
    for key in _LIST_DEFAULTS:
        if not ctx.get(key):
            ctx[key] = []

    _STR_DEFAULTS = {
        "deep_dive_title": "AI Deep Dive",
        "deep_dive_content": "_No deep dive content generated this week._",
        "prompt_of_the_week": "_No prompt generated this week._",
        "prompt_category": "General",
        "prompt_use_case": "Explore AI capabilities.",
        "prompt_pro_tip": "Add your own context for better results.",
        "sentiment_summary": "Community sentiment data unavailable this week.",
    }
    for key, default in _STR_DEFAULTS.items():
        if not ctx.get(key):
            ctx[key] = default

    _INT_DEFAULTS = {
        "sentiment_hype": 50,
        "sentiment_concern": 50,
        "sentiment_optimism": 50,
        "sentiment_skepticism": 50,
    }
    for key, default in _INT_DEFAULTS.items():
        if ctx.get(key) is None:
            ctx[key] = default

    final_markdown = ""
    try:
        template = jinja_env.get_template("newsletter.j2")
        final_markdown = template.render(**ctx)
    except Exception as e:
        errors.append(f"compiler_agent Jinja2 render failed: {e}")
        final_markdown = f"# {config.NEWSLETTER_NAME}\n\n_Newsletter generation encountered an error: {e}_\n"

    # ── Step 3: Save to disk ───────────────────────────────────────────────────
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"newsletter_issue_{state.get('issue_number', 1)}_{date_str}.md"
    output_path = _OUTPUT_DIR / filename

    try:
        output_path.write_text(final_markdown, encoding="utf-8")
    except Exception as e:
        errors.append(f"compiler_agent failed to save file: {e}")

    # ── Step 4: Rich summary panel ─────────────────────────────────────────────
    word_count = len(final_markdown.split())
    section_count = final_markdown.count("\n## ") + final_markdown.count("\n# ")

    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Output file", str(output_path))
    table.add_row("Word count", f"{word_count:,}")
    table.add_row("Sections", str(section_count))
    table.add_row("Errors", str(len(errors)) if errors else "[green]None[/green]")

    console.print(
        Panel(
            table,
            title="[bold green] Newsletter Generated Successfully[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )

    if errors:
        console.print("\n[yellow]Errors encountered during generation:[/yellow]")
        for err in errors:
            console.print(f"  [red]•[/red] {err}")

    return {
        "final_markdown": final_markdown,
        "editors_note": editors_note,
        "closing_thoughts": closing_thoughts,
        "errors": errors,
    }
