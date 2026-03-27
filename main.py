"""
main.py — Entry point for the AI Newsletter Multi-Agent System.

Usage:
    python main.py
"""

from __future__ import annotations

import sys
import os

# Force UTF-8 on Windows so Rich emojis don't crash the terminal
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime, timedelta, timezone

# ── Validate environment FIRST (exits with clear error if keys missing) ────────
import config
config.validate()

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box
from langgraph.checkpoint.memory import MemorySaver

# Windows: disable legacy renderer so Rich can output emojis via VT sequences
console = Console(legacy_windows=False)

from state import NewsletterState, default_state
from graph import build_graph

# ── Agent display names and phases ────────────────────────────────────────────
_PHASE1_AGENTS = ["news_agent", "research_agent", "tools_agent", "youtube_agent", "jobs_agent", "events_agent"]
_PHASE2_AGENTS = ["analysis_agent", "prompt_agent"]
_PHASE3_AGENTS = ["compiler_agent"]
_ALL_AGENTS = _PHASE1_AGENTS + _PHASE2_AGENTS + _PHASE3_AGENTS

_AGENT_LABELS = {
    "news_agent": "📰 News Collector",
    "research_agent": "🧠 Research Finder",
    "tools_agent": "🛠️  Tools Scout",
    "youtube_agent": "📺 YouTube Curator",
    "jobs_agent": "💼 Jobs Hunter",
    "events_agent": "📅 Events Tracker",
    "analysis_agent": "🔍 Deep Dive Analyst",
    "prompt_agent": "✍️  Prompt Engineer",
    "compiler_agent": "📋 Newsletter Compiler",
}

_PHASE_LABELS = {
    "news_agent": "Phase 1 · Parallel",
    "research_agent": "Phase 1 · Parallel",
    "tools_agent": "Phase 1 · Parallel",
    "youtube_agent": "Phase 1 · Parallel",
    "jobs_agent": "Phase 1 · Parallel",
    "events_agent": "Phase 1 · Parallel",
    "analysis_agent": "Phase 2 · Sequential",
    "prompt_agent": "Phase 2 · Sequential",
    "compiler_agent": "Phase 3 · Compile",
}


def _compute_week_label() -> str:
    """Compute 'Month DD–DD, YYYY' for the current week (last 7 days ending today)."""
    today = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=6)  # 7-day window ending today

    if week_start.month == today.month:
        return f"{week_start.strftime('%B')} {week_start.day}–{today.day}, {today.year}"
    else:
        return (
            f"{week_start.strftime('%B')} {week_start.day} – "
            f"{today.strftime('%B')} {today.day}, {today.year}"
        )


def _build_status_table(statuses: dict[str, str], start_times: dict[str, float]) -> Table:
    """Render the live agent status table."""
    import time
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold magenta", padding=(0, 1))
    table.add_column("Agent", style="white", min_width=28)
    table.add_column("Phase", style="dim", min_width=20)
    table.add_column("Status", min_width=16)
    table.add_column("Elapsed", justify="right", min_width=8)

    status_icons = {
        "waiting": "[dim]⏳ Waiting[/dim]",
        "running": "[yellow]⚡ Running[/yellow]",
        "done": "[green]✓ Done[/green]",
        "error": "[red]✗ Error[/red]",
    }

    for agent in _ALL_AGENTS:
        status = statuses.get(agent, "waiting")
        label = _AGENT_LABELS.get(agent, agent)
        phase = _PHASE_LABELS.get(agent, "")
        icon = status_icons.get(status, "[dim]?[/dim]")

        # Elapsed time
        elapsed = ""
        if agent in start_times:
            secs = time.time() - start_times[agent]
            elapsed = f"{secs:.1f}s"

        table.add_row(label, phase, icon, elapsed)

    return table


def main():
    import time

    console.print(
        Panel(
            f"[bold white]{config.NEWSLETTER_NAME}[/bold white] — AI Newsletter Generator\n"
            f"[dim]Issue #{config.NEWSLETTER_ISSUE_NUMBER} · {config.NEWSLETTER_AUTHOR}[/dim]",
            border_style="bright_blue",
            padding=(1, 4),
        )
    )

    # ── Build initial state ────────────────────────────────────────────────────
    week_label = _compute_week_label()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    initial_state = default_state(
        issue_number=config.NEWSLETTER_ISSUE_NUMBER,
        week_label=week_label,
        generated_at=generated_at,
    )

    console.print(f"\n[cyan]Week:[/cyan] {week_label}")
    console.print(f"[cyan]Generated at:[/cyan] {generated_at}\n")

    # ── Build the graph ────────────────────────────────────────────────────────
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    thread_id = f"newsletter_{config.NEWSLETTER_ISSUE_NUMBER}_{datetime.now().strftime('%Y%m%d')}"
    run_config = {"configurable": {"thread_id": thread_id}}

    # ── Live status tracking ───────────────────────────────────────────────────
    statuses: dict[str, str] = {agent: "waiting" for agent in _ALL_AGENTS}
    start_times: dict[str, float] = {}
    pipeline_start = time.time()

    console.print("[bold]Running agents...[/bold]\n")

    final_state: NewsletterState | None = None

    with Live(
        _build_status_table(statuses, start_times),
        console=console,
        refresh_per_second=4,
    ) as live:
        try:
            for event in graph.stream(
                initial_state,
                config=run_config,
                stream_mode="updates",
            ):
                for node_name, _ in event.items():
                    if node_name in _ALL_AGENTS:
                        if statuses.get(node_name) == "waiting":
                            statuses[node_name] = "running"
                            start_times[node_name] = time.time()

                        # Mark running agents that just produced output as done
                        statuses[node_name] = "done"

                live.update(_build_status_table(statuses, start_times))

            # Retrieve final state from checkpointer
            final_state = graph.get_state(run_config).values

        except Exception as e:
            console.print(f"\n[red bold]Pipeline error: {e}[/red bold]")
            sys.exit(1)

    total_elapsed = time.time() - pipeline_start
    console.print(f"\n[green]All agents completed in {total_elapsed:.1f}s[/green]\n")

    # ── Final validation ───────────────────────────────────────────────────────
    if not final_state or not final_state.get("final_markdown"):
        console.print("[red bold]ERROR: final_markdown is empty. Newsletter generation failed.[/red bold]")
        sys.exit(1)

    errors = final_state.get("errors", [])
    if errors:
        console.print(f"\n[yellow]⚠  {len(errors)} non-fatal error(s) occurred during generation.[/yellow]")

    console.print("\n[bold green]Done! Your newsletter is ready.[/bold green]")


if __name__ == "__main__":
    main()
