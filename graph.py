"""
graph.py — LangGraph StateGraph definition for the newsletter pipeline.

Topology:
  Phase 1 (parallel fan-out from START):
    news_agent, research_agent, tools_agent, youtube_agent, jobs_agent, events_agent

  Phase 2 (sequential, after ALL Phase 1 nodes complete):
    analysis_agent → prompt_agent

  Phase 3:
    compiler_agent → END
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import NewsletterState
from agents.news_agent import news_agent
from agents.research_agent import research_agent
from agents.tools_agent import tools_agent
from agents.youtube_agent import youtube_agent
from agents.jobs_agent import jobs_agent
from agents.events_agent import events_agent
from agents.analysis_agent import analysis_agent
from agents.prompt_agent import prompt_agent
from agents.compiler_agent import compiler_agent


def build_graph(checkpointer: MemorySaver | None = None) -> StateGraph:
    """Build and compile the newsletter state graph."""
    workflow = StateGraph(NewsletterState)

    # ── Register all nodes ────────────────────────────────────────────────────
    workflow.add_node("news_agent", news_agent)
    workflow.add_node("research_agent", research_agent)
    workflow.add_node("tools_agent", tools_agent)
    workflow.add_node("youtube_agent", youtube_agent)
    workflow.add_node("jobs_agent", jobs_agent)
    workflow.add_node("events_agent", events_agent)
    workflow.add_node("analysis_agent", analysis_agent)
    workflow.add_node("prompt_agent", prompt_agent)
    workflow.add_node("compiler_agent", compiler_agent)

    # ── Phase 1: Fan-out from START (all run in parallel) ─────────────────────
    for node in ["news_agent", "research_agent", "tools_agent", "youtube_agent", "jobs_agent", "events_agent"]:
        workflow.add_edge(START, node)

    # ── Phase 1 → Phase 2: Fan-in to analysis_agent (waits for all 6) ─────────
    # LangGraph waits until ALL predecessors of a node have completed.
    for node in ["news_agent", "research_agent", "tools_agent", "youtube_agent", "jobs_agent", "events_agent"]:
        workflow.add_edge(node, "analysis_agent")

    # ── Phase 2: Sequential ───────────────────────────────────────────────────
    workflow.add_edge("analysis_agent", "prompt_agent")

    # ── Phase 3: Compile and output ───────────────────────────────────────────
    workflow.add_edge("prompt_agent", "compiler_agent")
    workflow.add_edge("compiler_agent", END)

    return workflow.compile(checkpointer=checkpointer)
