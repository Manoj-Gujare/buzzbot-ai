# Architecture

This document describes how the newsletter pipeline is **wired together** so you can extend or debug it.

## Entry point

- **`main.py`** — Imports `config` (triggers `.env` load + `validate()`), builds `default_state(...)`, compiles the graph with `MemorySaver`, streams updates for a Rich live table, then reads final state from the checkpointer. Fails if `final_markdown` is empty.

## Graph

- **`graph.py`** — Defines a `StateGraph` over `NewsletterState`.

Flow:

1. **Phase 1** — From `START`, edges go to six nodes in parallel: `news_agent`, `research_agent`, `tools_agent`, `youtube_agent`, `jobs_agent`, `events_agent`.
2. **Fan-in** — Each of those six nodes has an edge to `analysis_agent`. LangGraph waits until **all** predecessors complete before running `analysis_agent`.
3. **Phase 2** — `analysis_agent` → `prompt_agent` (sequential).
4. **Phase 3** — `prompt_agent` → `compiler_agent` → `END`.

## State

- **`state.py`** — `NewsletterState` is a `TypedDict` holding:

  - **Meta:** `issue_number`, `week_label`, `generated_at`
  - **Collected data:** lists such as `top_news`, `quick_hits`, `research_papers`, `new_tools`, `youtube_videos`, `jobs`, `events`, `ai_quotes`, `industry_usecases`, `ai_stats`
  - **LLM sections:** `editors_note`, `deep_dive_*`, `prompt_*`, `closing_thoughts`, sentiment fields
  - **Output:** `final_markdown`
  - **Errors:** `errors` is `Annotated[list[str], operator.add]` so parallel nodes can append without clobbering each other

`default_state(...)` initializes empty lists and neutral defaults for sentiment integers.

## Agents

Each node under `agents/` is a function `(state) -> dict` returning partial state updates (and optionally `errors`).

Rough responsibilities:

| Agent | Typical role |
|-------|----------------|
| `news_agent` | Headlines / quick hits (Tavily-backed search patterns in code) |
| `research_agent` | Papers (arXiv tooling in `tools/`) |
| `tools_agent` | New tools / product signal |
| `youtube_agent` | Curated videos (YouTube API) |
| `jobs_agent` | Job listings |
| `events_agent` | Events |
| `analysis_agent` | Deep dive + sentiment meter (uses Bedrock; consumes prior state like `top_news`) |
| `prompt_agent` | Prompt of the week copy |
| `compiler_agent` | Editor’s note and closing via LLM, Jinja2 render, write `outputs/newsletter_issue_{N}_{date}.md` |

Read individual modules for exact prompts and tool usage.

## Tools

- **`tools/`** — Shared integrations (e.g. Tavily, arXiv, YouTube). Agents import these rather than duplicating HTTP or client setup.

## Template and output

- **`templates/newsletter.j2`** — Jinja2 template; context is built from state plus `newsletter_name`, `newsletter_author`, and compiler-filled fields.
- **`outputs/`** — Generated Markdown per run; path is printed in a Rich panel from `compiler_agent`.

## Extending the pipeline

1. Add fields to `NewsletterState` and `default_state` if you need new data.
2. Implement or adjust an agent module; return only the keys you update.
3. Register the node in `graph.py` and connect edges so ordering matches your dependencies (parallel vs fan-in vs sequential).
4. Update `newsletter.j2` (and optionally `main.py` status labels) if you add a visible section.
